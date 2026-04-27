{
    "name": "Dedicata Run Identity Provisioning",
    "summary": "Provision Odoo users managed by Dedicata Run and Keycloak OIDC",
    "version": "@@ODOO_MODULE_VERSION@@",
    "category": "Tools",
    "license": "AGPL-3",
    "author": "Dedicata",
    "website": "https://github.com/dedicata/odoo",
    "depends": ["dedicata_auth_oidc_keycloak", "auth_oidc", "auth_oauth"],
    "data": [
        "security/ir.model.access.csv",
        "views/web_login_templates.xml",
    ],
    "installable": True,
    "auto_install": [],
}
