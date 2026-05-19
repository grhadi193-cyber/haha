from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel


# ── Catalog ──────────────────────────────────────────────────

class CategoryOut(BaseModel):
    id:   int
    name: str
    slug: str

    class Config:
        from_attributes = True


class ProductListOut(BaseModel):
    id:         int
    name:       str
    slug:       str
    price:      Decimal
    stock:      int
    is_active:  bool
    category_id: Optional[int] = None

    class Config:
        from_attributes = True


class ProductDetailOut(ProductListOut):
    description: Optional[str] = None
    weight:      Optional[Decimal] = None


# ── Orders ───────────────────────────────────────────────────

class OrderItemIn(BaseModel):
    product_id: int
    quantity:   int


class CreateOrderIn(BaseModel):
    address_id:         int
    shipping_method_id: int
    items:              List[OrderItemIn]


class OrderItemOut(BaseModel):
    product_id:   int
    product_name: str
    quantity:     int
    unit_price:   Decimal

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id:              int
    status:          str
    total_price:     Decimal
    shipping_cost:   Decimal
    payment_url:     Optional[str] = None
    items:           List[OrderItemOut]

    class Config:
        from_attributes = True
