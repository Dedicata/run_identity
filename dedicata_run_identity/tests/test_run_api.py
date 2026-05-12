"""
Unit tests for the Run API controller and related model changes.
Runs without a live Odoo instance using stubs and mocks.
"""

import importlib.util
import json
import os
import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

_ADDON_ROOT = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Odoo stubs (same pattern as test_run_identity_invite.py)
# ---------------------------------------------------------------------------


def _make_odoo_stubs():
    odoo = types.ModuleType("odoo")
    odoo_api = types.ModuleType("odoo.api")
    odoo_models = types.ModuleType("odoo.models")
    odoo_exceptions = types.ModuleType("odoo.exceptions")
    odoo_fields = types.ModuleType("odoo.fields")
    odoo_http = types.ModuleType("odoo.http")

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

    # http stubs
    class _Controller:
        pass

    class _Response:
        def __init__(self, body, status=200, content_type="application/json"):
            self.data = body
            self.status_code = status
            self.content_type = content_type

    def _route(*a, **kw):
        return lambda fn: fn

    odoo_http.Controller = _Controller
    odoo_http.Response = _Response
    odoo_http.route = _route
    odoo_http.request = None  # replaced per-test

    odoo.api = odoo_api
    odoo.models = odoo_models
    odoo.exceptions = odoo_exceptions
    odoo.fields = odoo_fields
    odoo.http = odoo_http
    odoo._ = lambda s: s
    odoo.SUPERUSER_ID = 1

    for name, mod in [
        ("odoo", odoo),
        ("odoo.api", odoo_api),
        ("odoo.models", odoo_models),
        ("odoo.exceptions", odoo_exceptions),
        ("odoo.fields", odoo_fields),
        ("odoo.http", odoo_http),
    ]:
        sys.modules.setdefault(name, mod)

    return


_make_odoo_stubs()

# Always resolve from sys.modules so pytest+conftest and direct run share the same class
UserError = sys.modules["odoo.exceptions"].UserError
AccessError = sys.modules["odoo.exceptions"].AccessError
_Response = sys.modules["odoo.http"].Response


# ---------------------------------------------------------------------------
# Load modules under test
# ---------------------------------------------------------------------------


