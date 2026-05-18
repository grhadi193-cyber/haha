from decimal import Decimal
from datetime import datetime
from typing import List
from pydantic import BaseModel
from ninja import Schema


# ── Catalog ──────────────────────────────────────────────────────────────────

class CategoryOut(Schema):
    id: int
    name: str
    slug: str


class ProductListOut(Schema):
    id: int
    name: str
    slug: str
    price: Decimal
    stock: int
    is_active: bool


class ProductDetailOut(Schema):
    id: int
    name: str
    slug: str
    description: str
    price: Decimal
    stock: int
    weight: Decimal | None
    is_active: bool
    category: CategoryOut | None


# ── Orders ────────────────────────────────────────────────────────────────────

class OrderItemIn(Schema):
    product_id: int
    quantity: int


class CreateOrderIn(Schema):
    address_id: int
    shipping_method_id: int
    items: List[OrderItemIn]


class OrderItemOut(Schema):
    product_id: int
    quantity: int
    unit_price: Decimal


class OrderOut(Schema):
    id: int
    status: str
    total_amount: Decimal
    shipping_cost: Decimal
    created_at: datetime
    items: List[OrderItemOut]
