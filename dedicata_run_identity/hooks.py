import logging


_logger = logging.getLogger(__name__)

ADMIN_XMLID = "base.user_admin"


def post_init_hook(env):
    """Grant local-login bypass to the built-in admin user after installation.

    Odoo's database manager creates the admin user with ``login`` set to
    whatever e-mail address the operator typed in the creation form.  Because
    the Run platform assigns a unique e-mail per instance, the login will never
    be a static string like ``admin``.

    Instead of normalising the login (which would change a meaningful value),
    we set the ``dedicata_run_local_login_allowed`` flag on ``base.user_admin``.
    This flag is checked by ``should_disable_password_login`` before any
    allowlist look-up, so the admin can always authenticate with a local
    password regardless of the login format or SSO enforcement policy.

    The ``login`` and ``email`` fields are intentionally left untouched.
    """
    admin_user = env.ref(ADMIN_XMLID, raise_if_not_found=False)
    if not admin_user:
        _logger.warning(
            "dedicata_run_identity: post_init_hook could not find %s – "
            "skipping local-login flag setup.",
            ADMIN_XMLID,
        )
        return

    if admin_user.dedicata_run_local_login_allowed:
        _logger.debug(
            "dedicata_run_identity: admin user already has local-login flag, nothing to do."
        )
        return

    _logger.info(
        "dedicata_run_identity: granting local-login bypass to admin user (login=%s).",
        admin_user.login,
    )
    # Use the sync context key so the write() guard in res.users does not
    # interfere (the module is being installed right now but we stay safe
    # for any future Odoo version that might run the hook after the ORM is
    # fully loaded).
    admin_user.sudo().with_context(dedicata_run_identity_sync=True).write(
        {"dedicata_run_local_login_allowed": True}
    )
