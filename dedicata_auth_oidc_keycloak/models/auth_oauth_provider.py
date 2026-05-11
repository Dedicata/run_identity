from odoo import _, models
from odoo.exceptions import AccessError

from ..hooks import (
    MANAGED_PROVIDER_FIELDS,
    PROVIDER_XMLID,
    SYNC_CONTEXT_KEY,
    is_provider_config_locked,
    sync_keycloak_provider,
)


class AuthOauthProvider(models.Model):
    _inherit = "auth.oauth.provider"

    def _register_hook(self):
        result = super()._register_hook()
        sync_keycloak_provider(self.env)
        return result

    def _is_dedicata_keycloak_provider(self):
        provider = self.env.ref(PROVIDER_XMLID, raise_if_not_found=False)
        return bool(provider and (self & provider))

    def write(self, vals):
        if (
            vals
            and is_provider_config_locked()
            and not self.env.context.get(SYNC_CONTEXT_KEY)
            and MANAGED_PROVIDER_FIELDS.intersection(vals)
            and self._is_dedicata_keycloak_provider()
        ):
            raise AccessError(
                _("The Dedicata Keycloak provider is managed by environment variables.")
            )
        return super().write(vals)

    def unlink(self):
        if (
            is_provider_config_locked()
            and not self.env.context.get(SYNC_CONTEXT_KEY)
            and self._is_dedicata_keycloak_provider()
        ):
            raise AccessError(
                _("The Dedicata Keycloak provider is managed by environment variables.")
            )
        return super().unlink()
