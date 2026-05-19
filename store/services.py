"""
Store Service Layer.
- No HttpRequest dependency.
- create_order: atomic + select_for_update + triggers payment initiation.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction as db_transaction

from shipping.services import calculate_shipping_cost
from core.exceptions import NotFoundError, InsufficientStockError
from .models import Category, Product, Order, OrderItem

logger = logging.getLogger(__name__)


# ── Catalog ──────────────────────────────────────────────────

def get_active_categories():
    return list(Category.objects.filter(is_active=True).order_by("name"))


def get_active_products():
    return list(Product.objects.filter(is_active=True).select_related("category").order_by("name"))


def get_product_by_id(product_id: int) -> Product:
    try:
        return Product.objects.get(pk=product_id, is_active=True)
    except Product.DoesNotExist:
        raise NotFoundError(f"Product #{product_id} not found.")


# ── Orders ───────────────────────────────────────────────────

def create_order(user, address_id: int, shipping_method_id: int, items: list[dict]) -> dict:
    """
    Creates an Order atomically, then initiates a payment via PaymentGateway.

    Returns a dict with keys: order, payment_url
    """
    from accounts.models import Address

    # Validate address ownership
    try:
        address = Address.objects.get(pk=address_id, user=user)
    except Address.DoesNotExist:
        raise NotFoundError(f"Address #{address_id} not found.")

    # Calculate shipping cost (raises NotFoundError if method not found)
    shipping_cost: Decimal = calculate_shipping_cost(shipping_method_id)

    with db_transaction.atomic():
        # Lock products for stock check
        product_ids = [item["product_id"] for item in items]
        products = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(pk__in=product_ids, is_active=True)
        }

        order_items_data = []
        total_price = Decimal("0")

        for item in items:
            pid = item["product_id"]
            qty = item["quantity"]

            if pid not in products:
                raise NotFoundError(f"Product #{pid} not found or inactive.")

            product = products[pid]

            if product.stock < qty:
                raise InsufficientStockError(
                    product_name=product.name,
                    available=product.stock,
                    requested=qty,
                )

            product.stock -= qty
            product.save(update_fields=["stock"])

            line_total = product.price * qty
            total_price += line_total

            order_items_data.append(
                OrderItem(
                    product=product,
                    quantity=qty,
                    unit_price=product.price,
                )
            )

        total_price += shipping_cost

        order = Order.objects.create(
            user=user,
            address=address,
            shipping_method_id=shipping_method_id,
            shipping_cost=shipping_cost,
            total_price=total_price,
            status="pending",
        )

        for oi in order_items_data:
            oi.order = order

        OrderItem.objects.bulk_create(order_items_data)

    # ── Payment initiation (outside inner atomic to avoid nesting issues) ──
    payment_url: str | None = None
    try:
        from payment.services import PaymentGateway
        payment_url, _txn_id = PaymentGateway.initiate(order)
    except Exception as exc:
        # Payment initiation failure should NOT roll back the order.
        # The order is created; the user can retry payment separately.
        logger.error("[Store] Payment initiation failed for order #%s: %s", order.pk, exc)

    return {"order": order, "payment_url": payment_url}
