"""必须显式开启；不创建凭据，所有请求均使用 GET。"""
import os
import pytest
from src.mcp_server.erpnext.models import ERPNextSettings, Query, BinQuery, PurchaseOrderQuery
from src.mcp_server.erpnext.client import ERPNextClient
from src.mcp_server.erpnext.adapter import ERPNextAdapter

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("RUN_ERPNEXT_INTEGRATION") != "1", reason="Set RUN_ERPNEXT_INTEGRATION=1 with least-privilege credentials")]

async def test_authenticated_five_doctype_readonly():
    async with ERPNextClient(ERPNextSettings.from_env()) as client:
        adapter=ERPNextAdapter(client)
        for doctype in ("Supplier","Item","Warehouse","Bin","Purchase Order"):
            query=BinQuery(limit=1) if doctype=="Bin" else PurchaseOrderQuery(limit=1) if doctype=="Purchase Order" else Query(limit=1)
            result=await adapter.query(doctype,query)
            assert isinstance(result.data,list)
