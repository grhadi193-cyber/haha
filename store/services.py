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
