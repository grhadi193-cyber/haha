from decimal import Decimal
from ninja import Schema


class ShippingMethodOut(Schema):
    id: int
    name: str
    base_cost: Decimal
