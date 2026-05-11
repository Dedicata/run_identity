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

* ``email``: user email.
* ``name``: user display name.

Optional payload fields:

* ``sub`` (alias ``oauth_uid``): Keycloak subject. Stored as Odoo ``oauth_uid``.
  May be omitted when the Keycloak subject is not yet known (e.g. invitation
  flow — see below).
* ``login``: Odoo login. Defaults to ``email``.
* ``active``: defaults to ``true``.
* ``lang``: Odoo language code.
* ``tz``: Odoo timezone.

Minimal payload (full — user already has a Keycloak account):

.. code-block:: json

    {
      "sub": "11111111-1111-1111-1111-111111111111",
      "email": "run.user@example.com",
      "name": "Run User"
    }

Minimal payload (invite — Keycloak subject not yet known):

.. code-block:: json

    {
      "email": "invited@example.com",
      "name": "Invited User"
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

Invitation flow
^^^^^^^^^^^^^^^

When a user is provisioned before they have authenticated with Keycloak (for
example through an invitation), ``sub`` may be omitted:

1. Call ``upsert_user`` with only ``email`` and ``name``. The user is created
   without an ``oauth_uid``.
2. When the user later authenticates via Keycloak, call ``upsert_user`` again
   with ``sub``, ``email``, and ``name``. The existing user is found by email
   or login, and ``oauth_uid`` is set on that record.
3. Subsequent calls find the user directly by ``oauth_uid``.

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

1. Matching Keycloak provider plus ``oauth_uid``/``sub`` — only when ``sub``
   is present in the payload.
2. Matching Odoo ``login``.
3. Matching Odoo ``email``.

If an existing user is already linked to a different OAuth provider, the method
raises an error. If an existing user already has an ``oauth_uid`` and the
payload provides a *different* ``sub``, the method also raises an error.
Providing no ``sub`` (or an empty ``sub``) for a user that already has an
``oauth_uid`` is safe — the existing value is preserved.

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
