import logging
import os

from odoo import api

_logger = logging.getLogger(__name__)

PROVIDER_XMLID = "dedicata_auth_oidc_keycloak.provider_keycloak"

ENV_ISSUER_URL = "DEDICATA_KEYCLOAK_ISSUER_URL"
ENV_CLIENT_ID = "DEDICATA_KEYCLOAK_CLIENT_ID"
ENV_CLIENT_SECRET = "DEDICATA_KEYCLOAK_CLIENT_SECRET"
ENV_ENABLED = "DEDICATA_KEYCLOAK_ENABLED"
ENV_PROVIDER_NAME = "DEDICATA_KEYCLOAK_PROVIDER_NAME"
ENV_LOGIN_LABEL = "DEDICATA_KEYCLOAK_LOGIN_LABEL"
ENV_SCOPE = "DEDICATA_KEYCLOAK_SCOPE"
ENV_TOKEN_MAP = "DEDICATA_KEYCLOAK_TOKEN_MAP"
ENV_LOCK_PROVIDER_CONFIG = "DEDICATA_KEYCLOAK_LOCK_PROVIDER_CONFIG"

SYNC_CONTEXT_KEY = "dedicata_keycloak_env_sync"
MANAGED_PROVIDER_FIELDS = {
    "name",
    "flow",
    "enabled",
    "client_id",
    "client_secret",
    "scope",
    "token_map",
    "body",
    "css_class",
    "auth_endpoint",
    "token_endpoint",
    "jwks_uri",
    "end_session_endpoint",
}

FALSE_VALUES = {"0", "false", "no", "off"}


def _clean_url(value):
    return (value or "").strip().rstrip("/")


def _get_bool(value, default):
    if value is None or value == "":
        return default
    return value.strip().lower() not in FALSE_VALUES


def is_provider_config_locked():
    return _get_bool(os.getenv(ENV_LOCK_PROVIDER_CONFIG), True)


def _provider_values(env):
    issuer_url = _clean_url(os.getenv(ENV_ISSUER_URL))
    client_id = (os.getenv(ENV_CLIENT_ID) or "").strip()
    has_required_config = bool(issuer_url and client_id)
    enabled = (
        _get_bool(os.getenv(ENV_ENABLED), has_required_config) and has_required_config
    )

    values = {
        "name": (os.getenv(ENV_PROVIDER_NAME) or "Keycloak").strip(),
        "flow": "id_token_code",
        "enabled": enabled,
        "client_id": client_id,
        "client_secret": os.getenv(ENV_CLIENT_SECRET) or "",
        "scope": (os.getenv(ENV_SCOPE) or "openid email profile").strip(),
        "token_map": (os.getenv(ENV_TOKEN_MAP) or "sub:user_id email:email").strip(),
        "body": (os.getenv(ENV_LOGIN_LABEL) or "Login with Keycloak").strip(),
        "css_class": "fa fa-fw fa-key",
    }

    if issuer_url:
        values.update(
            {
                "auth_endpoint": f"{issuer_url}/protocol/openid-connect/auth",
                "token_endpoint": f"{issuer_url}/protocol/openid-connect/token",
                "jwks_uri": f"{issuer_url}/protocol/openid-connect/certs",
            }
        )
        if "end_session_endpoint" in env["auth.oauth.provider"]._fields:
            values[
                "end_session_endpoint"
            ] = f"{issuer_url}/protocol/openid-connect/logout"

    return values


def _xmlid_record(env):
    xmlid = (
        env["ir.model.data"]
        .sudo()
        .search(
            [
                ("module", "=", "dedicata_auth_oidc_keycloak"),
                ("name", "=", "provider_keycloak"),
                ("model", "=", "auth.oauth.provider"),
            ],
            limit=1,
        )
    )
    if not xmlid:
        return env["auth.oauth.provider"]
    return env["auth.oauth.provider"].sudo().browse(xmlid.res_id).exists()


def _ensure_xmlid(env, provider):
    if _xmlid_record(env):
        return
    env["ir.model.data"].sudo().create(
        {
            "module": "dedicata_auth_oidc_keycloak",
            "name": "provider_keycloak",
            "model": "auth.oauth.provider",
            "res_id": provider.id,
            "noupdate": True,
        }
    )


def sync_keycloak_provider(env):
    provider_model = env["auth.oauth.provider"].sudo()
    values = _provider_values(env)

    provider = _xmlid_record(env)
    if not provider:
        provider = provider_model.search([("name", "=", values["name"])], limit=1)

    if provider:
        provider.with_context(**{SYNC_CONTEXT_KEY: True}).write(values)
    else:
        if not _clean_url(os.getenv(ENV_ISSUER_URL)):
            _logger.info(
                "Keycloak OIDC provider not created: %s is not configured.",
                ENV_ISSUER_URL,
            )
            return
        provider = provider_model.with_context(**{SYNC_CONTEXT_KEY: True}).create(
            values
        )
    _ensure_xmlid(env, provider)

    if values["enabled"]:
        _logger.info("Keycloak OIDC provider synchronized from environment.")
    else:
        _logger.info(
            "Keycloak OIDC provider disabled: missing or disabled environment."
        )


def post_init_hook(env_or_cr, registry=None):
    if registry is None:
        sync_keycloak_provider(env_or_cr)
        return

    with api.Environment.manage():
        env = api.Environment(env_or_cr, api.SUPERUSER_ID, {})
        sync_keycloak_provider(env)
