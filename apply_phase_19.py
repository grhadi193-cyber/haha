# coding: utf-8
"""
apply_phase_19.py
=================
Phase 19 — Pagination + Search روی محصولات

فایل‌های تغییریافته:
  - store/schemas.py
  - store/services.py
  - store/api.py
  - admin_panel/api.py

اجرا:
    python apply_phase_19.py
"""

from pathlib import Path

BASE = Path(__file__).resolve().parent

FILES = {}

# ─────────────────────────────────────────────────────────────────────────────
# store/schemas.py
# ─────────────────────────────────────────────────────────────────────────────

FILES["store/schemas.py"] = '''\
from decimal import Decimal
from typing import Generic, List, Optional, TypeVar
from datetime import datetime
from pydantic import BaseModel


# ── Generic Paginated Response ─────────────────────────────────────────────

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """پاسخ صفحه‌بندی‌شده عمومی — قابل استفاده برای هر نوع داده."""
    count: int
    page: int
    page_size: int
    total_pages: int
    results: List[T]


# ── Category ─────────────────────────────────────────────────────────────────

class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str

    model_config = {"from_attributes": True}


# ── Product Images ────────────────────────────────────────────────────────────

class ProductImageOut(BaseModel):
    id: int
    image: str
    alt_text: str
    order: int
    is_cover: bool

    model_config = {"from_attributes": True}


# ── Product List (public) ─────────────────────────────────────────────────────

class ProductListOut(BaseModel):
    id: int
    name: str
    slug: str
    price: Decimal
    discount_price: Optional[Decimal] = None
    weight: Decimal = Decimal("0")
    stock: int
    image: Optional[str] = None
    category: Optional[CategoryOut] = None

    model_config = {"from_attributes": True}


# ── Product Detail (public) ───────────────────────────────────────────────────

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


# ── Order (Create) ────────────────────────────────────────────────────────────

class OrderItemIn(BaseModel):
    product_id: int
    quantity: int


class CreateOrderIn(BaseModel):
    address_id: int
    shipping_method_id: int
    items: List[OrderItemIn]


# ── Order (Response) ──────────────────────────────────────────────────────────

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


# ── Order Tracking (Phase 13) ─────────────────────────────────────────────────

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
'''

# ─────────────────────────────────────────────────────────────────────────────
# store/services.py
# ─────────────────────────────────────────────────────────────────────────────

