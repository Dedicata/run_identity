"""
Inject Odoo stubs before pytest collects any addon modules.
This allows standalone unit tests to run without a live Odoo installation.
"""

import sys
import types


def _inject_odoo_stubs():
    if "odoo" in sys.modules:
        return

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
    odoo_http.request = None

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
        sys.modules[name] = mod


_inject_odoo_stubs()
