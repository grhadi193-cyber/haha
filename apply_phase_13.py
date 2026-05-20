# apply_phase_13.py
# Phase 13 — Order Tracking + OrderStatusHistory
# Windows-compatible, UTF-8, pathlib-based patch script.
# Run from the project root directory (where manage.py lives).

import pathlib, sys

ROOT = pathlib.Path(__file__).parent
CHANGED = []


def write(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    CHANGED.append(rel)


# ─────────────────────────────────────────────────────────────────────────────
# 1. store/services.py
#    Fix: get_user_orders   → prefetch "history"
#    Fix: get_user_order_detail → prefetch "history"
#    New: update_order_status() service  (used by admin_panel)
#    All other logic unchanged.
# ─────────────────────────────────────────────────────────────────────────────
write("store/services.py", '''\
from decimal import Decimal
from typing import List

from django.db import transaction as db_transaction
from django.db.models import F

from core.exceptions import NotFoundError, InsufficientStockError, AppException
from .models import Order, OrderItem, OrderStatusHistory, Product
from accounts.models import Address
from shipping.models import ShippingMethod
from shipping.services import calculate_shipping_cost


def get_active_categories():
    from .models import Category
    return list(Category.objects.filter(is_active=True))


def get_active_products():
    return list(Product.objects.select_related("category").filter(is_active=True))


def get_product_by_id(product_id: int) -> Product:
    try:
        return Product.objects.select_related("category").get(pk=product_id, is_active=True)
    except Product.DoesNotExist:
        raise NotFoundError(f"Product {product_id} not found")


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
            f"وضعیت نامعتبر است. مقادیر مجاز: {', '.join(valid_statuses)}",
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

        # اگر shipped شد، shipped_at را ثبت کن
        if new_status == "shipped" and not order.shipped_at:
            from django.utils import timezone
            order.shipped_at = timezone.now()
            update_fields.append("shipped_at")

        # اگر delivered شد، delivered_at را ثبت کن
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
''')


# ─────────────────────────────────────────────────────────────────────────────
# 2. accounts/api.py
#    Add: DELETE /orders/{order_id}  (cancel order)
#    All other endpoints unchanged.
# ─────────────────────────────────────────────────────────────────────────────
write("accounts/api.py", '''\
from typing import List
from ninja import Router
from django.http import JsonResponse

from core.exceptions import AppException
from .schemas import (
    SendOTPIn, VerifyOTPIn, TokenOut,
    AddressIn, AddressOut,
    ProfileOut, UpdateProfileIn,
)
from . import services as svc

router = Router(tags=["Auth"])


def _get_auth_bearer():
    from store.api import AuthBearer
    return AuthBearer()


_auth = _get_auth_bearer()


@router.post("/send-otp", auth=None, summary="ارسال کد OTP")
def send_otp(request, payload: SendOTPIn):
    try:
        svc.send_otp(payload.phone_number)
    except AppException as e:
        return JsonResponse({"detail": e.detail}, status=e.status_code)
    return {"detail": "کد تایید ارسال شد"}


@router.post("/verify-otp", auth=None, response=TokenOut, summary="تایید OTP و دریافت توکن")
def verify_otp(request, payload: VerifyOTPIn):
    from rest_framework_simplejwt.tokens import RefreshToken
    try:
        user = svc.verify_otp(payload.phone_number, payload.code)
    except AppException as e:
        return JsonResponse({"detail": e.detail}, status=e.status_code)
    refresh = RefreshToken.for_user(user)
    return TokenOut(access=str(refresh.access_token), refresh=str(refresh))


@router.get("/addresses", auth=_auth, response=List[AddressOut], summary="لیست آدرس‌ها")
def list_addresses(request):
    return svc.get_addresses(request.auth)


@router.post("/addresses", auth=_auth, response=AddressOut, summary="افزودن آدرس")
def create_address(request, payload: AddressIn):
    return svc.create_address(
        request.auth,
        payload.title,
        payload.province,
        payload.city,
        payload.street,
        payload.postal_code,
        payload.is_default,
    )


@router.delete("/addresses/{address_id}", auth=_auth, summary="حذف آدرس")
def delete_address(request, address_id: int):
    try:
        svc.delete_address(request.auth, address_id)
    except AppException as e:
        return JsonResponse({"detail": e.detail}, status=e.status_code)
    return {"detail": "آدرس حذف شد"}


@router.get("/profile", auth=_auth, response=ProfileOut, summary="دریافت پروفایل کاربر")
def get_profile(request):
    return svc.get_profile(request.auth)


@router.patch("/profile", auth=_auth, response=ProfileOut, summary="ویرایش پروفایل کاربر")
def update_profile(request, payload: UpdateProfileIn):
    try:
        return svc.update_profile(
            request.auth,
            payload.full_name,
            payload.email,
            payload.national_id,
        )
    except AppException as e:
        return JsonResponse({"detail": e.detail}, status=e.status_code)


@router.get("/orders", auth=_auth, summary="لیست سفارش‌های کاربر")
def my_orders(request):
    from store.services import get_user_orders
    from store.schemas import UserOrderOut
    orders = get_user_orders(request.auth)
    return [UserOrderOut.model_validate(o) for o in orders]


@router.get("/orders/{order_id}", auth=_auth, summary="جزئیات سفارش کاربر")
def my_order_detail(request, order_id: int):
    from store.services import get_user_order_detail
    from store.schemas import UserOrderOut
    try:
        order = get_user_order_detail(request.auth, order_id)
    except AppException as e:
        return JsonResponse({"detail": e.detail}, status=e.status_code)
    return UserOrderOut.model_validate(order)


@router.delete("/orders/{order_id}", auth=_auth, summary="لغو سفارش توسط کاربر")
def cancel_my_order(request, order_id: int):
    """
    لغو سفارش — فقط سفارش‌های با وضعیت «pending» قابل لغو هستند.
    موجودی محصولات به صورت خودکار برگشت داده می‌شود.
    """
    from store.services import cancel_order
    try:
        cancel_order(order_id=order_id, user=request.auth)
    except AppException as e:
        return JsonResponse({"detail": e.detail}, status=e.status_code)
    return {"detail": "سفارش با موفقیت لغو شد"}
''')


# ─────────────────────────────────────────────────────────────────────────────
# 3. admin_panel/api.py
#    Fix: update_order_status now delegates to store.services.update_order_status
#         which records OrderStatusHistory correctly.
#    All other endpoints unchanged.
# ─────────────────────────────────────────────────────────────────────────────
write("admin_panel/api.py", '''\
from typing import List
from ninja import Router
from ninja.security import HttpBearer
from django.http import JsonResponse
from pydantic import BaseModel

from accounts.models import User
from store.models import Order
from store.schemas import UserOrderOut

router = Router(tags=["Admin"])


class AdminBearer(HttpBearer):
    def authenticate(self, request, token):
        from rest_framework_simplejwt.tokens import AccessToken
        try:
            acc = AccessToken(token)
            user = User.objects.get(pk=acc["user_id"])
            if not user.is_staff:
                return None
            return user
        except Exception:
            return None


_auth = AdminBearer()


class DashboardOut(BaseModel):
    total_users: int
    total_orders: int
    total_revenue: int


@router.get("/dashboard", auth=_auth, response=DashboardOut, summary="داشبورد ادمین")
def admin_dashboard(request):
    from django.db.models import Sum
    total_users   = User.objects.count()
    total_orders  = Order.objects.count()
    revenue_agg   = Order.objects.filter(status="paid").aggregate(total=Sum("total_price"))
    total_revenue = int(revenue_agg["total"] or 0)
    return DashboardOut(
        total_users=total_users,
        total_orders=total_orders,
        total_revenue=total_revenue,
    )


@router.get("/orders", auth=_auth, response=List[UserOrderOut], summary="لیست سفارش‌ها (ادمین)")
def admin_orders(request):
    orders = (
        Order.objects.all()
        .prefetch_related("items__product", "history")
        .order_by("-created_at")
    )
    return [UserOrderOut.model_validate(o) for o in orders]


class UpdateOrderStatusIn(BaseModel):
    status: str
    tracking_number: str = ""
    postal_tracking: str = ""
    note: str = ""


@router.put(
    "/orders/{order_id}/status",
    auth=_auth,
    summary="تغییر وضعیت سفارش (ادمین)",
)
def update_order_status(request, order_id: int, payload: UpdateOrderStatusIn):
    """
    تغییر وضعیت سفارش توسط ادمین.
    یک رکورد در OrderStatusHistory با اطلاعات ادمین ثبت می‌کند.
    اگر وضعیت shipped شود، shipped_at خودکار ثبت می‌شود.
    اگر وضعیت delivered شود، delivered_at خودکار ثبت می‌شود.
    """
    from store.services import update_order_status as svc_update
    from core.exceptions import AppException
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
        return JsonResponse({"detail": e.detail}, status=e.status_code)
    return {"detail": "وضعیت سفارش با موفقیت تغییر کرد"}
''')


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n✅  Phase 13 applied successfully.\n")
print("Files written:")
for f in CHANGED:
    print(f"   ✔  {f}")

print("""
─────────────────────────────────────────────────────
Next steps (TEST_PROTOCOL):
  1.  python manage.py check
  2.  python manage.py makemigrations --check   ← must say "No changes"
  3.  python manage.py migrate
  4.  python manage.py runserver
  5.  Open http://127.0.0.1:8000/api/docs
─────────────────────────────────────────────────────
""")