FILES["store/services.py"] = '''\
from decimal import Decimal
from typing import List, Optional

from django.db import transaction as db_transaction
from django.db.models import F, Q

from core.exceptions import NotFoundError, InsufficientStockError, AppException
from .models import Order, OrderItem, OrderStatusHistory, Product
from accounts.models import Address
from shipping.models import ShippingMethod
from shipping.services import calculate_shipping_cost


# ── Catalogue ─────────────────────────────────────────────────────────────────

def get_active_categories():
    from .models import Category
    return list(Category.objects.filter(is_active=True))


def get_active_products(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    لیست محصولات فعال با پشتیبانی از:
      - فیلتر category_id
      - جستجو در name و description
      - صفحه‌بندی با page و page_size
    خروجی: دیکشنری سازگار با PaginatedResponse
    """
    # اعتبارسنجی محدوده‌ها
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    qs = (
        Product.objects
        .select_related("category")
        .filter(is_active=True)
        .order_by("-created_at")
    )

    if category_id:
        qs = qs.filter(category_id=category_id)

    if search:
        qs = qs.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    total = qs.count()
    start = (page - 1) * page_size
    results = list(qs[start: start + page_size])
    total_pages = max(1, (total + page_size - 1) // page_size)

    return {
        "count": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "results": results,
    }


def get_product_by_id(product_id: int) -> Product:
    """
    جزئیات یک محصول فعال.
    - view_count یک واحد افزایش می‌یابد.
    - images (گالری) از طریق prefetch_related بارگذاری می‌شوند.
    """
    try:
        product = (
            Product.objects
            .select_related("category")
            .prefetch_related("images")
            .get(pk=product_id, is_active=True)
        )
    except Product.DoesNotExist:
        raise NotFoundError(f"Product {product_id} not found")

    # افزایش view_count بدون race condition
    Product.objects.filter(pk=product_id).update(view_count=F("view_count") + 1)

    # مقدار view_count در آبجکت بازگشتی را دستی بروزرسانی می‌کنیم
    product.view_count += 1

    return product


# ── Orders ────────────────────────────────────────────────────────────────────

def create_order(user, address_id: int, shipping_method_id: int, items: list) -> dict:
    try:
        address = Address.objects.get(pk=address_id, user=user)
    except Address.DoesNotExist:
        raise NotFoundError("Address not found")

    try:
        method = ShippingMethod.objects.get(pk=shipping_method_id, is_active=True)
    except ShippingMethod.DoesNotExist:
        raise NotFoundError("Shipping method not found")

    if not items:
        raise AppException("سبد خرید خالی است", status_code=400)

    order_items = []
    total = Decimal("0")

    for item_in in items:
        product_id = item_in["product_id"] if isinstance(item_in, dict) else item_in.product_id
        quantity   = item_in["quantity"]   if isinstance(item_in, dict) else item_in.quantity
        try:
            product = Product.objects.get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundError(f"Product {product_id} not found")

        if product.stock < quantity:
            raise InsufficientStockError(product.name, product.stock, quantity)

        order_items.append((product, quantity, product.price))
        total += product.price * quantity

    shipping_cost = calculate_shipping_cost(method)

    shipping_address_snapshot = {
        "province":    address.province,
        "city":        address.city,
        "street":      address.street,
        "postal_code": address.postal_code,
        "title":       address.title,
    }

    with db_transaction.atomic():
        order = Order.objects.create(
            user=user,
            address=address,
            shipping_method=method,
            status="pending",
            total_price=total + Decimal(str(shipping_cost)),
            shipping_cost=Decimal(str(shipping_cost)),
            shipping_address_snapshot=shipping_address_snapshot,
        )

        OrderStatusHistory.objects.create(
            order=order, status="pending", note="سفارش ثبت شد", created_by=user
        )

        for product, qty, price in order_items:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=qty,
                unit_price=price,
                product_name_snapshot=product.name,
            )
            Product.objects.filter(pk=product.pk).update(stock=F("stock") - qty)

    return {"order": order, "payment_url": None}


def cancel_order(order_id: int, user) -> Order:
    """
    لغو سفارش توسط کاربر.
    فقط سفارش‌های pending قابل لغو هستند.
    موجودی محصولات برگشت داده می‌شود.
    یک رکورد تاریخچه با status=cancelled ثبت می‌شود.
    """
    with db_transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id, user=user)
        except Order.DoesNotExist:
            raise AppException("سفارش یافت نشد", status_code=404)

        if order.status != "pending":
            raise AppException("تنها سفارش‌های در حال تایید قابل لغو هستند.", status_code=400)

        for item in order.items.select_related("product"):
            Product.objects.filter(pk=item.product_id).update(
                stock=F("stock") + item.quantity
            )

        order.status = "cancelled"
        order.save(update_fields=["status"])

        OrderStatusHistory.objects.create(
            order=order, status="cancelled", note="لغو توسط کاربر", created_by=user
        )

    return order


def update_order_status(
    order_id: int,
    new_status: str,
    admin_user,
    tracking_number: str = "",
    postal_tracking: str = "",
    note: str = "",
) -> Order:
    """
    تغییر وضعیت سفارش توسط ادمین.
    یک رکورد در OrderStatusHistory ثبت می‌کند.
    """
    valid_statuses = {choice[0] for choice in Order.STATUS_CHOICES}
    if new_status not in valid_statuses:
        raise AppException(
            f"وضعیت نامعتبر است. مقادیر مجاز: {', '.join(sorted(valid_statuses))}",
            status_code=400,
        )

    with db_transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id)
        except Order.DoesNotExist:
            raise AppException("سفارش یافت نشد", status_code=404)

        update_fields = ["status"]
        order.status = new_status

        if tracking_number:
            order.tracking_number = tracking_number
            update_fields.append("tracking_number")

        if postal_tracking:
            order.postal_tracking = postal_tracking
            update_fields.append("postal_tracking")

        if new_status == "shipped" and not order.shipped_at:
            from django.utils import timezone
            order.shipped_at = timezone.now()
            update_fields.append("shipped_at")

        if new_status == "delivered" and not order.delivered_at:
            from django.utils import timezone
            order.delivered_at = timezone.now()
            update_fields.append("delivered_at")

        order.save(update_fields=update_fields)

        OrderStatusHistory.objects.create(
            order=order,
            status=new_status,
            note=note or f"وضعیت توسط ادمین به «{new_status}» تغییر کرد",
            created_by=admin_user,
        )

    return order


def get_user_orders(user) -> List[Order]:
    """لیست سفارش‌های کاربر به همراه آیتم‌ها و تاریخچه وضعیت."""
    return list(
        Order.objects.filter(user=user)
        .prefetch_related("items__product", "history")
        .order_by("-created_at")
    )


def get_user_order_detail(user, order_id: int) -> Order:
    """جزئیات یک سفارش خاص به همراه آیتم‌ها و تاریخچه وضعیت."""
    try:
        return (
            Order.objects.filter(user=user)
            .prefetch_related("items__product", "history")
            .get(pk=order_id)
        )
    except Order.DoesNotExist:
        raise AppException("سفارش یافت نشد", status_code=404)
'''

