Usage
=====

Dedicata Run provisions users through the ``/run-api`` REST controller exposed
by this module. The controller identifies users by their Keycloak **username**
(stored as the Odoo ``login`` field).

REST API (``/run-api``)
-----------------------

All requests require the header::

    Authorization: Bearer <DEDICATA_RUN_API_SECRET>

If the secret is wrong or missing the endpoint returns ``401``. If
``DEDICATA_RUN_API_SECRET`` is not set at all the endpoint returns ``503``.

Create or update a user
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    curl -X POST http://localhost:18069/run-api/users \
      -H "Authorization: Bearer <secret>" \
      -H "Content-Type: application/json" \
      -d '{
        "username": "joao.silva",
        "email": "joao.silva@example.com",
        "name": "João Silva"
      }'

Request body fields:

* ``username`` (**required**): Keycloak username — stored as Odoo ``login``.
* ``email`` (**required**): user e-mail address.
* ``name`` (**required**): display name.
* ``active``: defaults to ``true``.
* ``lang``: Odoo language code (e.g. ``pt_BR``).
* ``tz``: Odoo timezone (e.g. ``America/Sao_Paulo``).
* ``local_login_allowed``: grant password-login bypass for SSO enforcement.

Response on **create** (HTTP ``201``):

.. code-block:: json

    {
      "user_id": 5,
      "login": "joao.silva",
      "email": "joao.silva@example.com",
      "oauth_uid": null,
      "created": true,
      "updated": false
    }

Response on **update** (HTTP ``200``):

.. code-block:: json

    {
      "user_id": 5,
      "login": "joao.silva",
      "email": "joao.silva@example.com",
      "oauth_uid": null,
      "created": false,
      "updated": true
    }

The ``oauth_uid`` field will be populated automatically the first time the
user authenticates via Keycloak SSO.

Archive a user
~~~~~~~~~~~~~~

.. code-block:: bash

    curl -X DELETE http://localhost:18069/run-api/users/joao.silva \
      -H "Authorization: Bearer <secret>"

The user is **archived** (``active = false``), not deleted. Response (HTTP
``200``):

.. code-block:: json

    {
      "user_id": 5,
      "login": "joao.silva",
      "email": "joao.silva@example.com",
      "archived": true
    }

If the username is not found the endpoint returns ``404``.

Error responses
~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Status
     - Body
     - Cause
   * - ``400``
     - ``{"error": "<message>"}``
     - Missing required field or invalid payload.
   * - ``401``
     - ``{"error": "unauthorized"}``
     - Bearer token missing or incorrect.
   * - ``404``
     - ``{"error": "user not found"}``
     - Username not found (DELETE only).
   * - ``503``
     - ``{"error": "api not configured"}``
     - ``DEDICATA_RUN_API_SECRET`` is not set.

Matching rules (upsert)
-----------------------

When processing a ``POST`` the module searches for an existing user in this
order:

1. Matching Odoo ``login`` (Keycloak username).
2. Matching Odoo ``email``.

If an existing user is already linked to a different OAuth provider an error
is raised.

On create, the user receives the groups from
``DEDICATA_RUN_IDENTITY_DEFAULT_GROUP_XMLIDS`` (default: ``base.group_user``).
On update, groups and companies are not overwritten, so manual permission
changes made by an Odoo administrator are preserved.

JSON-RPC (legacy)
-----------------

The model methods ``upsert_user``, ``deactivate_user``, and ``get_user`` remain
available through Odoo's standard JSON-RPC endpoint for backward compatibility.

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
          "args": ["my_odoo_db", "admin", "admin-or-api-key", {}]
        },
        "id": 1
      }'

Call ``upsert_user`` (note: JSON-RPC still accepts ``sub``):

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
            "my_odoo_db", 2, "admin-or-api-key",
            "dedicata.run.identity", "upsert_user",
            [{"email": "run.user@example.com", "name": "Run User"}]
          ]
        },
        "id": 2
      }'

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
