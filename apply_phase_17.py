# coding: utf-8
"""
apply_phase_17.py
=================
Phase 17 — Admin API کامل
فقط دو فایل ایجاد/بازنویسی می‌شوند:
  - admin_panel/api.py
  - config/urls.py  (بدون تغییر — فقط برای اطمینان از ثبت router)
"""

import pathlib, textwrap, sys

ROOT = pathlib.Path(__file__).parent
CREATED = []


def write(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    CREATED.append(rel)


# ─────────────────────────────────────────────────────────────────────────────
# admin_panel/api.py
# ─────────────────────────────────────────────────────────────────────────────
write("admin_panel/api.py", '''\
"""
Admin Panel API  —  Phase 17
=============================
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
    results: List[AdminUserOut]


class AdminUserUpdateIn(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class AdminOrderListOut(BaseModel):
    count: int
    page: int
    page_size: int
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
    """صفحه‌بندی ساده روی QuerySet — برمی‌گرداند (total_count, page_qs)."""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    total = qs.count()
    start = (page - 1) * page_size
    return total, qs[start: start + page_size]


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
    """
    qs = User.objects.annotate(order_count=Count("orders")).order_by("-date_joined")
    if search:
        qs = qs.filter(
            Q(phone_number__icontains=search) | Q(full_name__icontains=search)
        )

    total, page_qs = _paginate(qs, page, page_size)

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
    return AdminUserListOut(count=total, page=page, page_size=page_size, results=results)


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
    مثال: GET /api/admin/orders/?status=pending&page=2
    """
    qs = (
        Order.objects.all()
        .prefetch_related("items__product", "history")
        .order_by("-created_at")
    )
    if status:
        qs = qs.filter(status=status)

    total, page_qs = _paginate(qs, page, page_size)

    results = [UserOrderOut.model_validate(o) for o in page_qs]
    return AdminOrderListOut(count=total, page=page, page_size=page_size, results=results)


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
    """
    qs = Product.objects.select_related("category").order_by("-created_at")
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
    if is_active is not None:
        qs = qs.filter(is_active=is_active)

    total, page_qs = _paginate(qs, page, page_size)
    results = [AdminProductOut.model_validate(p) for p in page_qs]
    return AdminProductListOut(count=total, page=page, page_size=page_size, results=results)


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

    paid_orders = Order.objects.filter(status="paid")

    revenue_today = _revenue_for(Order.objects.filter(created_at__gte=today_start))
    revenue_this_week = _revenue_for(Order.objects.filter(created_at__gte=week_start))
    revenue_this_month = _revenue_for(Order.objects.filter(created_at__gte=month_start))

    # تعداد سفارش به تفکیک وضعیت
    status_counts = (
        Order.objects.values("status")
        .annotate(count=Count("id"))
    )
    # پر کردن همه وضعیت‌ها حتی اگر صفر باشند
    all_statuses = [s for s, _ in Order.STATUS_CHOICES]
    status_map = {row["status"]: row["count"] for row in status_counts}
    orders_by_status = {s: status_map.get(s, 0) for s in all_statuses}

    # ۵ محصول پرفروش بر اساس تعداد فروش (از سفارش‌های paid)
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
''')

# ─────────────────────────────────────────────────────────────────────────────
# config/urls.py  — بدون تغییر محتوایی، فقط اطمینان از وجود admin_panel router
# ─────────────────────────────────────────────────────────────────────────────
write("config/urls.py", '''\
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from ninja import NinjaAPI

api = NinjaAPI(title="Shop API", version="1.0.0", docs_url="/docs")

# -- Routers ------------------------------------------------------------------
from core.api        import router as core_router
from accounts.api    import router as accounts_router
from store.api       import router as store_router
from shipping.api    import router as shipping_router
from payment.api     import router as payment_router
from blog.api        import router as blog_router
from admin_panel.api import router as admin_router

api.add_router("/",         core_router)
api.add_router("/auth",     accounts_router)
api.add_router("/",         store_router)
api.add_router("/shipping", shipping_router)
api.add_router("/payment",  payment_router)
api.add_router("/blog",     blog_router)
api.add_router("/admin",    admin_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/",   api.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        from django.urls import include
        import debug_toolbar
        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
''')

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n✅  Phase 17 applied successfully.\n")
print("Files created / updated:")
for f in CREATED:
    print(f"  → {f}")
print()
