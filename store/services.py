from decimal import Decimal
from django.db import transaction

from store.models import Category, Product, Order, OrderItem
from store.schemas import CreateOrderIn
from core.exceptions import NotFoundError, InsufficientStockError
from shipping.services import calculate_shipping_cost


# ── Catalog ──────────────────────────────────────────────────────────────────

def get_active_categories():
    return Category.objects.filter(is_active=True)


def get_active_products():
    return Product.objects.filter(is_active=True).select_related("category")


def get_product_by_id(product_id: int) -> Product:
    try:
        return Product.objects.select_related("category").get(pk=product_id, is_active=True)
    except Product.DoesNotExist:
        raise NotFoundError(f"Product {product_id} not found.")


# ── Orders ────────────────────────────────────────────────────────────────────

def create_order(user, data: CreateOrderIn) -> Order:
    """
    Create an Order transactionally.

    Steps:
    1. Lock each requested Product row with select_for_update().
    2. Validate stock; raise InsufficientStockError on shortfall.
    3. Calculate shipping cost via shipping.services.
    4. Persist Order + OrderItems; deduct stock.
    5. Return the Order instance (payment handled in Phase 09).
    """
    from accounts.models import Address
    from shipping.models import ShippingMethod

    with transaction.atomic():
        # ── Validate address ownership ────────────────────────────────────
        try:
            address = Address.objects.get(pk=data.address_id, user=user)
        except Address.DoesNotExist:
            raise NotFoundError(f"Address {data.address_id} not found.")

        # ── Validate shipping method ──────────────────────────────────────
        try:
            shipping_method = ShippingMethod.objects.get(pk=data.shipping_method_id, is_active=True)
        except ShippingMethod.DoesNotExist:
            raise NotFoundError(f"ShippingMethod {data.shipping_method_id} not found.")

        # ── Lock & validate each product ──────────────────────────────────
        product_ids = [item.product_id for item in data.items]
        locked_products = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(pk__in=product_ids, is_active=True)
        }

        for item in data.items:
            if item.product_id not in locked_products:
                raise NotFoundError(f"Product {item.product_id} not found.")
            product = locked_products[item.product_id]
            if product.stock < item.quantity:
                raise InsufficientStockError(
                    product_name=product.name,
                    available=product.stock,
                    requested=item.quantity,
                )

        # ── Calculate costs ───────────────────────────────────────────────
        total_weight: Decimal = sum(
            (locked_products[item.product_id].weight or Decimal("0")) * item.quantity
            for item in data.items
        )
        shipping_cost: Decimal = calculate_shipping_cost(
            method_id=shipping_method.pk,
            total_weight=total_weight,
        )

        items_total: Decimal = sum(
            locked_products[item.product_id].price * item.quantity
            for item in data.items
        )
        total_amount: Decimal = items_total + shipping_cost

        # ── Persist Order ─────────────────────────────────────────────────
        order = Order.objects.create(
            user=user,
            address=address,
            shipping_method=shipping_method,
            status=Order.Status.PENDING,
            shipping_cost=shipping_cost,
            total_amount=total_amount,
        )

        # ── Persist OrderItems & deduct stock ─────────────────────────────
        order_items = []
        for item in data.items:
            product = locked_products[item.product_id]
            order_items.append(
                OrderItem(
                    order=order,
                    product=product,
                    quantity=item.quantity,
                    unit_price=product.price,
                )
            )
            product.stock -= item.quantity
            product.save(update_fields=["stock"])

        OrderItem.objects.bulk_create(order_items)

        return order