def _load(rel_path):
    src = _ADDON_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(str(rel_path).replace("/", "."), src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_model_mod = _load("models/dedicata_run_identity.py")
DedicataRunIdentity = _model_mod.DedicataRunIdentity
RUN_SYNC_CONTEXT_KEY = _model_mod.RUN_SYNC_CONTEXT_KEY

_ctrl_mod = _load("controllers/main.py")
_authenticate = _ctrl_mod._authenticate
_json_response = _ctrl_mod._json_response
RunApiController = _ctrl_mod.RunApiController
ENV_API_SECRET = _ctrl_mod.ENV_API_SECRET


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_identity():
    obj = object.__new__(DedicataRunIdentity)
    obj.env = MagicMock()
    return obj


def _make_request(method="POST", body=None, auth_header=None, path="/run-api/users"):
    req = MagicMock()
    req.httprequest.method = method
    req.httprequest.data = json.dumps(body or {}).encode()
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header
    req.httprequest.headers = headers
    req.env = MagicMock()
    return req


# ---------------------------------------------------------------------------
# Model: _normalize_payload — username alias
# ---------------------------------------------------------------------------


class TestNormalizePayloadUsername(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.identity = _make_identity()

    def test_username_used_as_login(self):
        values = self.identity._normalize_payload(
            {"username": "joao.silva", "email": "joao@example.com", "name": "João"}
        )
        self.assertEqual(values["login"], "joao.silva")

    def test_login_takes_precedence_over_username(self):
        values = self.identity._normalize_payload(
            {
                "username": "joao",
                "login": "joao.silva",
                "email": "joao@example.com",
                "name": "João",
            }
        )
        self.assertEqual(values["login"], "joao.silva")

    def test_fallback_to_email_when_no_username_or_login(self):
        values = self.identity._normalize_payload(
            {"email": "joao@example.com", "name": "João"}
        )
        self.assertEqual(values["login"], "joao@example.com")

    def test_username_does_not_set_oauth_uid(self):
        values = self.identity._normalize_payload(
            {"username": "joao.silva", "email": "joao@example.com", "name": "João"}
        )
        self.assertEqual(values["oauth_uid"], "")

    def test_existing_sub_still_sets_oauth_uid(self):
        values = self.identity._normalize_payload(
            {
                "username": "joao.silva",
                "sub": "kc-uuid-123",
                "email": "joao@example.com",
                "name": "João",
            }
        )
        self.assertEqual(values["oauth_uid"], "kc-uuid-123")
        self.assertEqual(values["login"], "joao.silva")


# ---------------------------------------------------------------------------
# Model: archive_user_by_login
# ---------------------------------------------------------------------------


class TestArchiveUserByLogin(unittest.TestCase):
    def _users_mock(self, found=None):
        identity = _make_identity()
        Users = MagicMock()
        Users.search.return_value = found
        chain = identity.env.__getitem__.return_value.sudo.return_value
        chain.with_context.return_value = Users
        return identity, Users

    def test_returns_none_when_not_found(self):
        not_found = MagicMock()
        not_found.__bool__ = lambda s: False
        identity, _ = self._users_mock(found=not_found)
        result = identity.archive_user_by_login("ghost")
        self.assertIsNone(result)

    def test_archives_user_and_returns_dict(self):
        user = MagicMock()
        user.id = 5
        user.login = "joao.silva"
        user.email = "joao@example.com"
        user.__bool__ = lambda s: True
        identity, Users = self._users_mock(found=user)

        result = identity.archive_user_by_login("joao.silva")

        self.assertIsNotNone(result)
        self.assertEqual(result["user_id"], 5)
        self.assertEqual(result["login"], "joao.silva")
        self.assertTrue(result["archived"])

    def test_write_called_with_active_false(self):
        user = MagicMock()
        user.__bool__ = lambda s: True
        identity, Users = self._users_mock(found=user)

        identity.archive_user_by_login("joao.silva")

        user.with_context.assert_called_once_with(**{RUN_SYNC_CONTEXT_KEY: True})
        user.with_context.return_value.write.assert_called_once_with({"active": False})

    def test_search_uses_active_test_false(self):
        not_found = MagicMock()
        not_found.__bool__ = lambda s: False
        identity, Users = self._users_mock(found=not_found)

        identity.archive_user_by_login("joao.silva")

        # with_context(active_test=False) must be applied before search
        identity.env.__getitem__.return_value.sudo.return_value.with_context.assert_called_once_with(
            active_test=False
        )


# ---------------------------------------------------------------------------
# Controller: _authenticate
# ---------------------------------------------------------------------------


class TestAuthenticate(unittest.TestCase):
    def _req(self, auth_header=None):
        req = MagicMock()
        req.httprequest.headers = {"Authorization": auth_header} if auth_header else {}
        return req

    def test_no_secret_configured_returns_503(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop(ENV_API_SECRET, None)
            resp = _authenticate(self._req("Bearer anything"))
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 503)
        self.assertIn("not configured", resp.data)

    def test_missing_auth_header_returns_401(self):
        with patch.dict(os.environ, {ENV_API_SECRET: "mysecret"}):
            resp = _authenticate(self._req())
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 401)

    def test_wrong_token_returns_401(self):
        with patch.dict(os.environ, {ENV_API_SECRET: "mysecret"}):
            resp = _authenticate(self._req("Bearer wrongtoken"))
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 401)

    def test_correct_token_returns_none(self):
        with patch.dict(os.environ, {ENV_API_SECRET: "mysecret"}):
            resp = _authenticate(self._req("Bearer mysecret"))
        self.assertIsNone(resp)

    def test_header_without_bearer_prefix_returns_401(self):
        with patch.dict(os.environ, {ENV_API_SECRET: "mysecret"}):
            resp = _authenticate(self._req("mysecret"))
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 401)


# ---------------------------------------------------------------------------
# Controller: POST /run-api/users
# ---------------------------------------------------------------------------


