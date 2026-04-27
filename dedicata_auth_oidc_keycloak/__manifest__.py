{
    "name": "Dedicata Keycloak OIDC Authentication",
    "summary": "Configure the default Keycloak OIDC provider from environment variables",
    "version": "@@ODOO_MODULE_VERSION@@",
    "category": "Tools",
    "license": "AGPL-3",
    "author": "Dedicata",
    "website": "https://github.com/dedicata/odoo",
    "depends": ["auth_oidc"],
    "data": [],
    "installable": True,
    "auto_install": [],
    "post_init_hook": "post_init_hook",
}
