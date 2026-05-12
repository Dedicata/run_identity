The module is configured through environment variables:

* ``DEDICATA_RUN_IDENTITY_BLOCK_OAUTH_AUTO_CREATE``: defaults to ``true``.
* ``DEDICATA_RUN_IDENTITY_DISABLE_PASSWORD_LOGIN``: defaults to ``true``.
* ``DEDICATA_RUN_IDENTITY_HIDE_PASSWORD_FORM``: defaults to ``true``.
* ``DEDICATA_RUN_IDENTITY_LOCAL_LOGIN_ALLOWLIST``: defaults to ``admin``.
* ``DEDICATA_RUN_IDENTITY_DEFAULT_GROUP_XMLIDS``: defaults to ``base.group_user``.
* ``DEDICATA_RUN_IDENTITY_LOCK_USER_IDENTITY``: defaults to ``true``.
* ``DEDICATA_RUN_API_SECRET``: shared secret for the ``/run-api`` HTTP
  controller (see *Usage*). **Required** to enable the REST endpoints — if
  unset the controller returns ``503``.
