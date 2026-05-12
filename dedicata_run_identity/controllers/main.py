import hmac
import json
import logging
import os

from odoo import SUPERUSER_ID, http
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ENV_API_SECRET = "DEDICATA_RUN_API_SECRET"


def _json_response(data, status=200):
    return http.Response(
        json.dumps(data),
        status=status,
        content_type="application/json",
    )


def _authenticate(request):
    secret = os.getenv(ENV_API_SECRET, "").strip()
    if not secret:
        return _json_response({"error": "api not configured"}, status=503)

    auth_header = request.httprequest.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return _json_response({"error": "unauthorized"}, status=401)

    token = auth_header[len("Bearer ") :]
    if not hmac.compare_digest(token.encode(), secret.encode()):
        return _json_response({"error": "unauthorized"}, status=401)

    return None


class RunApiController(http.Controller):
    @http.route(
        "/run-api/users",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        readonly=False,
    )
    def upsert_user(self, **_kwargs):
        error = _authenticate(http.request)
        if error:
            return error

        try:
            body = json.loads(http.request.httprequest.data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return _json_response({"error": "invalid json body"}, status=400)

        username = (body.get("username") or "").strip()
        if not username:
            return _json_response({"error": "username is required"}, status=400)

        payload = {
            "login": username,
            "email": body.get("email"),
            "name": body.get("name"),
        }
        for optional in ("active", "lang", "tz", "local_login_allowed"):
            if optional in body:
                payload[optional] = body[optional]

        try:
            env = http.request.env(user=SUPERUSER_ID)
            result = env["dedicata.run.identity"].upsert_user(payload)
        except UserError as exc:
            return _json_response({"error": str(exc)}, status=400)
        except Exception:
            _logger.exception("run-api: unexpected error in upsert_user")
            return _json_response({"error": "internal error"}, status=500)

        status = 201 if result.get("created") else 200
        return _json_response(result, status=status)

    @http.route(
        "/run-api/users/<username>",
        type="http",
        auth="none",
        methods=["DELETE"],
        csrf=False,
        readonly=False,
    )
    def archive_user(self, username, **_kwargs):
        error = _authenticate(http.request)
        if error:
            return error

        username = (username or "").strip()
        if not username:
            return _json_response({"error": "username is required"}, status=400)

        try:
            env = http.request.env(user=SUPERUSER_ID)
            result = env["dedicata.run.identity"].archive_user_by_login(username)
        except Exception:
            _logger.exception("run-api: unexpected error in archive_user")
            return _json_response({"error": "internal error"}, status=500)

        if result is None:
            return _json_response({"error": "user not found"}, status=404)

        return _json_response(result, status=200)
