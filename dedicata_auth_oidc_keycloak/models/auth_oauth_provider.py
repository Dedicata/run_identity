from odoo import models

from ..hooks import sync_keycloak_provider


class AuthOauthProvider(models.Model):
    _inherit = "auth.oauth.provider"

    def _register_hook(self):
        result = super()._register_hook()
        sync_keycloak_provider(self.env)
        return result
