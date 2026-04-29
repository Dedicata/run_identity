Usage
=====

Dedicata Run should provision users through Odoo's native external RPC API.
The module does not expose a custom HTTP controller. It exposes model methods
on ``dedicata.run.identity`` and those methods are called through the standard
Odoo RPC endpoints.

Authentication
--------------

Use a technical Odoo user that belongs to ``Settings / Administration``.
Authenticate with either the user's password or, preferably, an Odoo API key.

The API key is passed in the same RPC field normally named ``password``.

JSON-RPC endpoints
------------------

Authenticate and get the Odoo ``uid``:

.. code-block:: bash

    curl -s http://localhost:18069/jsonrpc \
      -H "Content-Type: application/json" \
      -d '{
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
          "service": "common",
          "method": "authenticate",
          "args": [
            "my_odoo_db",
            "admin",
            "admin-or-api-key",
            {}
          ]
        },
        "id": 1
      }'

Call ``upsert_user``:

.. code-block:: bash

    curl -s http://localhost:18069/jsonrpc \
      -H "Content-Type: application/json" \
      -d '{
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
          "service": "object",
          "method": "execute_kw",
          "args": [
            "my_odoo_db",
            2,
            "admin-or-api-key",
            "dedicata.run.identity",
            "upsert_user",
            [{
              "sub": "11111111-1111-1111-1111-111111111111",
              "email": "run.user@example.com",
              "name": "Run User"
            }]
          ]
        },
        "id": 2
      }'

The second argument in ``args`` is the ``uid`` returned by
``common.authenticate``.

Available methods
-----------------

``upsert_user(payload)``
~~~~~~~~~~~~~~~~~~~~~~~~

Creates or updates one Odoo user and links it to the configured Keycloak
provider.

Required payload fields:

* ``sub``: Keycloak subject. Stored as Odoo ``oauth_uid``.
* ``email``: user email.
* ``name``: user display name.

Optional payload fields:

* ``login``: Odoo login. Defaults to ``email``.
* ``active``: defaults to ``true``.
* ``lang``: Odoo language code.
* ``tz``: Odoo timezone.

Minimal payload:

.. code-block:: json

    {
      "sub": "11111111-1111-1111-1111-111111111111",
      "email": "run.user@example.com",
      "name": "Run User"
    }

Return example:

.. code-block:: json

    {
      "user_id": 5,
      "login": "run.user@example.com",
      "email": "run.user@example.com",
      "oauth_uid": "11111111-1111-1111-1111-111111111111",
      "created": true,
      "updated": false
    }

On create, the user receives the groups from
``DEDICATA_RUN_IDENTITY_DEFAULT_GROUP_XMLIDS``. The default is
``base.group_user``. On update, groups and companies are not overwritten, so
manual permission changes made by an Odoo administrator are preserved.

``deactivate_user(payload)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Deactivates the matching Odoo user.

Payload:

.. code-block:: json

    {
      "sub": "11111111-1111-1111-1111-111111111111"
    }

``get_user(payload)``
~~~~~~~~~~~~~~~~~~~~~

Returns the matching user data or ``false``.

Payload:

.. code-block:: json

    {
      "sub": "11111111-1111-1111-1111-111111111111"
    }

Matching rules
--------------

``upsert_user`` searches in this order:

* matching Keycloak provider plus ``oauth_uid``/``sub``;
* matching Odoo ``login``;
* matching Odoo ``email``.

If an existing user is already linked to another OAuth provider or another
OAuth subject, the method raises an error instead of relinking it silently.

Local Keycloak compose test
---------------------------

The repository includes a local Keycloak realm for development:

* Keycloak URL: ``http://keycloak.localhost:18080``
* Realm: ``dedicata-run``
* Client ID: ``odoo``
* Client secret: ``change-me``
* Test user: ``run.user@example.com``
* Test password: ``run-user``
* Test subject: ``11111111-1111-1111-1111-111111111111``
