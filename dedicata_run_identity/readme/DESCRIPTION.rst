Provision Odoo users from Dedicata Run and link them to the Keycloak OIDC
provider configured by ``dedicata_auth_oidc_keycloak``.

Exposes a lightweight REST controller (``/run-api/users``) that the Run
platform uses to create and archive users. The controller identifies users by
their Keycloak **username** (mapped to the Odoo ``login`` field) rather than
the OIDC ``sub`` UUID, and is secured with a shared Bearer token.
