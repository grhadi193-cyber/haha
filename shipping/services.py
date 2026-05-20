from decimal import Decimal
from typing import Optional

from core.exceptions import NotFoundError
from shipping.models import ShippingMethod


def get_active_shipping_methods() -> list[ShippingMethod]:
    """Return all active shipping methods ordered by name."""
    return list(ShippingMethod.objects.filter(is_active=True))


def calculate_shipping_options(province: str, total_weight_kg: float, order_total: Decimal) -> list:
    from .models import ShippingZone, ShippingMethod
    zone = ShippingZone.objects.filter(provinces__contains=province).first()
    methods = ShippingMethod.objects.filter(zone=zone, is_active=True)
    results = []
    for m in methods:
        if m.free_above and order_total >= m.free_above:
            cost = Decimal("0")
        else:
            extra_weight = max(0, total_weight_kg - 1)
            cost = m.base_cost + Decimal(str(extra_weight)) * m.cost_per_kg
        results.append({
            "id": m.pk, "name": m.name, "cost": cost,
            "min_days": m.min_days, "max_days": m.max_days,
        })
    return results

def calculate_shipping_cost(
    method_id_or_obj,
    total_weight: Optional[float] = None,
    order_total: Optional[Decimal] = None,
) -> Decimal:
    if isinstance(method_id_or_obj, ShippingMethod):
        method = method_id_or_obj
    else:
        try:
            method = ShippingMethod.objects.get(pk=method_id_or_obj, is_active=True)
        except ShippingMethod.DoesNotExist:
            raise NotFoundError(f"ShippingMethod with id={method_id_or_obj} not found or inactive.")

    if method.free_above and order_total and order_total >= method.free_above:
        return Decimal("0")
        
    cost: Decimal = method.base_cost
    if total_weight is not None:
        extra_weight = max(0, total_weight - 1)
        cost += Decimal(str(extra_weight)) * method.cost_per_kg
    return cost
