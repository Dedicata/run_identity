from odoo import _, fields, models
from odoo.exceptions import AccessDenied, AccessError

from .dedicata_run_identity import (
    MANAGED_USER_FIELDS,
    RUN_SYNC_CONTEXT_KEY,
)


class ResUsers(models.Model):
    _inherit = "res.users"

    dedicata_run_managed = fields.Boolean(
        string="Dedicata Run Managed",
        copy=False,
        readonly=True,
    )

    dedicata_run_local_login_allowed = fields.Boolean(
        string="Dedicata Run: Local Login Allowed",
        copy=False,
        help=(
            "When enabled, this user can always authenticate with a local "
            "password even when SSO enforcement is active. Grant this flag "
            "to the instance master user so it is never locked out."
        ),
    )

    def _auth_oauth_signin(self, provider, validation, params):
        identity = self.env["dedicata.run.identity"].sudo()
        if identity.should_block_oauth_auto_create(provider):
            return super(
                ResUsers,
                self.with_context(no_user_creation=True),
            )._auth_oauth_signin(provider, validation, params)
        return super()._auth_oauth_signin(provider, validation, params)

    def _dedicata_login_from_credentials(self, args):
        if not args:
            return self.login
        credential = args[0]
        if isinstance(credential, dict):
            return credential.get("login") or self.login
        return self.login

    def _dedicata_is_interactive_credentials(self, args):
        if len(args) < 2 or not isinstance(args[1], dict):
            return True
        return bool(args[1].get("interactive", True))

    def _dedicata_is_oauth_token_credentials(self, args):
        if not args:
            return False
        credential = args[0]
        if isinstance(credential, dict):
            return credential.get("type") == "oauth_token"
        return bool(self.sudo().oauth_access_token and credential == self.sudo().oauth_access_token)

    def _check_credentials(self, *args, **kwargs):
        if not self._dedicata_is_oauth_token_credentials(args):
            login = self._dedicata_login_from_credentials(args)
            interactive = self._dedicata_is_interactive_credentials(args)
            if self.env["dedicata.run.identity"].sudo().should_disable_password_login(
                login,
                interactive=interactive,
            ):
                raise AccessDenied()
        return super()._check_credentials(*args, **kwargs)

    def write(self, vals):
        if (
            vals
            and MANAGED_USER_FIELDS.intersection(vals)
            and not self.env.context.get(RUN_SYNC_CONTEXT_KEY)
            and self.env["dedicata.run.identity"].sudo().is_user_identity_locked()
            and any(self.sudo().mapped("dedicata_run_managed"))
        ):
            raise AccessError(_("Dedicata Run manages identity fields for this user."))
        return super().write(vals)
