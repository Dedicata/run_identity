import logging
import os

from odoo import api, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)

PROVIDER_XMLID = "dedicata_auth_oidc_keycloak.provider_keycloak"

ENV_BLOCK_OAUTH_AUTO_CREATE = "DEDICATA_RUN_IDENTITY_BLOCK_OAUTH_AUTO_CREATE"
ENV_DISABLE_PASSWORD_LOGIN = "DEDICATA_RUN_IDENTITY_DISABLE_PASSWORD_LOGIN"
ENV_HIDE_PASSWORD_FORM = "DEDICATA_RUN_IDENTITY_HIDE_PASSWORD_FORM"
ENV_LOCAL_LOGIN_ALLOWLIST = "DEDICATA_RUN_IDENTITY_LOCAL_LOGIN_ALLOWLIST"
ENV_DEFAULT_GROUP_XMLIDS = "DEDICATA_RUN_IDENTITY_DEFAULT_GROUP_XMLIDS"
ENV_LOCK_USER_IDENTITY = "DEDICATA_RUN_IDENTITY_LOCK_USER_IDENTITY"

RUN_SYNC_CONTEXT_KEY = "dedicata_run_identity_sync"
FALSE_VALUES = {"0", "false", "no", "off"}
MANAGED_USER_FIELDS = {
    "active",
    "dedicata_run_managed",
    "email",
    "login",
    "name",
    "oauth_provider_id",
    "oauth_uid",
}


