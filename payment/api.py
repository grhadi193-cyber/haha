from django.http import JsonResponse
from ninja import Router, Query
from ninja.security import HttpBearer

from .schemas import InitiatePaymentIn, InitiatePaymentOut, VerifyCallbackIn
from .orchestrator import start_payment, verify_payment
from store.models import Order
from core.exceptions import NotFoundError

import logging

logger = logging.getLogger(__name__)

router = Router(tags=["Payment"])


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


@router.post("/initiate", response=InitiatePaymentOut, auth=AuthBearer())
def initiate_payment(request, payload: InitiatePaymentIn):
    """
    Initiate payment for an existing order.
    The order must belong to the authenticated user.
    """
    try:
        order = Order.objects.get(pk=payload.order_id, user=request.auth)
    except Order.DoesNotExist:
        raise NotFoundError(f"Order #{payload.order_id} not found.")

    if order.status == "paid":
        return JsonResponse({"detail": "Order is already paid."}, status=400)

    payment_url, transaction_id = start_payment(order)
    return InitiatePaymentOut(payment_url=payment_url, transaction_id=transaction_id)


@router.get("/callback")
def payment_callback(request, params: Query[VerifyCallbackIn]):
    """
    Gateway redirect endpoint.
    Accepts Zarinpal-style ?Authority=...&Status=OK&transaction_id=...
    Returns JSON (Swagger-friendly).  In production you'd redirect to frontend.
    """
    raw = dict(request.GET)
    # Flatten single-value lists that Django query dicts produce
    raw_flat = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in raw.items()}

    transaction_id = params.transaction_id
    if not transaction_id:
        # Try to derive from Authority field stored at initiation
        # For sandbox Authority is SANDBOX_<txn_pk>
        authority = params.Authority
        if authority.startswith("SANDBOX_"):
            try:
                transaction_id = int(authority.split("_")[1])
            except (IndexError, ValueError):
                return JsonResponse({"detail": "Cannot resolve transaction_id from Authority."}, status=400)
        else:
            # Real gateway: look up by ref_id
            from .models import Transaction
            txn = Transaction.objects.filter(ref_id=authority, status="pending").first()
            if txn is None:
                return JsonResponse({"detail": "Transaction not found for given Authority."}, status=404)
            transaction_id = txn.pk

    success = verify_payment(transaction_id, raw_flat)

    if success:
        return JsonResponse({"status": "paid", "transaction_id": transaction_id})
    return JsonResponse({"status": "failed", "transaction_id": transaction_id}, status=402)
