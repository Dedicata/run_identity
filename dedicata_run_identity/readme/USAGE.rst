Usage
=====

Dedicata Run should call the native Odoo JSON-RPC API on model
``dedicata.run.identity``.

Minimal user creation payload::

    {
        "sub": "keycloak-subject",
        "email": "user@example.com",
        "name": "User Name"
    }
