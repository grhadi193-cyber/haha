from decimal import Decimal
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str

    model_config = {"from_attributes": True}


class ProductListOut(BaseModel):
    id: int
    name: str
    slug: str
    price: Decimal
    stock: int
    image: Optional[str] = None
    category: Optional[CategoryOut] = None

    model_config = {"from_attributes": True}


class ProductImageOut(BaseModel):
    id: int
    image: str
    alt_text: str
    order: int
    is_cover: bool

    model_config = {"from_attributes": True}

class ProductDetailOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    price: Decimal
    discount_price: Optional[Decimal] = None
    sku: Optional[str] = None
    meta_title: str = ""
    meta_description: str = ""
    view_count: int = 0
    stock: int
    weight: Decimal
    image: Optional[str] = None
    category: Optional[CategoryOut] = None
    images: List[ProductImageOut] = []

    model_config = {"from_attributes": True}


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int


class CreateOrderIn(BaseModel):
    address_id: int
    shipping_method_id: int
    items: List[OrderItemIn]


class OrderItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    status: str
    total_price: Decimal
    shipping_cost: Decimal
    tracking_number: str = ""
    payment_url: Optional[str] = None
    items: List[OrderItemOut] = []

    model_config = {"from_attributes": True}


# ── Phase 12 — Order Tracking ──────────────────────────────────────────

STATUS_DISPLAY = {
    "pending":    "درحال تایید",
    "paid":       "تایید شده",
    "processing": "آماده سازی",
    "shipped":    "تحویل به پست",
    "delivered":  "تحویل داده شده",
    "cancelled":  "لغو شده",
}


class OrderItemTrackingOut(BaseModel):
    product_name: str
    quantity: int
    unit_price: Decimal

class OrderStatusHistoryOut(BaseModel):
    status: str
    status_display: str
    note: str
    created_at: datetime

class UserOrderOut(BaseModel):
    id: int
    tracking_number: str
    postal_tracking: str
    carrier_name: str
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    customer_notes: str
    status: str
    status_display: str
    total_price: Decimal
    shipping_cost: Decimal
    created_at: datetime
    shipping_address_snapshot: Optional[dict] = None
    items: List[OrderItemTrackingOut]
    history: List[OrderStatusHistoryOut] = []

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        items = [
            OrderItemTrackingOut(
                product_name=i.product_name_snapshot or i.product.name,
                quantity=i.quantity,
                unit_price=i.unit_price,
            )
            for i in obj.items.all()
        ]
        history = [
            OrderStatusHistoryOut(
                status=h.status,
                status_display=STATUS_DISPLAY.get(h.status, h.status),
                note=h.note,
                created_at=h.created_at,
            )
            for h in obj.history.all()
        ]
        return cls(
            id=obj.pk,
            tracking_number=obj.tracking_number,
            postal_tracking=obj.postal_tracking,
            carrier_name=obj.carrier_name,
            shipped_at=obj.shipped_at,
            delivered_at=obj.delivered_at,
            customer_notes=obj.customer_notes,
            status=obj.status,
            status_display=STATUS_DISPLAY.get(obj.status, obj.status),
            total_price=obj.total_price,
            shipping_cost=obj.shipping_cost,
            created_at=obj.created_at,
            shipping_address_snapshot=obj.shipping_address_snapshot,
            items=items,
            history=history,
        )
