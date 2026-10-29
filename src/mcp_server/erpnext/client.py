"""Token-authenticated GET-only transport. No arbitrary paths or write methods."""
import json
from urllib.parse import quote, urlsplit
import httpx
from .models import ERPNextSettings

DOCTYPES = frozenset({"Supplier", "Item", "Warehouse", "Bin", "Purchase Order"})

class ERPNextError(RuntimeError):
    def __init__(self, code: str, status: int | None = None):
        self.code, self.status = code, status
        super().__init__(f"ERPNext {code}" + (f" (HTTP {status})" if status else ""))

class ERPNextClient:
    def __init__(self, settings: ERPNextSettings, *, transport=None):
        self.settings = settings
        self.transport = transport
        self._http = None

    async def __aenter__(self):
        s = self.settings
        url = urlsplit(s.base_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
            raise ERPNextError("invalid_base_url")
        if not (s.api_key.get_secret_value() and s.api_secret.get_secret_value() and s.api_user and s.company and s.warehouses):
            raise ERPNextError("configuration_required")
        if s.api_user.lower() in {"administrator", "guest"}:
            raise ERPNextError("least_privilege_user_required")
        if url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}:
            raise ERPNextError("https_required")
        self._http = httpx.AsyncClient(base_url=s.base_url, timeout=s.timeout, follow_redirects=False,
            trust_env=False, transport=self.transport,
            headers={"Authorization": f"token {s.api_key.get_secret_value()}:{s.api_secret.get_secret_value()}"})
        try:
            identity = await self._get("/api/method/frappe.auth.get_logged_user")
            if identity.get("message") != s.api_user:
                raise ERPNextError("identity_mismatch")
        except BaseException:
            await self._http.aclose()
            raise
        return self

    async def __aexit__(self, *_):
        await self._http.aclose()

    async def _get(self, path, params=None):
        if self._http is None:
            raise ERPNextError("client_not_open")
        try:
            response = await self._http.get(path, params=params)
        except httpx.TimeoutException:
            raise ERPNextError("timeout") from None
        except httpx.RequestError:
            raise ERPNextError("connection_failed") from None
        if response.status_code != 200:
            # Never forward Frappe stack traces, cookies, headers or raw error bodies.
            code = {401: "authentication_failed", 403: "permission_denied", 404: "not_found", 429: "rate_limited"}.get(response.status_code, "http_error")
            raise ERPNextError(code, response.status_code)
        try:
            body = response.json()
        except ValueError:
            raise ERPNextError("invalid_json") from None
        if not isinstance(body, dict) or any(body.get(k) for k in ("exc", "exception", "exc_type")):
            raise ERPNextError("erp_error")
        return body

    async def list_documents(self, doctype, *, fields, filters, limit, offset=0):
        if doctype not in DOCTYPES:
            raise ERPNextError("doctype_denied")
        body = await self._get(f"/api/resource/{quote(doctype, safe='')}", {
            "fields": json.dumps(fields), "filters": json.dumps(filters), "order_by": "name asc",
            "limit_page_length": limit, "limit_start": offset,
        })
        if not isinstance(body.get("data"), list):
            raise ERPNextError("invalid_payload")
        return body["data"]
