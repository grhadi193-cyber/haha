from decimal import Decimal
from typing import List

from django.db import transaction as db_transaction
from django.db.models import F

from core.exceptions import NotFoundError, InsufficientStockError, AppException
from .models import Order, OrderItem, Product
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
        quantity = item_in["quantity"] if isinstance(item_in, dict) else item_in.quantity
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
        "province": address.province,
        "city": address.city,
        "street": address.street,
        "postal_code": address.postal_code,
        "title": address.title
    }

    order = Order.objects.create(
        user=user,
        address=address,
        shipping_method=method,
        status="pending",
        total_price=total + Decimal(str(shipping_cost)),
        shipping_cost=Decimal(str(shipping_cost)),
        shipping_address_snapshot=shipping_address_snapshot,
    )

    from .models import OrderStatusHistory
    OrderStatusHistory.objects.create(
        order=order, status="pending", note="سفارش ثبت شد", created_by=user
    )

    for product, qty, price in order_items:
        OrderItem.objects.create(
            order=order, product=product, quantity=qty, unit_price=price,
            product_name_snapshot=product.name
        )
        product.stock -= qty
        product.save(update_fields=["stock"])

    return {"order": order, "payment_url": None}


def cancel_order(order_id: int, user) -> Order:
    with db_transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id, user=user)
        if order.status != "pending":
            raise AppException("تنها سفارش‌های در حال تایید قابل لغو هستند.", status_code=400)
        
        for item in order.items.select_related("product"):
            Product.objects.filter(pk=item.product_id).update(
                stock=F("stock") + item.quantity
            )
        
        order.status = "cancelled"
        order.save(update_fields=["status"])
        
        from .models import OrderStatusHistory
        OrderStatusHistory.objects.create(
            order=order, status="cancelled", note="لغو توسط کاربر", created_by=user
        )
    return order


# ── Phase 12 ──────────────────────────────────────────────────────────

def get_user_orders(user) -> List[Order]:
    return list(
        Order.objects.filter(user=user)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )


def get_user_order_detail(user, order_id: int) -> Order:
    try:
        return (
            Order.objects.filter(user=user)
            .prefetch_related("items__product")
            .get(pk=order_id)
        )
    except Order.DoesNotExist:
        raise AppException("سفارش یافت نشد", status_code=404)
