import json
import httpx
import pytest
from fastmcp import Client
from unittest.mock import patch
from src.mcp_server.erpnext.models import ERPNextSettings, Query, BinQuery, PurchaseOrderQuery
from src.mcp_server.erpnext.client import ERPNextClient, ERPNextError
from src.mcp_server.erpnext.adapter import ERPNextAdapter
from src.mcp_server.server_main import mcp

pytestmark = pytest.mark.mock_erp

@pytest.fixture
def settings():
    return ERPNextSettings(api_key="test-key", api_secret="test-secret", api_user="reader@example.test",
                           company="Lighting Co", warehouses=["Finished - LC"])

ROWS = {
    "Supplier": {"name": "SUP-001", "supplier_name": "Lighting Supplier"},
    "Item": {"name": "LED-001", "item_code": "LED-001", "item_name": "台灯", "stock_uom": "Nos"},
    "Warehouse": {"name": "Finished - LC", "warehouse_name": "Finished", "company": "Lighting Co"},
    "Bin": {"company": "Lighting Co", "name": "bin-1", "item_code": "LED-001", "warehouse": "Finished - LC", "actual_qty": 12},
    "Purchase Order": {"name": "PUR-ORD-2026-00001", "company": "Lighting Co", "supplier": "SUP-001",
                       "transaction_date": "2026-10-30", "status": "To Receive and Bill", "docstatus": 1,
                       "currency": "CNY", "grand_total": "125.50"},
}

def responder(request):
    assert request.method == "GET"
    assert request.headers["Authorization"] == "token test-key:test-secret"
    if request.url.path.endswith("get_logged_user"):
        return httpx.Response(200, json={"message": "reader@example.test"})
    doctype = request.url.path.rsplit("/", 1)[1]
    return httpx.Response(200, json={"data": [ROWS[doctype]]})

@pytest.mark.parametrize("doctype,query", [(d, BinQuery() if d == "Bin" else PurchaseOrderQuery() if d == "Purchase Order" else Query()) for d in ROWS])
async def test_five_doctypes(settings, doctype, query):
    requests = []
    def handler(request):
        requests.append(request)
        return responder(request)
    async with ERPNextClient(settings, transport=httpx.MockTransport(handler)) as client:
        result = await ERPNextAdapter(client).query(doctype, query)
    assert len(result.data) == 1
    params = requests[-1].url.params
    filters = json.loads(params["filters"])
    if doctype in {"Warehouse", "Purchase Order"}:
        assert ["company", "=", settings.company] in filters
    if doctype == "Bin":
        assert ["warehouse", "in", settings.warehouses] in filters
    assert not result.has_more

@pytest.mark.parametrize("status,code", [(401,"authentication_failed"),(403,"permission_denied"),(404,"not_found"),(429,"rate_limited"),(500,"http_error"),(302,"http_error")])
async def test_http_errors_sanitized(settings, status, code):
    async with ERPNextClient(settings, transport=httpx.MockTransport(responder)) as client:
        async def get(*args, **kwargs):
            return httpx.Response(status, json={"exc": "SECRET TRACE", "api_secret": "secret"})
        with patch.object(client._http, "get", get), pytest.raises(ERPNextError) as err:
            await ERPNextAdapter(client).query("Supplier", Query())
        assert err.value.code == code
        assert "SECRET" not in str(err.value)

@pytest.mark.parametrize("body,code", [({"exc_type":"PermissionError"},"erp_error"), ({"data":{}},"invalid_payload"), ({"data":[{}]},"invalid_document")])
async def test_bad_erp_payload(settings, body, code):
    def handler(request):
        return responder(request) if request.url.path.endswith("get_logged_user") else httpx.Response(200,json=body)
    async with ERPNextClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ERPNextError, match=code):
            await ERPNextAdapter(client).query("Supplier", Query())

async def test_timeout_empty_and_pagination(settings):
    async with ERPNextClient(settings, transport=httpx.MockTransport(responder)) as client:
        def timeout(*args, **kwargs): raise httpx.ReadTimeout("secret")
        with patch.object(client._http, "get", side_effect=timeout), pytest.raises(ERPNextError, match="timeout"):
            await ERPNextAdapter(client).query("Supplier", Query())
        for rows, more in [([],False), ([ROWS["Supplier"]]*3,True)]:
            async def get(*a, **kw): return httpx.Response(200,json={"data":rows})
            with patch.object(client._http, "get", get):
                result = await ERPNextAdapter(client).query("Supplier", Query(limit=2,offset=10))
                assert result.has_more is more
                assert len(result.data) == min(2,len(rows))

async def test_scope_rejection(settings):
    async with ERPNextClient(settings, transport=httpx.MockTransport(responder)) as client:
        adapter = ERPNextAdapter(client)
        with pytest.raises(ERPNextError, match="warehouse_denied"):
            await adapter.query("Bin", BinQuery(warehouse="Other"))
        settings.company = "Another Co"
        with pytest.raises(ERPNextError, match="warehouse_company_mismatch"):
            await adapter.query("Bin", BinQuery())
        with pytest.raises(ERPNextError, match="response_scope_violation"):
            await adapter.query("Purchase Order", PurchaseOrderQuery())

@pytest.mark.parametrize("change,code", [({"api_user":"Administrator"},"least_privilege"),({"api_key":""},"configuration_required"),({"company":""},"configuration_required"),({"warehouses":[]},"configuration_required"),({"api_user":"other"},"identity_mismatch")])
async def test_fail_closed_configuration(settings, change, code):
    settings = settings.model_copy(update=change)
    # Pydantic 的 model_copy 不会自动转换敏感字段的类型。
    settings = ERPNextSettings.model_validate(settings.model_dump())
    with pytest.raises(ERPNextError, match=code):
        async with ERPNextClient(settings,transport=httpx.MockTransport(responder)): pass

async def test_mcp_registry_and_roundtrip(settings):
    original = ERPNextClient
    with patch("src.mcp_server.tools.erpnext_tools.ERPNextSettings.from_env", return_value=settings), patch("src.mcp_server.tools.erpnext_tools.ERPNextClient", side_effect=lambda s: original(s,transport=httpx.MockTransport(responder))):
        async with Client(mcp) as client:
            tools = await client.list_tools()
            assert {t.name for t in tools} == {"erpnext_suppliers","erpnext_items","erpnext_warehouses","erpnext_bins","erpnext_purchase_orders"}
            for name in [t.name for t in tools]:
                result = await client.call_tool(name, {"query":{}})
                assert not result.is_error
                assert "data" in result.structured_content

async def test_mcp_exposes_only_safe_error_code():
    from fastmcp.exceptions import ToolError
    from src.mcp_server.tools.erpnext_tools import read
    with patch("src.mcp_server.tools.erpnext_tools.ERPNextSettings.from_env",return_value=ERPNextSettings()):
        with pytest.raises(ToolError, match="configuration_required"):
            await read("Supplier", Query())
