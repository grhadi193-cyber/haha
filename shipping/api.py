from typing import List

from ninja import Router

from shipping.schemas import ShippingMethodOut
from shipping.services import get_active_shipping_methods

router = Router(tags=["Shipping"])


@router.get(
    "/methods",
    response=List[ShippingMethodOut],
    summary="List active shipping methods",
)
def list_shipping_methods(request):
    """Return all active shipping methods available for checkout."""
    return get_active_shipping_methods()

from shipping.schemas import ShippingOptionIn, ShippingOptionOut
from store.models import Product
from decimal import Decimal
from shipping.services import calculate_shipping_options

@router.post(
    "/options",
    response=List[ShippingOptionOut],
    summary="Get shipping options based on province and items",
)
def get_shipping_options(request, payload: ShippingOptionIn):
    total_weight = 0.0
    order_total = Decimal("0")
    for item in payload.items:
        try:
            product = Product.objects.get(pk=item.product_id)
            total_weight += float(product.weight) * item.quantity
            price = product.discount_price if product.discount_price else product.price
            order_total += price * item.quantity
        except Product.DoesNotExist:
            continue
    
    return calculate_shipping_options(payload.province, total_weight, order_total)