# ─────────────────────────────────────────────────────────────────────────────
# store/api.py
# ─────────────────────────────────────────────────────────────────────────────

FILES["store/api.py"] = '''\
from typing import Optional

from django.http import JsonResponse
from ninja import Router
from ninja.security import HttpBearer

from .schemas import (
    CategoryOut,
    PaginatedResponse,
    ProductDetailOut,
    ProductListOut,
    CreateOrderIn,
    OrderOut,
    OrderItemOut,
)
from .services import (
    get_active_categories,
    get_active_products,
    get_product_by_id,
    create_order,
)
from core.exceptions import NotFoundError, InsufficientStockError

router = Router(tags=["Store"])


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import TokenError
        try:
            validated = AccessToken(token)
            from accounts.models import User
            return User.objects.get(pk=validated["user_id"])
        except (TokenError, Exception):
            return None


@router.get("/categories", response=list[CategoryOut])
def list_categories(request):
    return get_active_categories()


@router.get("/products", response=PaginatedResponse[ProductListOut])
def list_products(
    request,
    page: int = 1,
    page_size: int = 20,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
):
    """
    لیست محصولات فعال با pagination و جستجو.

    - **page**: شماره صفحه (پیش‌فرض ۱)
    - **page_size**: تعداد در هر صفحه (پیش‌فرض ۲۰، حداکثر ۱۰۰)
    - **category_id**: فیلتر بر اساس دسته‌بندی
    - **search**: جستجو در نام و توضیحات محصول
    """
    data = get_active_products(
        category_id=category_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse[ProductListOut](
        count=data["count"],
        page=data["page"],
        page_size=data["page_size"],
        total_pages=data["total_pages"],
        results=[ProductListOut.model_validate(p) for p in data["results"]],
    )


@router.get("/products/{product_id}", response=ProductDetailOut)
def get_product(request, product_id: int):
    try:
        return get_product_by_id(product_id)
    except NotFoundError as e:
        return JsonResponse({"detail": str(e)}, status=404)


@router.post("/orders", response=OrderOut, auth=AuthBearer())
def create_order_endpoint(request, payload: CreateOrderIn):
    items = [item.dict() for item in payload.items]
    try:
        result = create_order(
            user=request.auth,
            address_id=payload.address_id,
            shipping_method_id=payload.shipping_method_id,
            items=items,
        )
    except NotFoundError as e:
        return JsonResponse({"detail": str(e)}, status=404)
    except InsufficientStockError as e:
        return JsonResponse({"detail": str(e)}, status=400)

    order       = result["order"]
    payment_url = result.get("payment_url")

    order_items_out = [
        OrderItemOut(
            product_id=oi.product_id,
            product_name=oi.product.name,
            quantity=oi.quantity,
            unit_price=oi.unit_price,
        )
        for oi in order.items.select_related("product").all()
    ]

    return OrderOut(
        id=order.pk,
        status=order.status,
        total_price=order.total_price,
        shipping_cost=order.shipping_cost,
        payment_url=payment_url,
        items=order_items_out,
    )
'''

