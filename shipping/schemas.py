from decimal import Decimal
from ninja import Schema


from typing import List, Optional

class ShippingMethodOut(Schema):
    id: int
    name: str
    base_cost: Decimal
    cost_per_kg: Decimal
    free_above: Optional[Decimal] = None
    min_days: int
    max_days: int

class ShippingItemIn(Schema):
    product_id: int
    quantity: int

class ShippingOptionIn(Schema):
    province: str
    items: List[ShippingItemIn]

class ShippingOptionOut(Schema):
    id: int
    name: str
    cost: Decimal
    min_days: int
    max_days: int
