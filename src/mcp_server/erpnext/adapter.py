"""Company/warehouse scope is server-owned, never accepted from the model."""
from pydantic import ValidationError
from .client import ERPNextClient, ERPNextError
from .models import Query, BinQuery, PurchaseOrderQuery, Supplier, Item, Warehouse, Bin, PurchaseOrder, ReadResult

MODELS = {"Supplier": Supplier, "Item": Item, "Warehouse": Warehouse, "Bin": Bin, "Purchase Order": PurchaseOrder}

class ERPNextAdapter:
    def __init__(self, client: ERPNextClient):
        self.client = client
        self.settings = client.settings

    async def query(self, doctype: str, query: Query):
        if doctype not in MODELS:
            raise ERPNextError("doctype_denied")
        model = MODELS[doctype]
        s = self.settings
        filters = []
        if query.name:
            filters.append(["name", "=", query.name])
        scope = "Frappe API user permissions (shared master)"
        if doctype == "Warehouse":
            filters.extend([["company", "=", s.company], ["name", "in", s.warehouses]])
            scope = "company + warehouse allowlist + Frappe API user permissions"
        elif doctype == "Bin":
            assert isinstance(query, BinQuery)
            if query.warehouse and query.warehouse not in s.warehouses:
                raise ERPNextError("warehouse_denied")
            requested = [query.warehouse] if query.warehouse else s.warehouses
            # ERPNext 16.34.1 Bin has company; also verify warehouse ownership.
            warehouses = await self.client.list_documents("Warehouse", fields=["name", "company"],
                filters=[["company", "=", s.company], ["name", "in", requested]], limit=len(requested))
            if {w.get("name") for w in warehouses if w.get("company") == s.company} != set(requested):
                raise ERPNextError("warehouse_company_mismatch")
            filters.extend([["company", "=", s.company], ["warehouse", "in", requested]])
            if query.item_code:
                filters.append(["item_code", "=", query.item_code])
            scope = "company-verified warehouse allowlist + Frappe API user permissions"
        elif doctype == "Purchase Order":
            assert isinstance(query, PurchaseOrderQuery)
            filters.append(["company", "=", s.company])
            for field in ("supplier", "status", "docstatus"):
                value = getattr(query, field)
                if value is not None:
                    filters.append([field, "=", value])
            scope = "company + Frappe API user permissions (order headers; no warehouse filter)"
        rows = await self.client.list_documents(doctype, fields=list(model.model_fields), filters=filters,
            limit=query.limit + 1, offset=query.offset)
        try:
            data = [model.model_validate(row) for row in rows[:query.limit]]
        except ValidationError:
            raise ERPNextError("invalid_document") from None
        if doctype in {"Warehouse", "Purchase Order", "Bin"} and any(row.company != s.company for row in data):
            raise ERPNextError("response_scope_violation")
        if doctype == "Warehouse" and any(row.name not in s.warehouses for row in data):
            raise ERPNextError("response_scope_violation")
        if doctype == "Bin" and any(row.warehouse not in requested for row in data):
            raise ERPNextError("response_scope_violation")
        return ReadResult[model](data=data, limit=query.limit, offset=query.offset,
                                has_more=len(rows) > query.limit, scope=scope)
