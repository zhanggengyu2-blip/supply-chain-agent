"""阶段一只注册读取工具，旧 Java ERP 工具保持未注册。"""
from ..erpnext.models import ERPNextSettings, Query, BinQuery, PurchaseOrderQuery, Supplier, Item, Warehouse, Bin, PurchaseOrder, ReadResult
from fastmcp.exceptions import ToolError
from ..erpnext.client import ERPNextClient, ERPNextError
from ..erpnext.adapter import ERPNextAdapter

async def read(doctype, query):
    try:
        async with ERPNextClient(ERPNextSettings.from_env()) as client:
            return await ERPNextAdapter(client).query(doctype, query)
    except ERPNextError as exc:
        # MCP 边界只对外暴露脱敏后的错误代码和状态。
        raise ToolError(str(exc)) from None

def register_erpnext_tools(mcp):
    @mcp.tool()
    async def erpnext_suppliers(query: Query) -> ReadResult[Supplier]:
        """查询供应商；共享主数据，遵循固定 API 用户的 Frappe 权限。"""
        return await read("Supplier", query)

    @mcp.tool()
    async def erpnext_items(query: Query) -> ReadResult[Item]:
        """查询物料，item_code 为字符串业务编码，遵循 Frappe 权限。"""
        return await read("Item", query)

    @mcp.tool()
    async def erpnext_warehouses(query: Query) -> ReadResult[Warehouse]:
        """查询固定公司和仓库白名单范围内的仓库。"""
        return await read("Warehouse", query)

    @mcp.tool()
    async def erpnext_bins(query: BinQuery) -> ReadResult[Bin]:
        """查询库存 Bin，先验证仓库所属公司，再按仓库白名单查询。"""
        return await read("Bin", query)

    @mcp.tool()
    async def erpnext_purchase_orders(query: PurchaseOrderQuery) -> ReadResult[PurchaseOrder]:
        """查询固定公司采购订单表头；status 为 ERPNext 字符串，docstatus 为 0/1/2。表头按公司权限，不按仓库过滤。"""
        return await read("Purchase Order", query)
