{
    "name": "Dedicata Run Identity Provisioning",
    "summary": "Provision Odoo users managed by Dedicata Run and Keycloak OIDC",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "license": "AGPL-3",
    "author": "Dedicata",
    "website": "https://github.com/dedicata/run_identity",
    "depends": ["dedicata_auth_oidc_keycloak", "auth_oidc", "auth_oauth"],
    "data": [
        "security/ir.model.access.csv",
        "views/web_login_templates.xml",
    ],
    "installable": True,
    "auto_install": [],
    "post_init_hook": "post_init_hook",
}