class TestUpsertEndpoint(unittest.TestCase):
    def _call(self, body, secret="mysecret", env_secret="mysecret"):
        ctrl = object.__new__(RunApiController)
        req = _make_request(body=body, auth_header=f"Bearer {secret}")
        with patch.dict(os.environ, {ENV_API_SECRET: env_secret}):
            with patch.object(_ctrl_mod, "http") as mock_http:
                mock_http.request = req
                mock_http.Response = _Response
                req.env.return_value.__getitem__.return_value = MagicMock()
                with patch.dict(os.environ, {ENV_API_SECRET: env_secret}):
                    return ctrl.upsert_user()

    def _call_with_identity(self, body, identity_result, secret="s", env_secret="s"):
        ctrl = object.__new__(RunApiController)
        req = _make_request(body=body, auth_header=f"Bearer {secret}")
        env_mock = MagicMock()
        env_mock.__getitem__.return_value = MagicMock()
        env_mock.__getitem__.return_value.upsert_user.return_value = identity_result

        with patch.dict(os.environ, {ENV_API_SECRET: env_secret}):
            with patch.object(_ctrl_mod, "http") as mock_http:
                mock_http.request = req
                mock_http.Response = _Response
                req.env.return_value = env_mock
                return ctrl.upsert_user()

    def test_missing_username_returns_400(self):
        resp = self._call_with_identity(
            body={"email": "a@b.com", "name": "A"},
            identity_result={"created": True},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("username", resp.data)

    def test_created_returns_201(self):
        result = {
            "user_id": 5,
            "login": "joao.silva",
            "email": "a@b.com",
            "created": True,
            "updated": False,
        }
        resp = self._call_with_identity(
            body={"username": "joao.silva", "email": "a@b.com", "name": "João"},
            identity_result=result,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn("joao.silva", resp.data)

    def test_updated_returns_200(self):
        result = {
            "user_id": 5,
            "login": "joao.silva",
            "email": "a@b.com",
            "created": False,
            "updated": True,
        }
        resp = self._call_with_identity(
            body={"username": "joao.silva", "email": "a@b.com", "name": "João"},
            identity_result=result,
        )
        self.assertEqual(resp.status_code, 200)

    def test_invalid_json_returns_400(self):
        ctrl = object.__new__(RunApiController)
        req = MagicMock()
        req.httprequest.data = b"not-json{{{{"
        req.httprequest.headers = {"Authorization": "Bearer s"}
        with patch.dict(os.environ, {ENV_API_SECRET: "s"}):
            with patch.object(_ctrl_mod, "http") as mock_http:
                mock_http.request = req
                mock_http.Response = _Response
                resp = ctrl.upsert_user()
        self.assertEqual(resp.status_code, 400)

    def test_user_error_returns_400(self):
        ctrl = object.__new__(RunApiController)
        req = _make_request(
            body={"username": "u", "email": "u@b.com", "name": "U"},
            auth_header="Bearer s",
        )
        env_mock = MagicMock()
        env_mock.__getitem__.return_value.upsert_user.side_effect = UserError(
            "bad payload"
        )

        with patch.dict(os.environ, {ENV_API_SECRET: "s"}):
            with patch.object(_ctrl_mod, "http") as mock_http:
                mock_http.request = req
                mock_http.Response = _Response
                req.env.return_value = env_mock
                resp = ctrl.upsert_user()
        self.assertEqual(resp.status_code, 400)
        self.assertIn("bad payload", resp.data)


# ---------------------------------------------------------------------------
# Controller: DELETE /run-api/users/<username>
# ---------------------------------------------------------------------------


class TestArchiveEndpoint(unittest.TestCase):
    def _call(self, username, identity_result, secret="s", env_secret="s"):
        ctrl = object.__new__(RunApiController)
        req = _make_request(method="DELETE", auth_header=f"Bearer {secret}")
        env_mock = MagicMock()
        env_mock.__getitem__.return_value.archive_user_by_login.return_value = (
            identity_result
        )

        with patch.dict(os.environ, {ENV_API_SECRET: env_secret}):
            with patch.object(_ctrl_mod, "http") as mock_http:
                mock_http.request = req
                mock_http.Response = _Response
                req.env.return_value = env_mock
                return ctrl.archive_user(username)

    def test_found_returns_200(self):
        result = {
            "user_id": 5,
            "login": "joao.silva",
            "email": "a@b.com",
            "archived": True,
        }
        resp = self._call("joao.silva", identity_result=result)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("archived", resp.data)

    def test_not_found_returns_404(self):
        resp = self._call("ghost.user", identity_result=None)
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.data)

    def test_wrong_token_returns_401(self):
        resp = self._call(
            "joao.silva", identity_result={}, secret="wrong", env_secret="correct"
        )
        self.assertEqual(resp.status_code, 401)

    def test_empty_username_returns_400(self):
        resp = self._call("", identity_result={})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
