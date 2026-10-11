"""
Unit tests for dedicata_run_identity invitation flow.
Tests run without a live Odoo instance using mocks.
"""

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

_ADDON_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _make_odoo_stubs():
    odoo = types.ModuleType("odoo")
    odoo_api = types.ModuleType("odoo.api")
    odoo_models = types.ModuleType("odoo.models")
    odoo_exceptions = types.ModuleType("odoo.exceptions")
    odoo_fields = types.ModuleType("odoo.fields")

    class UserError(Exception):
        pass

    class AccessError(Exception):
        pass

    class AccessDenied(Exception):
        pass

    odoo_exceptions.UserError = UserError
    odoo_exceptions.AccessError = AccessError
    odoo_exceptions.AccessDenied = AccessDenied

    class Model:
        pass

    odoo_models.Model = Model
    odoo_api.model = lambda fn: fn

    class _BooleanField:
        def __init__(self, *a, **kw):
            pass

    odoo_fields.Boolean = _BooleanField

    odoo.api = odoo_api
    odoo.models = odoo_models
    odoo.exceptions = odoo_exceptions
    odoo.fields = odoo_fields
    odoo._ = lambda s: s

    sys.modules.setdefault("odoo", odoo)
    sys.modules.setdefault("odoo.api", odoo_api)
    sys.modules.setdefault("odoo.models", odoo_models)
    sys.modules.setdefault("odoo.exceptions", odoo_exceptions)
    sys.modules.setdefault("odoo.fields", odoo_fields)


_make_odoo_stubs()

# Always resolve from sys.modules so pytest+conftest and direct run share the same class
UserError = sys.modules["odoo.exceptions"].UserError

_src = _ADDON_ROOT / "models" / "dedicata_run_identity.py"
_spec = importlib.util.spec_from_file_location("dedicata_run_identity_module", _src)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

DedicataRunIdentity = _mod.DedicataRunIdentity
payload_bool = _mod.payload_bool


def _translate(message, *args):
    return message % args if args else message


def _make_identity():
    obj = object.__new__(DedicataRunIdentity)
    obj.env = MagicMock()
    # The model formats its error messages with self.env._(): keep them readable.
    obj.env._ = _translate
    return obj


class TestNormalizePayload(unittest.TestCase):
    def setUp(self):
        self.identity = _make_identity()

    def test_full_payload(self):
        values = self.identity._normalize_payload(
            {"sub": "kc-sub-123", "email": "a@b.com", "name": "Alice"}
        )
        self.assertEqual(values["oauth_uid"], "kc-sub-123")
        self.assertEqual(values["email"], "a@b.com")
        self.assertEqual(values["login"], "a@b.com")
        self.assertEqual(values["name"], "Alice")

    def test_sub_optional(self):
        """Invite flow: no sub — must NOT raise."""
        values = self.identity._normalize_payload(
            {"email": "invite@b.com", "name": "Bob"}
        )
        self.assertEqual(values["oauth_uid"], "")
        self.assertEqual(values["email"], "invite@b.com")

    def test_email_required(self):
        with self.assertRaises(UserError) as ctx:
            self.identity._normalize_payload({"sub": "kc-123", "name": "Alice"})
        self.assertIn("email", str(ctx.exception))

    def test_name_required(self):
        with self.assertRaises(UserError) as ctx:
            self.identity._normalize_payload({"sub": "kc-123", "email": "a@b.com"})
        self.assertIn("name", str(ctx.exception))

    def test_login_defaults_to_email(self):
        values = self.identity._normalize_payload({"email": "u@b.com", "name": "U"})
        self.assertEqual(values["login"], "u@b.com")

    def test_custom_login(self):
        values = self.identity._normalize_payload(
            {"sub": "s", "email": "u@b.com", "name": "U", "login": "mylogin"}
        )
        self.assertEqual(values["login"], "mylogin")

    def test_oauth_uid_alias(self):
        values = self.identity._normalize_payload(
            {"oauth_uid": "alias-sub", "email": "a@b.com", "name": "A"}
        )
        self.assertEqual(values["oauth_uid"], "alias-sub")


class TestFindUser(unittest.TestCase):
    def _users_mock(self, *search_returns):
        Users = MagicMock()
        Users.search.side_effect = list(search_returns)
        identity = _make_identity()
        users_model = identity.env.__getitem__.return_value.sudo.return_value
        users_model.with_context.return_value = Users
        return identity, Users

    def test_find_by_oauth_uid(self):
        found = MagicMock()
        identity, Users = self._users_mock(found)

        provider = MagicMock()
        provider.id = 1
        values = {"oauth_uid": "kc-sub", "login": "a@b.com", "email": "a@b.com"}

        result = identity._find_user(provider, values)

        self.assertEqual(result, found)
        Users.search.assert_called_once_with(
            [("oauth_provider_id", "=", 1), ("oauth_uid", "=", "kc-sub")],
            limit=1,
        )

    def test_skip_oauth_uid_when_empty(self):
        """No sub → skip oauth_uid search, go to login search."""
        login_user = MagicMock()
        identity, Users = self._users_mock(login_user)

        provider = MagicMock()
        values = {"oauth_uid": "", "login": "invite@b.com", "email": "invite@b.com"}

        result = identity._find_user(provider, values)

        self.assertEqual(result, login_user)
        self.assertEqual(Users.search.call_count, 1)
        Users.search.assert_called_once_with([("login", "=", "invite@b.com")], limit=1)

    def test_fallback_to_email(self):
        empty = MagicMock()
        empty.__bool__ = lambda s: False
        email_user = MagicMock()
        identity, Users = self._users_mock(empty, email_user)

        provider = MagicMock()
        values = {"oauth_uid": "", "login": "u@b.com", "email": "u@b.com"}

        result = identity._find_user(provider, values)
        self.assertEqual(result, email_user)


