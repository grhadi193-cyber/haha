from decimal import Decimal
from typing import Optional

from core.exceptions import NotFoundError
from shipping.models import ShippingMethod


def get_active_shipping_methods() -> list[ShippingMethod]:
    """Return all active shipping methods ordered by name."""
    return list(ShippingMethod.objects.filter(is_active=True))


def calculate_shipping_cost(
    method_id: int,
    total_weight: Optional[float] = None,
    # future extensibility: add city_id, zone, cart_total, etc.
) -> Decimal:
    """
    Return the shipping cost for the given method.

    MVP: returns base_cost directly.
    Future: weight-based or city/zone-based pricing can be layered here
    without changing the function signature consumed by store/payment.
    """
    try:
        method = ShippingMethod.objects.get(pk=method_id, is_active=True)
    except ShippingMethod.DoesNotExist:
        raise NotFoundError(f"ShippingMethod with id={method_id} not found or inactive.")

    # ── MVP pricing logic ──────────────────────────────────────────────────
    cost: Decimal = method.base_cost

    # ── Future hook: weight-based surcharge ───────────────────────────────
    # if total_weight is not None:
    #     cost += _weight_surcharge(method, total_weight)

    return cost
