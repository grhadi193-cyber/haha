from django.http import JsonResponse
from ninja import Router
from ninja.security import HttpBearer
from typing import List

from .schemas import (
    CategoryOut, ProductListOut, ProductDetailOut,
    CreateOrderIn, OrderOut, OrderItemOut,
)
from .services import get_active_categories, get_active_products, get_product_by_id, create_order
from core.exceptions import NotFoundError, InsufficientStockError

router = Router(tags=["Store"])


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import TokenError
        try:
            validated = AccessToken(token)
            from accounts.models import User
            return User.objects.get(pk=validated["user_id"])
        except (TokenError, Exception):
            return None


@router.get("/categories", response=List[CategoryOut])
def list_categories(request):
    return get_active_categories()


@router.get("/products", response=List[ProductListOut])
def list_products(request):
    return get_active_products()


@router.get("/products/{product_id}", response=ProductDetailOut)
def get_product(request, product_id: int):
    try:
        return get_product_by_id(product_id)
    except NotFoundError as e:
        return JsonResponse({"detail": str(e)}, status=404)


@router.post("/orders", response=OrderOut, auth=AuthBearer())
def create_order_endpoint(request, payload: CreateOrderIn):
    items = [item.dict() for item in payload.items]
    try:
        result = create_order(
            user=request.auth,
            address_id=payload.address_id,
            shipping_method_id=payload.shipping_method_id,
            items=items,
        )
    except NotFoundError as e:
        return JsonResponse({"detail": str(e)}, status=404)
    except InsufficientStockError as e:
        return JsonResponse({"detail": str(e)}, status=400)

    order       = result["order"]
    payment_url = result.get("payment_url")

    order_items_out = [
        OrderItemOut(
            product_id=oi.product_id,
            product_name=oi.product.name,
            quantity=oi.quantity,
            unit_price=oi.unit_price,
        )
        for oi in order.items.select_related("product").all()
    ]

    return OrderOut(
        id=order.pk,
        status=order.status,
        total_price=order.total_price,
        shipping_cost=order.shipping_cost,
        payment_url=payment_url,
        items=order_items_out,
    )
