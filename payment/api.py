from django.http import JsonResponse
from ninja import Router, Query

from core.auth import AuthBearer
from .schemas import InitiatePaymentIn, InitiatePaymentOut, VerifyCallbackIn
from .orchestrator import start_payment, verify_payment
from store.models import Order
from core.exceptions import NotFoundError

import logging

logger = logging.getLogger(__name__)

router = Router(tags=["Payment"])

_auth = AuthBearer()


@router.post("/initiate", response=InitiatePaymentOut, auth=_auth)
def initiate_payment(request, payload: InitiatePaymentIn):
    """
    Initiate payment for an existing order.
    The order must belong to the authenticated user.
    """
    try:
        order = Order.objects.get(pk=payload.order_id, user=request.auth)
    except Order.DoesNotExist:
        return JsonResponse(
            {"error": True, "code": "not_found", "message": f"سفارش #{payload.order_id} یافت نشد."},
            status=404,
        )

    if order.status == "paid":
        return JsonResponse(
            {"error": True, "code": "already_paid", "message": "این سفارش قبلاً پرداخت شده است."},
            status=400,
        )

    payment_url, transaction_id = start_payment(order)
    return InitiatePaymentOut(payment_url=payment_url, transaction_id=transaction_id)


@router.get("/callback")
def payment_callback(request, params: Query[VerifyCallbackIn]):
    """
    Gateway redirect endpoint.
    Accepts Zarinpal-style ?Authority=...&Status=OK&transaction_id=...

    NOTE: In production, replace the JSON responses here with
    HttpResponseRedirect to your frontend success/failure URLs, e.g.:
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(f"https://yourfrontend.com/payment/success?order={order_id}")
    """
    raw = dict(request.GET)
    raw_flat = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in raw.items()}

    transaction_id = params.transaction_id
    if not transaction_id:
        authority = params.Authority
        if authority and authority.startswith("SANDBOX_"):
            try:
                transaction_id = int(authority.split("_")[1])
            except (IndexError, ValueError):
                return JsonResponse(
                    {"error": True, "code": "invalid_authority", "message": "Cannot resolve transaction from Authority."},
                    status=400,
                )
        else:
            from .models import Transaction
            txn = Transaction.objects.filter(ref_id=authority, status="pending").first()
            if txn is None:
                return JsonResponse(
                    {"error": True, "code": "not_found", "message": "Transaction not found for given Authority."},
                    status=404,
                )
            transaction_id = txn.pk

    success = verify_payment(transaction_id, raw_flat)

    if success:
        return JsonResponse({"status": "paid", "transaction_id": transaction_id})
    return JsonResponse({"status": "failed", "transaction_id": transaction_id}, status=402)