def get_bool_env(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() not in FALSE_VALUES


def get_csv_env(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        value = default
    return [item.strip() for item in value.split(",") if item.strip()]


def payload_bool(value, default):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in FALSE_VALUES
    return bool(value)


class DedicataRunIdentity(models.Model):
    _name = "dedicata.run.identity"
    _description = "Dedicata Run Identity Provisioning"

    @api.model
    def _keycloak_provider(self):
        provider = self.env.ref(PROVIDER_XMLID, raise_if_not_found=False)
        if not provider:
            raise UserError("Dedicata Keycloak provider was not found.")
        return provider.sudo()

    @api.model
    def _default_group_ids(self):
        groups = self.env["res.groups"].sudo()
        for xmlid in get_csv_env(ENV_DEFAULT_GROUP_XMLIDS, "base.group_user"):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group and group._name == "res.groups":
                groups |= group.sudo()
            else:
                _logger.warning("Ignoring unknown default user group XMLID: %s", xmlid)
        return groups.ids

    @api.model
    def _users_group_field(self):
        Users = self.env["res.users"]
        if "groups_id" in Users._fields:
            return "groups_id"
        if "group_ids" in Users._fields:
            return "group_ids"
        raise UserError("Could not find the users groups field.")

    @api.model
    def _normalize_payload(self, payload):
        payload = payload or {}
        sub = (payload.get("sub") or payload.get("oauth_uid") or "").strip()
        email = (payload.get("email") or "").strip()
        name = (payload.get("name") or "").strip()
        login = (payload.get("login") or payload.get("username") or email).strip()
        missing = [
            field
            for field, value in (("email", email), ("name", name))
            if not value
        ]
        if missing:
            raise UserError("Missing required identity fields: %s" % ", ".join(missing))
        values = {
            "name": name,
            "login": login,
            "email": email,
            "oauth_uid": sub,
            "active": payload_bool(payload.get("active"), True),
            "dedicata_run_managed": True,
        }
        for optional_field in ("lang", "tz"):
            if payload.get(optional_field):
                values[optional_field] = payload[optional_field]
        local_login = payload.get("local_login_allowed")
        if local_login is not None:
            values["dedicata_run_local_login_allowed"] = payload_bool(local_login, False)
        return values

    @api.model
    def _find_user(self, provider, values):
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        if values.get("oauth_uid"):
            user = Users.search(
                [
                    ("oauth_provider_id", "=", provider.id),
                    ("oauth_uid", "=", values["oauth_uid"]),
                ],
                limit=1,
            )
            if user:
                return user

        user = Users.search([("login", "=", values["login"])], limit=1)
        if user:
            return user

        return Users.search([("email", "=", values["email"])], limit=1)

    @api.model
    def _serialize_user(self, user, created=False, updated=False):
        return {
            "user_id": user.id,
            "login": user.login,
            "email": user.email,
            "oauth_uid": user.oauth_uid,
            "created": created,
            "updated": updated,
        }

    @api.model
    def upsert_user(self, payload):
        provider = self._keycloak_provider()
        values = self._normalize_payload(payload)
        values["oauth_provider_id"] = provider.id

        user = self._find_user(provider, values)
        Users = self.env["res.users"].sudo().with_context(
            active_test=False,
            **{RUN_SYNC_CONTEXT_KEY: True},
        )
        if not user:
            create_values = dict(values)
            user = Users.create(create_values)
            group_ids = self._default_group_ids()
            if group_ids:
                user.write({self._users_group_field(): [(6, 0, group_ids)]})
            return self._serialize_user(user, created=True)

        if user.oauth_provider_id and user.oauth_provider_id != provider:
            raise UserError("Existing user is already linked to another OAuth provider.")
        if user.oauth_uid and values["oauth_uid"] and user.oauth_uid != values["oauth_uid"]:
            raise UserError("Existing user is already linked to another OAuth subject.")

        write_values = dict(values)
        if not write_values.get("oauth_uid") and user.oauth_uid:
            write_values.pop("oauth_uid", None)
        user.with_context(**{RUN_SYNC_CONTEXT_KEY: True}).write(write_values)
        return self._serialize_user(user, updated=True)

    @api.model
    def deactivate_user(self, payload):
        payload = payload or {}
        provider = self._keycloak_provider()
        values = self._normalize_payload(
            {
                "sub": payload.get("sub") or payload.get("oauth_uid"),
                "email": payload.get("email") or "placeholder@example.invalid",
                "name": payload.get("name") or "Placeholder",
            }
        )
        user = self._find_user(provider, values)
        if not user:
            return {
                "user_id": False,
                "login": False,
                "email": False,
                "oauth_uid": values["oauth_uid"],
                "created": False,
                "updated": False,
            }
        user.with_context(**{RUN_SYNC_CONTEXT_KEY: True}).sudo().write({"active": False})
        return self._serialize_user(user, updated=True)

    @api.model
    def get_user(self, payload):
        payload = payload or {}
        provider = self._keycloak_provider()
        values = self._normalize_payload(
            {
                "sub": payload.get("sub") or payload.get("oauth_uid"),
                "email": payload.get("email") or "placeholder@example.invalid",
                "name": payload.get("name") or "Placeholder",
                "login": payload.get("login") or payload.get("email"),
            }
        )
        user = self._find_user(provider, values)
        if not user:
            return False
        return self._serialize_user(user)

    @api.model
    def archive_user_by_login(self, username):
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        user = Users.search([("login", "=", username)], limit=1)
        if not user:
            return None
        user.with_context(**{RUN_SYNC_CONTEXT_KEY: True}).write({"active": False})
        return {
            "user_id": user.id,
            "login": user.login,
            "email": user.email,
            "archived": True,
        }

    @api.model
    def should_block_oauth_auto_create(self, provider_id):
        provider = self.env.ref(PROVIDER_XMLID, raise_if_not_found=False)
        return bool(
            provider
            and provider.id == provider_id
            and get_bool_env(ENV_BLOCK_OAUTH_AUTO_CREATE, True)
        )

    @api.model
    def should_hide_password_form(self):
        if not get_bool_env(ENV_HIDE_PASSWORD_FORM, True):
            return False
        provider = self.env.ref(PROVIDER_XMLID, raise_if_not_found=False)
        return bool(provider and provider.sudo().enabled)

    @api.model
    def should_disable_password_login(self, login, interactive=True):
        if not interactive or not get_bool_env(ENV_DISABLE_PASSWORD_LOGIN, True):
            return False
        provider = self.env.ref(PROVIDER_XMLID, raise_if_not_found=False)
        if not (provider and provider.sudo().enabled):
            return False
        login = (login or "").strip()
        # 1. Explicit ENV allowlist – escape hatch for ops (defaults to empty).
        if login in get_csv_env(ENV_LOCAL_LOGIN_ALLOWLIST, ""):
            return False
        # 2. Per-user flag: the instance master (base.user_admin) has this flag
        #    set by the post_init_hook.  The Run platform can also grant/revoke
        #    it programmatically via upsert_user().
        user = (
            self.env["res.users"]
            .sudo()
            .with_context(active_test=False)
            .search([("login", "=", login)], limit=1)
        )
        if user and user.dedicata_run_local_login_allowed:
            return False
        return True

    @api.model
    def is_user_identity_locked(self):
        return get_bool_env(ENV_LOCK_USER_IDENTITY, True)
