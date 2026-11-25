"""使用 ERPNext v16 字段名；共享主数据没有 company 字段。"""
from decimal import Decimal
from typing import Generic, TypeVar, Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr

class ERPNextSettings(BaseModel):
    base_url: str = "http://127.0.0.1:8080"
    api_key: SecretStr = SecretStr("")
    api_secret: SecretStr = SecretStr("")
    api_user: str = ""
    company: str = ""
    warehouses: list[str] = Field(default_factory=list)
    timeout: float = Field(default=15, gt=0, le=120)

    @classmethod
    def from_env(cls):
        import os
        from dotenv import load_dotenv
        from pathlib import Path
        load_dotenv(Path(__file__).resolve().parents[3] / ".env")
        return cls(base_url=os.getenv("ERPNEXT_BASE_URL", "http://127.0.0.1:8080"),
                   api_key=os.getenv("ERPNEXT_API_KEY", ""), api_secret=os.getenv("ERPNEXT_API_SECRET", ""),
                   api_user=os.getenv("ERPNEXT_API_USER", ""), company=os.getenv("ERPNEXT_COMPANY", ""),
                   warehouses=[s.strip() for s in os.getenv("ERPNEXT_WAREHOUSES", "").split(",") if s.strip()])

class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=140)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

class BinQuery(Query):
    warehouse: str | None = None
    item_code: str | None = None

class PurchaseOrderQuery(Query):
    supplier: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=80)
    docstatus: Literal[0, 1, 2] | None = None

class Supplier(BaseModel):
    name: str
    supplier_name: str
    supplier_group: str | None = None
    supplier_type: str | None = None
    disabled: int = 0

class Item(BaseModel):
    name: str
    item_code: str
    item_name: str
    item_group: str | None = None
    stock_uom: str
    is_stock_item: int = 1
    disabled: int = 0

class Warehouse(BaseModel):
    name: str
    warehouse_name: str
    company: str
    is_group: int = 0
    disabled: int = 0

class Bin(BaseModel):
    company: str
    name: str
    item_code: str
    warehouse: str
    actual_qty: Decimal = Decimal(0)
    reserved_qty: Decimal = Decimal(0)
    ordered_qty: Decimal = Decimal(0)
    projected_qty: Decimal = Decimal(0)
    stock_uom: str | None = None

class PurchaseOrder(BaseModel):
    name: str
    supplier: str
    company: str
    transaction_date: str
    schedule_date: str | None = None
    status: str
    docstatus: Literal[0, 1, 2]
    currency: str
    grand_total: Decimal
    per_received: Decimal = Decimal(0)
    per_billed: Decimal = Decimal(0)

T = TypeVar("T")
class ReadResult(BaseModel, Generic[T]):
    data: list[T]
    limit: int
    offset: int
    has_more: bool
    scope: str