class TestUpsertUserInviteFlow(unittest.TestCase):
    def _setup(self, existing_user=None):
        identity = _make_identity()
        provider = MagicMock()
        provider.id = 99

        identity._keycloak_provider = MagicMock(return_value=provider)
        identity._default_group_ids = MagicMock(return_value=[])
        identity._users_group_field = MagicMock(return_value="groups_id")
        identity._find_user = MagicMock(return_value=existing_user)

        Users = MagicMock()
        users_model = identity.env.__getitem__.return_value.sudo.return_value
        users_model.with_context.return_value = Users

        return identity, provider, Users

    def test_create_without_sub(self):
        identity, provider, Users = self._setup(existing_user=None)
        new_user = MagicMock()
        new_user.id = 42
        new_user.login = "invite@b.com"
        new_user.email = "invite@b.com"
        new_user.oauth_uid = ""
        Users.create.return_value = new_user

        result = identity.upsert_user({"email": "invite@b.com", "name": "Bob"})

        self.assertTrue(result["created"])
        self.assertFalse(result["updated"])
        self.assertTrue(Users.create.called)

    def test_update_sets_sub_after_invite(self):
        """User exists without sub → upsert with sub writes oauth_uid."""
        existing = MagicMock()
        existing.id = 42
        existing.login = "invite@b.com"
        existing.email = "invite@b.com"
        existing.oauth_uid = ""
        existing.oauth_provider_id = None

        identity, provider, Users = self._setup(existing_user=existing)

        with patch.object(
            identity,
            "_normalize_payload",
            return_value={
                "name": "Bob",
                "login": "invite@b.com",
                "email": "invite@b.com",
                "oauth_uid": "kc-real-sub",
                "active": True,
                "dedicata_run_managed": True,
                "oauth_provider_id": provider.id,
            },
        ):
            result = identity.upsert_user(
                {"sub": "kc-real-sub", "email": "invite@b.com", "name": "Bob"}
            )

        self.assertTrue(result["updated"])
        written = existing.with_context.return_value.write.call_args[0][0]
        self.assertEqual(written["oauth_uid"], "kc-real-sub")

    def test_no_overwrite_sub_with_empty(self):
        """upsert without sub must NOT clear existing oauth_uid."""
        existing = MagicMock()
        existing.id = 7
        existing.login = "u@b.com"
        existing.email = "u@b.com"
        existing.oauth_uid = "existing-sub"
        existing.oauth_provider_id = None

        identity, provider, Users = self._setup(existing_user=existing)

        with patch.object(
            identity,
            "_normalize_payload",
            return_value={
                "name": "U",
                "login": "u@b.com",
                "email": "u@b.com",
                "oauth_uid": "",
                "active": True,
                "dedicata_run_managed": True,
                "oauth_provider_id": provider.id,
            },
        ):
            identity.upsert_user({"email": "u@b.com", "name": "U"})

        written = existing.with_context.return_value.write.call_args[0][0]
        self.assertNotIn("oauth_uid", written)

    def test_conflict_different_subs_raises(self):
        existing = MagicMock()
        existing.oauth_uid = "sub-A"
        existing.oauth_provider_id = None

        identity, provider, Users = self._setup(existing_user=existing)

        with patch.object(
            identity,
            "_normalize_payload",
            return_value={
                "name": "U",
                "login": "u@b.com",
                "email": "u@b.com",
                "oauth_uid": "sub-B",
                "active": True,
                "dedicata_run_managed": True,
                "oauth_provider_id": provider.id,
            },
        ):
            with self.assertRaises(UserError):
                identity.upsert_user({"sub": "sub-B", "email": "u@b.com", "name": "U"})


class TestPayloadBool(unittest.TestCase):
    def test_none_returns_default(self):
        self.assertTrue(payload_bool(None, True))
        self.assertFalse(payload_bool(None, False))

    def test_false_strings(self):
        for s in ("0", "false", "no", "off", "FALSE", "No"):
            self.assertFalse(payload_bool(s, True), msg=f"expected False for {s!r}")

    def test_truthy_strings(self):
        for s in ("1", "true", "yes", "on"):
            self.assertTrue(payload_bool(s, False), msg=f"expected True for {s!r}")


if __name__ == "__main__":
    unittest.main()
