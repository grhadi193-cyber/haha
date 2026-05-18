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