# ─────────────────────────────────────────────────────────────────────────────
# admin_panel/api.py
# ─────────────────────────────────────────────────────────────────────────────

FILES["admin_panel/api.py"] = '''\
"""
Admin Panel API  —  Phase 17 + 18 + 19
========================================
تمام endpoint‌ها نیاز به is_staff=True دارند (AdminBearer).

Routers:
  GET  /api/admin/dashboard
  GET  /api/admin/users/
  GET  /api/admin/users/{id}/
  PUT  /api/admin/users/{id}/
  GET  /api/admin/orders/
  GET  /api/admin/orders/{id}/
  PUT  /api/admin/orders/{id}/status/
  GET  /api/admin/products/
  POST /api/admin/products/
  GET  /api/admin/products/{id}/
  PUT  /api/admin/products/{id}/
  PUT  /api/admin/products/{id}/stock/
  DELETE /api/admin/products/{id}/
  GET  /api/admin/analytics/overview/
  GET  /api/admin/settings/
  PUT  /api/admin/settings/

Phase 19: total_pages به AdminUserListOut و AdminOrderListOut اضافه شد.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from django.db import transaction as db_transaction
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from ninja import Router
from ninja.security import HttpBearer
from pydantic import BaseModel

from accounts.models import User
from core.exceptions import AppException, NotFoundError
from store.models import Order, OrderStatusHistory, Product
from store.schemas import UserOrderOut

logger = logging.getLogger(__name__)

router = Router(tags=["Admin"])


# ─────────────────────────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────────────────────────

class AdminBearer(HttpBearer):
    """JWT bearer که فقط کاربران is_staff=True را قبول می‌کند."""

    def authenticate(self, request, token):
        from rest_framework_simplejwt.exceptions import TokenError
        from rest_framework_simplejwt.tokens import AccessToken
        try:
            validated = AccessToken(token)
            user = User.objects.get(pk=validated["user_id"])
            if not user.is_staff:
                return None
            return user
        except (TokenError, User.DoesNotExist, Exception):
            return None


_auth = AdminBearer()


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class DashboardOut(BaseModel):
    total_users: int
    total_orders: int
    total_revenue: int
    orders_today: int
    orders_this_week: int
    orders_this_month: int


class AdminUserOut(BaseModel):
    id: int
    phone_number: str
    full_name: str
    email: Optional[str] = None
    is_active: bool
    date_joined: datetime
    order_count: int

    model_config = {"from_attributes": True}


class AdminUserListOut(BaseModel):
    count: int
    page: int
    page_size: int
    total_pages: int
    results: List[AdminUserOut]


class AdminUserUpdateIn(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class AdminOrderListOut(BaseModel):
    count: int
    page: int
    page_size: int
    total_pages: int
    results: List[UserOrderOut]


class AdminOrderStatusIn(BaseModel):
    status: str
    note: str = ""
    tracking_number: str = ""
    postal_tracking: str = ""


class AdminProductIn(BaseModel):
    name: str
    slug: str
    description: str = ""
    price: Decimal
    discount_price: Optional[Decimal] = None
    stock: int = 0
    weight: Decimal = Decimal("0")
    category_id: Optional[int] = None
    sku: Optional[str] = None
    meta_title: str = ""
    meta_description: str = ""
    is_active: bool = True


class AdminProductOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    price: Decimal
    discount_price: Optional[Decimal] = None
    stock: int
    weight: Decimal
    category_id: Optional[int] = None
    sku: Optional[str] = None
    meta_title: str
    meta_description: str
    is_active: bool
    view_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminProductListOut(BaseModel):
    count: int
    page: int
    page_size: int
    total_pages: int
    results: List[AdminProductOut]


class AdminStockUpdateIn(BaseModel):
    quantity_delta: int


class TopProductItem(BaseModel):
    id: int
    name: str
    total_sold: int
    revenue: Decimal


class AnalyticsOut(BaseModel):
    revenue_today: Decimal
    revenue_this_week: Decimal
    revenue_this_month: Decimal
    orders_by_status: dict
    top_products: List[TopProductItem]


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def _paginate(qs, page: int, page_size: int):
    """
    صفحه‌بندی روی QuerySet.
    برمی‌گرداند: (total_count, total_pages, page_qs)
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    total = qs.count()
    start = (page - 1) * page_size
    total_pages = max(1, (total + page_size - 1) // page_size)
    return total, total_pages, qs[start: start + page_size]


def _revenue_for(qs):
    """مجموع total_price برای سفارش‌های paid از یک QuerySet."""
    agg = qs.filter(status="paid").aggregate(total=Sum("total_price"))
    return agg["total"] or Decimal("0")


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    auth=_auth,
    response=DashboardOut,
    summary="داشبورد ادمین",
)
def admin_dashboard(request):
    """آمار کلی سایت."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    total_users = User.objects.count()
    total_orders = Order.objects.count()
    revenue_agg = Order.objects.filter(status="paid").aggregate(total=Sum("total_price"))
    total_revenue = int(revenue_agg["total"] or 0)

    orders_today = Order.objects.filter(created_at__gte=today_start).count()
    orders_this_week = Order.objects.filter(created_at__gte=week_start).count()
    orders_this_month = Order.objects.filter(created_at__gte=month_start).count()

    return DashboardOut(
        total_users=total_users,
        total_orders=total_orders,
        total_revenue=total_revenue,
        orders_today=orders_today,
        orders_this_week=orders_this_week,
        orders_this_month=orders_this_month,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/users/",
    auth=_auth,
    response=AdminUserListOut,
    summary="لیست کاربران (ادمین)",
)
def admin_list_users(request, page: int = 1, page_size: int = 20, search: str = ""):
    """
    لیست کاربران با pagination و جستجو.
    search روی phone_number و full_name اعمال می‌شود.
    پاسخ شامل total_pages است.
    """
    qs = User.objects.annotate(order_count=Count("orders")).order_by("-date_joined")
    if search:
        qs = qs.filter(
            Q(phone_number__icontains=search) | Q(full_name__icontains=search)
        )

    total, total_pages, page_qs = _paginate(qs, page, page_size)

    results = [
        AdminUserOut(
            id=u.pk,
            phone_number=u.phone_number,
            full_name=u.full_name,
            email=u.email,
            is_active=u.is_active,
            date_joined=u.date_joined,
            order_count=u.order_count,
        )
        for u in page_qs
    ]
    return AdminUserListOut(
        count=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        results=results,
    )


@router.get(
    "/users/{user_id}/",
    auth=_auth,
    response=AdminUserOut,
    summary="جزئیات کاربر (ادمین)",
)
def admin_get_user(request, user_id: int):
    """جزئیات یک کاربر + تعداد سفارش‌هایش."""
    try:
        user = User.objects.annotate(order_count=Count("orders")).get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse(
            {"error": True, "code": "not_found", "message": "کاربر یافت نشد."},
            status=404,
        )
    return AdminUserOut(
        id=user.pk,
        phone_number=user.phone_number,
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active,
        date_joined=user.date_joined,
        order_count=user.order_count,
    )


@router.put(
    "/users/{user_id}/",
    auth=_auth,
    summary="ویرایش کاربر (ادمین)",
)
def admin_update_user(request, user_id: int, payload: AdminUserUpdateIn):
    """
    ویرایش full_name و/یا is_active یک کاربر.
    فیلدهایی که None هستند تغییر نمی‌کنند.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse(
            {"error": True, "code": "not_found", "message": "کاربر یافت نشد."},
            status=404,
        )

    update_fields = []
    if payload.full_name is not None:
        user.full_name = payload.full_name
        update_fields.append("full_name")
    if payload.is_active is not None:
        user.is_active = payload.is_active
        update_fields.append("is_active")

    if update_fields:
        user.save(update_fields=update_fields)

    return {"detail": "کاربر با موفقیت ویرایش شد."}


# ─────────────────────────────────────────────────────────────────────────────
# Orders
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/orders/",
    auth=_auth,
    response=AdminOrderListOut,
    summary="لیست سفارش‌ها (ادمین)",
)
def admin_list_orders(request, page: int = 1, page_size: int = 20, status: str = ""):
    """
    همه سفارش‌ها با امکان فیلتر بر اساس status و pagination.
    پاسخ شامل total_pages است.
    مثال: GET /api/admin/orders/?status=pending&page=2
    """
    qs = (
        Order.objects.all()
        .prefetch_related("items__product", "history")
        .order_by("-created_at")
    )
    if status:
        qs = qs.filter(status=status)

    total, total_pages, page_qs = _paginate(qs, page, page_size)

    results = [UserOrderOut.model_validate(o) for o in page_qs]
    return AdminOrderListOut(
        count=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        results=results,
    )


@router.get(
    "/orders/{order_id}/",
    auth=_auth,
    response=UserOrderOut,
    summary="جزئیات سفارش (ادمین)",
)
def admin_get_order(request, order_id: int):
    """جزئیات کامل یک سفارش + history."""
    try:
        order = (
            Order.objects
            .prefetch_related("items__product", "history")
            .get(pk=order_id)
        )
    except Order.DoesNotExist:
        return JsonResponse(
            {"error": True, "code": "not_found", "message": "سفارش یافت نشد."},
            status=404,
        )
    return UserOrderOut.model_validate(order)


@router.put(
    "/orders/{order_id}/status/",
    auth=_auth,
    summary="تغییر وضعیت سفارش (ادمین)",
)
def admin_update_order_status(request, order_id: int, payload: AdminOrderStatusIn):
    """
    تغییر وضعیت سفارش + ثبت OrderStatusHistory.
    در صورت shipped شدن، shipped_at خودکار ثبت می‌شود.
    در صورت delivered شدن، delivered_at خودکار ثبت می‌شود.
    """
    from store.services import update_order_status as svc_update
    try:
        svc_update(
            order_id=order_id,
            new_status=payload.status,
            admin_user=request.auth,
            tracking_number=payload.tracking_number,
            postal_tracking=payload.postal_tracking,
            note=payload.note,
        )
    except AppException as e:
        return JsonResponse({"error": True, "code": "invalid", "message": e.detail}, status=e.status_code)
    return {"detail": "وضعیت سفارش با موفقیت تغییر کرد."}


# ─────────────────────────────────────────────────────────────────────────────
# Products
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/products/",
    auth=_auth,
    response=AdminProductListOut,
    summary="لیست محصولات (ادمین)",
)
def admin_list_products(
    request,
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    is_active: Optional[bool] = None,
):
    """
    لیست همه محصولات (فعال و غیرفعال) با pagination و جستجو.
    فیلتر: is_active=true/false
    پاسخ شامل total_pages است.
    """
    qs = Product.objects.select_related("category").order_by("-created_at")
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
    if is_active is not None:
        qs = qs.filter(is_active=is_active)

    total, total_pages, page_qs = _paginate(qs, page, page_size)
    results = [AdminProductOut.model_validate(p) for p in page_qs]
    return AdminProductListOut(
        count=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        results=results,
    )


@router.post(
    "/products/",
    auth=_auth,
    response=AdminProductOut,
    summary="ایجاد محصول جدید (ادمین)",
)
def admin_create_product(request, payload: AdminProductIn):
    """ساخت محصول جدید."""
    from store.models import Category
    category = None
    if payload.category_id:
        try:
            category = Category.objects.get(pk=payload.category_id)
        except Category.DoesNotExist:
            return JsonResponse(
                {"error": True, "code": "not_found", "message": "دسته‌بندی یافت نشد."},
                status=404,
            )

    product = Product.objects.create(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        price=payload.price,
        discount_price=payload.discount_price,
        stock=payload.stock,
        weight=payload.weight,
        category=category,
        sku=payload.sku or None,
        meta_title=payload.meta_title,
        meta_description=payload.meta_description,
        is_active=payload.is_active,
    )
    return AdminProductOut.model_validate(product)


@router.get(
    "/products/{product_id}/",
    auth=_auth,
    response=AdminProductOut,
    summary="جزئیات محصول (ادمین)",
)
def admin_get_product(request, product_id: int):
    """جزئیات کامل یک محصول (شامل غیرفعال‌ها)."""
    try:
        product = Product.objects.select_related("category").get(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse(
            {"error": True, "code": "not_found", "message": "محصول یافت نشد."},
            status=404,
        )
    return AdminProductOut.model_validate(product)


@router.put(
    "/products/{product_id}/",
    auth=_auth,
    response=AdminProductOut,
    summary="ویرایش محصول (ادمین)",
)
def admin_update_product(request, product_id: int, payload: AdminProductIn):
    """ویرایش کامل یک محصول."""
    from store.models import Category
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse(
            {"error": True, "code": "not_found", "message": "محصول یافت نشد."},
            status=404,
        )

    category = None
    if payload.category_id:
        try:
            category = Category.objects.get(pk=payload.category_id)
        except Category.DoesNotExist:
            return JsonResponse(
                {"error": True, "code": "not_found", "message": "دسته‌بندی یافت نشد."},
                status=404,
            )

    product.name = payload.name
    product.slug = payload.slug
    product.description = payload.description
    product.price = payload.price
    product.discount_price = payload.discount_price
    product.stock = payload.stock
    product.weight = payload.weight
    product.category = category
    product.sku = payload.sku or None
    product.meta_title = payload.meta_title
    product.meta_description = payload.meta_description
    product.is_active = payload.is_active
    product.save()

    return AdminProductOut.model_validate(product)


@router.put(
    "/products/{product_id}/stock/",
    auth=_auth,
    summary="تغییر موجودی محصول (ادمین)",
)
def admin_update_stock(request, product_id: int, payload: AdminStockUpdateIn):
    """
    تغییر موجودی با quantity_delta.
    مثبت = اضافه کردن به موجودی.
    منفی = کسر از موجودی.
    موجودی نمی‌تواند زیر صفر برود.
    """
    try:
        with db_transaction.atomic():
            product = Product.objects.select_for_update().get(pk=product_id)
            new_stock = product.stock + payload.quantity_delta
            if new_stock < 0:
                return JsonResponse(
                    {
                        "error": True,
                        "code": "insufficient_stock",
                        "message": f"موجودی کافی نیست. موجودی فعلی: {product.stock}",
                    },
                    status=400,
                )
            product.stock = new_stock
            product.save(update_fields=["stock"])
    except Product.DoesNotExist:
        return JsonResponse(
            {"error": True, "code": "not_found", "message": "محصول یافت نشد."},
            status=404,
        )

    return {"detail": "موجودی با موفقیت بروزرسانی شد.", "new_stock": product.stock}


@router.delete(
    "/products/{product_id}/",
    auth=_auth,
    summary="غیرفعال کردن محصول (ادمین)",
)
def admin_delete_product(request, product_id: int):
    """
    soft delete: محصول را غیرفعال می‌کند (is_active=False).
    محصول از دیتابیس حذف نمی‌شود.
    """
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse(
            {"error": True, "code": "not_found", "message": "محصول یافت نشد."},
            status=404,
        )
    product.is_active = False
    product.save(update_fields=["is_active"])
    return {"detail": "محصول با موفقیت غیرفعال شد."}


# ─────────────────────────────────────────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/analytics/overview/",
    auth=_auth,
    response=AnalyticsOut,
    summary="آنالیتیکس فروش (ادمین)",
)
def admin_analytics_overview(request):
    """
    آمار درآمد و سفارش‌ها:
    - درآمد امروز / این هفته / این ماه
    - تعداد سفارش به تفکیک وضعیت
    - ۵ محصول پرفروش
    """
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    revenue_today = _revenue_for(Order.objects.filter(created_at__gte=today_start))
    revenue_this_week = _revenue_for(Order.objects.filter(created_at__gte=week_start))
    revenue_this_month = _revenue_for(Order.objects.filter(created_at__gte=month_start))

    status_counts = (
        Order.objects.values("status")
        .annotate(count=Count("id"))
    )
    all_statuses = [s for s, _ in Order.STATUS_CHOICES]
    status_map = {row["status"]: row["count"] for row in status_counts}
    orders_by_status = {s: status_map.get(s, 0) for s in all_statuses}

    from store.models import OrderItem
    top_items = (
        OrderItem.objects.filter(order__status="paid")
        .values("product_id", "product__name")
        .annotate(
            total_sold=Sum("quantity"),
            revenue=Sum(F("quantity") * F("unit_price")),
        )
        .order_by("-total_sold")[:5]
    )

    top_products = [
        TopProductItem(
            id=row["product_id"],
            name=row["product__name"],
            total_sold=row["total_sold"],
            revenue=row["revenue"] or Decimal("0"),
        )
        for row in top_items
    ]

    return AnalyticsOut(
        revenue_today=revenue_today,
        revenue_this_week=revenue_this_week,
        revenue_this_month=revenue_this_month,
        orders_by_status=orders_by_status,
        top_products=top_products,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SiteSettings  (Phase 18)
# ─────────────────────────────────────────────────────────────────────────────

class AdminSiteSettingsOut(BaseModel):
    site_name:        str
    banner_text:      str
    announcement:     str
    primary_color:    str
    maintenance_mode: bool
    social_instagram: str
    social_telegram:  str
    support_phone:    str
    logo:             Optional[str] = None
    hero_title:       str
    hero_text:        str
    hero_banner:      Optional[str] = None
    about_us:         str

    model_config = {"from_attributes": True}


class AdminSiteSettingsUpdateIn(BaseModel):
    site_name:        Optional[str]  = None
    banner_text:      Optional[str]  = None
    announcement:     Optional[str]  = None
    primary_color:    Optional[str]  = None
    maintenance_mode: Optional[bool] = None
    social_instagram: Optional[str]  = None
    social_telegram:  Optional[str]  = None
    support_phone:    Optional[str]  = None
    hero_title:       Optional[str]  = None
    hero_text:        Optional[str]  = None
    about_us:         Optional[str]  = None


def _settings_to_out(s, request) -> AdminSiteSettingsOut:
    def _url(field):
        if field and hasattr(field, "url"):
            try:
                return request.build_absolute_uri(field.url)
            except Exception:
                return None
        return None

    return AdminSiteSettingsOut(
        site_name        = s.site_name,
        banner_text      = s.banner_text,
        announcement     = s.announcement,
        primary_color    = s.primary_color,
        maintenance_mode = s.maintenance_mode,
        social_instagram = s.social_instagram,
        social_telegram  = s.social_telegram,
        support_phone    = s.support_phone,
        logo             = _url(s.logo),
        hero_title       = s.hero_title,
        hero_text        = s.hero_text,
        hero_banner      = _url(s.hero_banner),
        about_us         = s.about_us,
    )


@router.get(
    "/settings/",
    auth=_auth,
    response=AdminSiteSettingsOut,
    summary="دریافت تنظیمات سایت (ادمین)",
)
def admin_get_settings(request):
    """تنظیمات کامل سایت را برمی‌گرداند."""
    from core.models import SiteSettings
    return _settings_to_out(SiteSettings.get(), request)


@router.put(
    "/settings/",
    auth=_auth,
    response=AdminSiteSettingsOut,
    summary="بروزرسانی تنظیمات سایت (ادمین)",
)
def admin_update_settings(request, payload: AdminSiteSettingsUpdateIn):
    """
    هر فیلدی که در body ارسال شود (غیر از None) آپدیت می‌شود.
    فیلدهای ارسال‌نشده یا None تغییر نمی‌کنند.
    آپلود لوگو/بنر از این endpoint پشتیبانی نمی‌شود — از /admin Django بارگذاری کنید.
    """
    from core.models import SiteSettings
    s = SiteSettings.get()

    updatable_fields = [
        "site_name", "banner_text", "announcement", "primary_color",
        "maintenance_mode", "social_instagram", "social_telegram",
        "support_phone", "hero_title", "hero_text", "about_us",
    ]
    update_fields = []
    for field in updatable_fields:
        value = getattr(payload, field, None)
        if value is not None:
            setattr(s, field, value)
            update_fields.append(field)

    if update_fields:
        s.save(update_fields=update_fields)

    return _settings_to_out(s, request)
'''

# ─────────────────────────────────────────────────────────────────────────────
# Write all files
# ─────────────────────────────────────────────────────────────────────────────

def main():
    written = []
    for rel_path, content in FILES.items():
        target = BASE / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(str(target))

    print("\n✅  Phase 19 applied successfully!\n")
    print("Files written:")
    for f in written:
        print(f"  ✔  {f}")
    print()
    print("Next steps:")
    print("  1. python manage.py check")
    print("  2. python manage.py makemigrations --check   (must say: No changes detected)")
    print("  3. python manage.py runserver")
    print("  4. Open http://127.0.0.1:8000/api/docs")


if __name__ == "__main__":
    main()
