from typing import List
from ninja import Router
from ninja.security import HttpBearer
from ninja.errors import HttpError
from ninja.responses import Response
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

from django.contrib.auth import get_user_model
from django.http import JsonResponse

from store.schemas import (
    CategoryOut, ProductListOut, ProductDetailOut,
    CreateOrderIn, OrderOut, OrderItemOut,
)
from store.services import (
    get_active_categories, get_active_products, get_product_by_id,
    create_order,
)
from core.exceptions import NotFoundError, InsufficientStockError

User = get_user_model()
router = Router()


# ── JWT Bearer Auth ───────────────────────────────────────────────────────────

class JWTAuth(HttpBearer):
    def authenticate(self, request, token: str):
        try:
            validated = AccessToken(token)
            user_id = validated["user_id"]
            return User.objects.get(pk=user_id, is_active=True)
        except (TokenError, User.DoesNotExist):
            return None


# ── Catalog endpoints (public) ────────────────────────────────────────────────

@router.get("/categories", response=List[CategoryOut], tags=["Store"])
def list_categories(request):
    return list(get_active_categories())


@router.get("/products", response=List[ProductListOut], tags=["Store"])
def list_products(request):
    return list(get_active_products())


@router.get("/products/{product_id}", response=ProductDetailOut, tags=["Store"])
def retrieve_product(request, product_id: int):
    try:
        return get_product_by_id(product_id)
    except NotFoundError as exc:
        raise HttpError(404, str(exc))


# ── Order endpoints (auth required) ──────────────────────────────────────────

def _serialize_order(order) -> OrderOut:
    return OrderOut(
        id=order.pk,
        status=order.status,
        total_amount=order.total_amount,
        shipping_cost=order.shipping_cost,
        created_at=order.created_at,
        items=[
            OrderItemOut(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in order.items.all()
        ],
    )


@router.post("/orders", response=OrderOut, auth=JWTAuth(), tags=["Orders"])
def place_order(request, payload: CreateOrderIn):
    user = request.auth
    try:
        order = create_order(user=user, data=payload)
    except NotFoundError as exc:
        raise HttpError(404, str(exc))
    except InsufficientStockError as exc:
        # HttpError فقط string قبول می‌کنه — مستقیم JsonResponse برمی‌گردونیم
        return JsonResponse(
            {
                "error": "insufficient_stock",
                "product": exc.product_name,
                "available": exc.available,
                "requested": exc.requested,
            },
            status=400,
        )
    return _serialize_order(order)
