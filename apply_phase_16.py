# apply_phase_16.py
# Phase 16 — Payment Refactor (Orchestrator + Providers)
# Run from the project root (next to "New folder (11)"):
#   python apply_phase_16.py

import pathlib

ROOT = pathlib.Path(__file__).parent
PROJ = ROOT / "New folder (11)"


def write(rel: str, content: str) -> None:
    p = PROJ / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"  [OK] {rel}")


print("=" * 60)
print("Phase 16 — Payment Refactor (Orchestrator + Providers)")
print("=" * 60)

# ---------------------------------------------------------------------------
# payment/providers/base.py
# ---------------------------------------------------------------------------
write("payment/providers/base.py", """\
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PaymentSession:
    payment_url: str
    transaction_id: int
    provider: str


class BasePaymentProvider(ABC):
    @abstractmethod
    def initiate(self, transaction) -> str:
        \"\"\"Initiates the payment and returns a payment_url.
        May mutate transaction.ref_id and transaction.gateway_response.
        \"\"\"

    @abstractmethod
    def verify(self, transaction, raw_params: dict) -> bool:
        \"\"\"Verifies a payment callback. Returns True if payment succeeded.
        May mutate transaction.ref_id and transaction.gateway_response.
        \"\"\"

    @property
    @abstractmethod
    def name(self) -> str:
        \"\"\"Unique identifier string for this provider (stored in Transaction.provider).\"\"\"
        ...
""")

# ---------------------------------------------------------------------------
# payment/providers/mock.py
# ---------------------------------------------------------------------------
write("payment/providers/mock.py", """\
import logging
from .base import BasePaymentProvider

logger = logging.getLogger(__name__)


class MockProvider(BasePaymentProvider):
    \"\"\"Instant-success mock provider for DEBUG mode.
    Generates a local callback URL so the full payment flow can be tested
    without any real gateway.
    \"\"\"

    @property
    def name(self) -> str:
        return "mock"

    def initiate(self, transaction) -> str:
        txn_id = transaction.pk
        transaction.ref_id = f"MOCK-{txn_id}"
        transaction.gateway_response = {
            "mock": True,
            "note": "DEBUG mode — no real gateway called",
        }
        callback_url = (
            f"http://127.0.0.1:8000/api/payment/mock-callback"
            f"?txn_id={txn_id}&status=OK"
        )
        logger.debug("[MockProvider] Fake payment URL: %s", callback_url)
        return callback_url

    def verify(self, transaction, raw_params: dict) -> bool:
        status = raw_params.get("status", "")
        success = status == "OK"
        transaction.ref_id = f"MOCK-{transaction.pk}"
        transaction.gateway_response = {
            **transaction.gateway_response,
            "verify_params": raw_params,
            "mock": True,
            "success": success,
        }
        logger.debug("[MockProvider] verify result=%s params=%s", success, raw_params)
        return success
""")

# ---------------------------------------------------------------------------
# payment/providers/zarinpal.py
# ---------------------------------------------------------------------------
write("payment/providers/zarinpal.py", """\
import logging
from decimal import Decimal

import requests
from django.conf import settings

from .base import BasePaymentProvider

logger = logging.getLogger(__name__)

# Zarinpal sandbox endpoints
_SANDBOX_REQUEST = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
_SANDBOX_VERIFY  = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
_SANDBOX_START   = "https://sandbox.zarinpal.com/pg/StartPay/{authority}"

# Zarinpal production endpoints
_PROD_REQUEST = "https://payment.zarinpal.com/pg/v4/payment/request.json"
_PROD_VERIFY  = "https://payment.zarinpal.com/pg/v4/payment/verify.json"
_PROD_START   = "https://payment.zarinpal.com/pg/StartPay/{authority}"


class ZarinpalProvider(BasePaymentProvider):
    \"\"\"Zarinpal payment gateway using direct REST API calls (no third-party SDK).
    Supports both sandbox and production modes via PAYMENT_SANDBOX setting.
    \"\"\"

    @property
    def name(self) -> str:
        return "zarinpal"

    def _is_sandbox(self) -> bool:
        return getattr(settings, "PAYMENT_SANDBOX", True)

    def _merchant(self) -> str:
        return getattr(settings, "ZARINPAL_MERCHANT_CODE", "SANDBOX")

    def _callback_url(self) -> str:
        base = getattr(settings, "PAYMENT_CALLBACK_BASE_URL", "http://127.0.0.1:8000")
        return f"{base}/api/payment/callback"

    def initiate(self, transaction) -> str:
        amount_irt   = int(Decimal(str(transaction.amount)))  # Toman
        amount_rials = amount_irt * 10                         # Zarinpal uses Rials

        request_url = _SANDBOX_REQUEST if self._is_sandbox() else _PROD_REQUEST
        start_tpl   = _SANDBOX_START   if self._is_sandbox() else _PROD_START

        payload = {
            "merchant_id":  self._merchant(),
            "amount":        amount_rials,
            "callback_url":  self._callback_url(),
            "description":   f"\\u067e\\u0631\\u062f\\u0627\\u062e\\u062a \\u0633\\u0641\\u0627\\u0631\\u0634 #{transaction.order_id}",
            "mobile":        transaction.order.user.phone_number,
            "order_id":      str(transaction.order_id),
        }

        try:
            resp = requests.post(request_url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("[Zarinpal] Request failed: %s", exc)
            raise RuntimeError(f"Zarinpal initiate error: {exc}") from exc

        if data.get("data", {}).get("code") != 100:
            errors = data.get("errors") or data.get("data", {})
            logger.error("[Zarinpal] Initiate rejected: %s", errors)
            raise RuntimeError(f"Zarinpal rejected payment request: {errors}")

        authority   = data["data"]["authority"]
        payment_url = start_tpl.format(authority=authority)

        transaction.ref_id = authority
        transaction.gateway_response = {
            "authority": authority,
            "sandbox":   self._is_sandbox(),
            "raw":       data,
        }

        logger.info(
            "[Zarinpal] Initiated — authority=%s order=%s",
            authority, transaction.order_id,
        )
        return payment_url

    def verify(self, transaction, raw_params: dict) -> bool:
        authority = raw_params.get("Authority") or transaction.ref_id
        status    = raw_params.get("Status", "")

        if status != "OK":
            logger.warning("[Zarinpal] Callback status not OK: %s", status)
            transaction.gateway_response = {
                **transaction.gateway_response,
                "verify_params": raw_params,
                "cancelled": True,
            }
            return False

        amount_rials = int(Decimal(str(transaction.amount))) * 10
        verify_url   = _SANDBOX_VERIFY if self._is_sandbox() else _PROD_VERIFY

        payload = {
            "merchant_id": self._merchant(),
            "amount":      amount_rials,
            "authority":   authority,
        }

        try:
            resp = requests.post(verify_url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("[Zarinpal] Verify request failed: %s", exc)
            raise RuntimeError(f"Zarinpal verify error: {exc}") from exc

        code    = data.get("data", {}).get("code")
        ref_id  = data.get("data", {}).get("ref_id", "")
        success = code in (100, 101)  # 101 = already verified (idempotent)

        transaction.ref_id = str(ref_id) if ref_id else authority
        transaction.gateway_response = {
            **transaction.gateway_response,
            "verify_params":    raw_params,
            "verify_response":  data,
            "ref_id":           ref_id,
            "code":             code,
        }

        if success:
            logger.info(
                "[Zarinpal] Verified — ref_id=%s order=%s",
                ref_id, transaction.order_id,
            )
        else:
            logger.warning(
                "[Zarinpal] Verify failed — code=%s order=%s",
                code, transaction.order_id,
            )

        return success
""")

# ---------------------------------------------------------------------------
# payment/providers/__init__.py
# ---------------------------------------------------------------------------
write("payment/providers/__init__.py", """\
from .mock import MockProvider
from .zarinpal import ZarinpalProvider

__all__ = ["MockProvider", "ZarinpalProvider"]
""")

# ---------------------------------------------------------------------------
# payment/orchestrator.py
# ---------------------------------------------------------------------------
write("payment/orchestrator.py", """\
\"\"\"
Payment Orchestrator
====================
Coordinates Transaction creation, provider calls, and post-payment side-effects.
Must NOT import HttpRequest.  Called from payment/api.py and tests.
\"\"\"
import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction as db_transaction

from store.models import Order, OrderStatusHistory
from sms.services import send_order_success_sms
from .models import Transaction
from .providers import MockProvider, ZarinpalProvider
from .providers.base import BasePaymentProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider Factory
# ---------------------------------------------------------------------------

def get_provider(name: str) -> BasePaymentProvider:
    \"\"\"Returns the correct provider instance.
    In DEBUG mode always returns MockProvider regardless of name.
    \"\"\"
    if settings.DEBUG:
        return MockProvider()
    if name == "zarinpal":
        return ZarinpalProvider()
    return ZarinpalProvider()


# ---------------------------------------------------------------------------
# Start Payment
# ---------------------------------------------------------------------------

def start_payment(order: Order, provider_name: str = "zarinpal") -> tuple[str, int]:
    \"\"\"Creates a Transaction, calls provider.initiate, returns (payment_url, txn_pk).

    On provider failure: marks transaction as FAILED, logs, re-raises.
    \"\"\"
    provider = get_provider(provider_name)

    amount = Decimal(str(order.total_price))
    txn = Transaction.objects.create(
        order=order,
        amount=amount,
        status=Transaction.Status.PENDING,
        provider=provider.name,
    )

    try:
        payment_url = provider.initiate(txn)
        # provider may have mutated txn.ref_id and txn.gateway_response
        txn.save(update_fields=["ref_id", "gateway_response"])
        logger.info(
            "[Orchestrator] Payment initiated — txn=%s order=%s provider=%s",
            txn.pk, order.pk, provider.name,
        )
        return payment_url, txn.pk
    except Exception as exc:
        txn.status = Transaction.Status.FAILED
        txn.gateway_response = {"error": str(exc)}
        txn.save(update_fields=["status", "gateway_response"])
        logger.exception(
            "[Orchestrator] Initiate failed — txn=%s order=%s", txn.pk, order.pk,
        )
        raise


# ---------------------------------------------------------------------------
# Verify Payment
# ---------------------------------------------------------------------------

def verify_payment(transaction_id: int, raw_params: dict) -> bool:
    \"\"\"Idempotent payment verification.

    - Already SUCCESS -> return True immediately (no duplicate side-effects).
    - Already FAILED  -> return False immediately.
    - PENDING         -> call provider.verify inside atomic block.
                         On success call _mark_order_paid().
    \"\"\"
    try:
        txn = Transaction.objects.select_for_update().get(pk=transaction_id)
    except Transaction.DoesNotExist:
        logger.error(
            "[Orchestrator] verify() called with unknown transaction_id=%s",
            transaction_id,
        )
        return False

    # Idempotency guard
    if txn.status == Transaction.Status.SUCCESS:
        logger.info("[Orchestrator] Transaction %s already SUCCESS — skipping.", transaction_id)
        return True
    if txn.status == Transaction.Status.FAILED:
        logger.info("[Orchestrator] Transaction %s already FAILED — skipping.", transaction_id)
        return False

    provider = get_provider(txn.provider)

    try:
        with db_transaction.atomic():
            success = provider.verify(txn, raw_params)
            txn.status = Transaction.Status.SUCCESS if success else Transaction.Status.FAILED
            txn.save(update_fields=["status", "ref_id", "gateway_response"])

            if success:
                _mark_order_paid(txn)

        logger.info(
            "[Orchestrator] Verify complete — txn=%s success=%s",
            transaction_id, success,
        )
        return success

    except Exception as exc:
        txn.status = Transaction.Status.FAILED
        txn.gateway_response = {**txn.gateway_response, "verify_error": str(exc)}
        txn.save(update_fields=["status", "gateway_response"])
        logger.exception("[Orchestrator] Verify raised — txn=%s", transaction_id)
        return False


# ---------------------------------------------------------------------------
# Post-Payment
# ---------------------------------------------------------------------------

def _mark_order_paid(txn: Transaction) -> None:
    \"\"\"Marks the linked order as paid, writes OrderStatusHistory, sends SMS.
    Must be called inside an atomic block.
    \"\"\"
    order = Order.objects.select_for_update().get(pk=txn.order_id)

    if order.status == "paid":
        # Already paid — idempotent, nothing to do
        return

    order.status = "paid"
    order.save(update_fields=["status"])

    OrderStatusHistory.objects.create(
        order=order,
        status="paid",
        note=f"\\u067e\\u0631\\u062f\\u0627\\u062e\\u062a \\u0645\\u0648\\u0641\\u0642 \\u2014 \\u062a\\u0631\\u0627\\u06a9\\u0646\\u0634 #{txn.pk} | ref: {txn.ref_id}",
        created_by=None,
    )

    try:
        send_order_success_sms(
            phone_number=order.user.phone_number,
            order_id=order.pk,
        )
    except Exception as sms_exc:
        # SMS failure must never roll back a successful payment
        logger.error(
            "[Orchestrator] SMS failed after payment — order=%s error=%s",
            order.pk, sms_exc,
        )
""")

# ---------------------------------------------------------------------------
# payment/services.py
# ---------------------------------------------------------------------------
write("payment/services.py", """\
# Payment services have been decoupled into orchestrator and providers.
# See payment/orchestrator.py  ->  start_payment(), verify_payment()
# See payment/providers/       ->  MockProvider, ZarinpalProvider
""")

# ---------------------------------------------------------------------------
# payment/api.py
# ---------------------------------------------------------------------------
write("payment/api.py", """\
\"\"\"
Payment API
===========
POST /api/payment/initiate       -- start payment for an order
GET  /api/payment/callback       -- Zarinpal callback (production)
GET  /api/payment/mock-callback  -- mock callback (DEBUG only)
\"\"\"
import logging

from django.conf import settings
from django.http import JsonResponse
from ninja import Router, Query
from ninja.security import HttpBearer

from core.exceptions import NotFoundError
from store.models import Order
from .orchestrator import start_payment, verify_payment
from .schemas import InitiatePaymentIn, InitiatePaymentOut, VerifyCallbackIn

logger = logging.getLogger(__name__)

router = Router(tags=["Payment"])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# POST /api/payment/initiate
# ---------------------------------------------------------------------------

@router.post(
    "/initiate",
    response=InitiatePaymentOut,
    auth=AuthBearer(),
    summary="\\u0634\\u0631\\u0648\\u0639 \\u067e\\u0631\\u062f\\u0627\\u062e\\u062a",
)
def initiate_payment(request, payload: InitiatePaymentIn):
    \"\"\"\\u0634\\u0631\\u0648\\u0639 \\u0641\\u0631\\u0622\\u06cc\\u0646\\u062f \\u067e\\u0631\\u062f\\u0627\\u062e\\u062a \\u0628\\u0631\\u0627\\u06cc \\u06cc\\u06a9 \\u0633\\u0641\\u0627\\u0631\\u0634.
    \\u0633\\u0641\\u0627\\u0631\\u0634 \\u0628\\u0627\\u06cc\\u062f \\u0645\\u062a\\u0639\\u0644\\u0642 \\u0628\\u0647 \\u06a9\\u0627\\u0631\\u0628\\u0631 \\u0627\\u062d\\u0631\\u0627\\u0632 \\u0647\\u0648\\u06cc\\u062a\\u200c\\u0634\\u062f\\u0647 \\u0628\\u0627\\u0634\\u062f.
    \\u062f\\u0631 DEBUG: payment_url \\u0628\\u0647 mock-callback \\u0627\\u0634\\u0627\\u0631\\u0647 \\u0645\\u06cc\\u200c\\u06a9\\u0646\\u062f.
    \"\"\"
    try:
        order = Order.objects.get(pk=payload.order_id, user=request.auth)
    except Order.DoesNotExist:
        raise NotFoundError(f"\\u0633\\u0641\\u0627\\u0631\\u0634 #{payload.order_id} \\u06cc\\u0627\\u0641\\u062a \\u0646\\u0634\\u062f.")

    if order.status == "paid":
        return JsonResponse(
            {
                "error": True,
                "code": "already_paid",
                "message": "\\u0627\\u06cc\\u0646 \\u0633\\u0641\\u0627\\u0631\\u0634 \\u0642\\u0628\\u0644\\u0627\\u064b \\u067e\\u0631\\u062f\\u0627\\u062e\\u062a \\u0634\\u062f\\u0647 \\u0627\\u0633\\u062a.",
            },
            status=400,
        )

    try:
        payment_url, transaction_id = start_payment(order)
    except Exception:
        logger.exception("[API] start_payment failed for order=%s", payload.order_id)
        return JsonResponse(
            {
                "error": True,
                "code": "gateway_error",
                "message": "\\u062e\\u0637\\u0627 \\u062f\\u0631 \\u0627\\u062a\\u0635\\u0627\\u0644 \\u0628\\u0647 \\u062f\\u0631\\u06af\\u0627\\u0647 \\u067e\\u0631\\u062f\\u0627\\u062e\\u062a.",
            },
            status=502,
        )

    return InitiatePaymentOut(payment_url=payment_url, transaction_id=transaction_id)


# ---------------------------------------------------------------------------
# GET /api/payment/callback  (Zarinpal production callback)
# ---------------------------------------------------------------------------

@router.get(
    "/callback",
    summary="\\u06a9\\u0627\\u0644\\u200c\\u0628\\u06a9 \\u062f\\u0631\\u06af\\u0627\\u0647 \\u0632\\u0631\\u06cc\\u0646\\u200c\\u067e\\u0627\\u0644",
)
def payment_callback(request, params: Query[VerifyCallbackIn]):
    \"\"\"Callback endpoint for Zarinpal (and compatible gateways).
    Accepts: ?Authority=...&Status=OK&transaction_id=...
    Returns JSON.  In production redirect to the frontend instead.
    \"\"\"
    raw = {
        k: (v[0] if isinstance(v, list) and len(v) == 1 else v)
        for k, v in request.GET.items()
    }

    transaction_id = params.transaction_id

    if not transaction_id:
        authority = params.Authority or ""
        if authority.startswith("MOCK-"):
            try:
                transaction_id = int(authority.split("-")[1])
            except (IndexError, ValueError):
                return JsonResponse(
                    {"error": True, "code": "bad_authority", "message": "Authority \\u0646\\u0627\\u0645\\u0639\\u062a\\u0628\\u0631 \\u0627\\u0633\\u062a."},
                    status=400,
                )
        elif authority:
            from .models import Transaction
            txn = Transaction.objects.filter(ref_id=authority, status="pending").first()
            if txn is None:
                return JsonResponse(
                    {"error": True, "code": "not_found", "message": "\\u062a\\u0631\\u0627\\u06a9\\u0646\\u0634 \\u06cc\\u0627\\u0641\\u062a \\u0646\\u0634\\u062f."},
                    status=404,
                )
            transaction_id = txn.pk
        else:
            return JsonResponse(
                {
                    "error": True,
                    "code": "missing_params",
                    "message": "\\u067e\\u0627\\u0631\\u0627\\u0645\\u062a\\u0631 transaction_id \\u06cc\\u0627 Authority \\u0627\\u0644\\u0632\\u0627\\u0645\\u06cc \\u0627\\u0633\\u062a.",
                },
                status=400,
            )

    success = verify_payment(transaction_id, raw)

    if success:
        return JsonResponse({"status": "paid", "transaction_id": transaction_id})
    return JsonResponse({"status": "failed", "transaction_id": transaction_id}, status=402)


# ---------------------------------------------------------------------------
# GET /api/payment/mock-callback  (DEBUG only)
# ---------------------------------------------------------------------------

@router.get(
    "/mock-callback",
    summary="\\u06a9\\u0627\\u0644\\u200c\\u0628\\u06a9 \\u0645\\u0635\\u0646\\u0648\\u0639\\u06cc (\\u0641\\u0642\\u0637 DEBUG)",
)
def mock_callback(request):
    \"\"\"DEBUG-only endpoint. Simulates a payment callback without a real gateway.
    Query params: ?txn_id=<int>&status=OK
    Returns 404 in production.
    \"\"\"
    if not settings.DEBUG:
        return JsonResponse(
            {
                "error": True,
                "code": "not_found",
                "message": "\\u0627\\u06cc\\u0646 endpoint \\u0641\\u0642\\u0637 \\u062f\\u0631 \\u0645\\u062d\\u06cc\\u0637 \\u062a\\u0648\\u0633\\u0639\\u0647 \\u062f\\u0631 \\u062f\\u0633\\u062a\\u0631\\u0633 \\u0627\\u0633\\u062a.",
            },
            status=404,
        )

    try:
        txn_id = int(request.GET.get("txn_id", 0))
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": True, "code": "invalid_params", "message": "\\u067e\\u0627\\u0631\\u0627\\u0645\\u062a\\u0631 txn_id \\u0628\\u0627\\u06cc\\u062f \\u0639\\u062f\\u062f \\u0635\\u062d\\u06cc\\u062d \\u0628\\u0627\\u0634\\u062f."},
            status=400,
        )

    if not txn_id:
        return JsonResponse(
            {"error": True, "code": "missing_params", "message": "\\u067e\\u0627\\u0631\\u0627\\u0645\\u062a\\u0631 txn_id \\u0627\\u0644\\u0632\\u0627\\u0645\\u06cc \\u0627\\u0633\\u062a."},
            status=400,
        )

    status_param = request.GET.get("status", "")
    raw_params   = {"txn_id": str(txn_id), "status": status_param}

    success = verify_payment(txn_id, raw_params)

    if success:
        return JsonResponse({
            "status":         "paid",
            "transaction_id": txn_id,
            "message":        "\\u067e\\u0631\\u062f\\u0627\\u062e\\u062a \\u0622\\u0632\\u0645\\u0627\\u06cc\\u0634\\u06cc \\u0628\\u0627 \\u0645\\u0648\\u0641\\u0642\\u06cc\\u062a \\u0627\\u0646\\u062c\\u0627\\u0645 \\u0634\\u062f.",
        })
    return JsonResponse({
        "status":         "failed",
        "transaction_id": txn_id,
        "message":        "\\u067e\\u0631\\u062f\\u0627\\u062e\\u062a \\u0622\\u0632\\u0645\\u0627\\u06cc\\u0634\\u06cc \\u0646\\u0627\\u0645\\u0648\\u0641\\u0642 \\u0628\\u0648\\u062f.",
    }, status=402)
""")

# ---------------------------------------------------------------------------
# store/services.py
# ---------------------------------------------------------------------------
write("store/services.py", """\
from decimal import Decimal
from typing import List

from django.db import transaction as db_transaction
from django.db.models import F

from core.exceptions import NotFoundError, InsufficientStockError, AppException
from .models import Order, OrderItem, OrderStatusHistory, Product
from accounts.models import Address
from shipping.models import ShippingMethod
from shipping.services import calculate_shipping_cost


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

def get_active_categories():
    from .models import Category
    return list(Category.objects.filter(is_active=True))


def get_active_products():
    return list(
        Product.objects.select_related("category")
        .filter(is_active=True)
        .order_by("-created_at")
    )


def get_product_by_id(product_id: int) -> Product:
    try:
        product = (
            Product.objects
            .select_related("category")
            .prefetch_related("images")
            .get(pk=product_id, is_active=True)
        )
    except Product.DoesNotExist:
        raise NotFoundError(f"Product {product_id} not found")

    Product.objects.filter(pk=product_id).update(view_count=F("view_count") + 1)
    product.view_count += 1
    return product


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

def create_order(user, address_id: int, shipping_method_id: int, items: list) -> dict:
    \"\"\"Create a new order and initiate payment.

    Flow:
    1. Validate address, shipping method, products and stock.
    2. Calculate shipping cost.
    3. Create Order + OrderItems inside atomic block; deduct stock.
    4. Call start_payment() outside the main atomic block so a gateway
       failure does not roll back the order.  Users can retry via
       POST /api/payment/initiate if payment_url is None.

    Returns {"order": order, "payment_url": str | None}
    \"\"\"
    try:
        address = Address.objects.get(pk=address_id, user=user)
    except Address.DoesNotExist:
        raise NotFoundError("Address not found")

    try:
        method = ShippingMethod.objects.get(pk=shipping_method_id, is_active=True)
    except ShippingMethod.DoesNotExist:
        raise NotFoundError("Shipping method not found")

    if not items:
        raise AppException("\\u0633\\u0628\\u062f \\u062e\\u0631\\u06cc\\u062f \\u062e\\u0627\\u0644\\u06cc \\u0627\\u0633\\u062a", status_code=400)

    order_items = []
    total = Decimal("0")

    for item_in in items:
        product_id = item_in["product_id"] if isinstance(item_in, dict) else item_in.product_id
        quantity   = item_in["quantity"]   if isinstance(item_in, dict) else item_in.quantity
        try:
            product = Product.objects.get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundError(f"Product {product_id} not found")

        if product.stock < quantity:
            raise InsufficientStockError(product.name, product.stock, quantity)

        order_items.append((product, quantity, product.price))
        total += product.price * quantity

    shipping_cost = calculate_shipping_cost(method)

    shipping_address_snapshot = {
        "province":    address.province,
        "city":        address.city,
        "street":      address.street,
        "postal_code": address.postal_code,
        "title":       address.title,
    }

    with db_transaction.atomic():
        order = Order.objects.create(
            user=user,
            address=address,
            shipping_method=method,
            status="pending",
            total_price=total + Decimal(str(shipping_cost)),
            shipping_cost=Decimal(str(shipping_cost)),
            shipping_address_snapshot=shipping_address_snapshot,
        )

        OrderStatusHistory.objects.create(
            order=order,
            status="pending",
            note="\\u0633\\u0641\\u0627\\u0631\\u0634 \\u062b\\u0628\\u062a \\u0634\\u062f",
            created_by=user,
        )

        for product, qty, price in order_items:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=qty,
                unit_price=price,
                product_name_snapshot=product.name,
            )
            Product.objects.filter(pk=product.pk).update(stock=F("stock") - qty)

    # Initiate payment outside the main atomic block.
    # A gateway failure does not roll back the saved order.
    payment_url = None
    try:
        from payment.orchestrator import start_payment
        payment_url, _txn_id = start_payment(order)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "[store.create_order] start_payment failed for order=%s — order saved, payment_url=None",
            order.pk,
        )

    return {"order": order, "payment_url": payment_url}


def cancel_order(order_id: int, user) -> Order:
    with db_transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id, user=user)
        except Order.DoesNotExist:
            raise AppException("\\u0633\\u0641\\u0627\\u0631\\u0634 \\u06cc\\u0627\\u0641\\u062a \\u0646\\u0634\\u062f", status_code=404)

        if order.status != "pending":
            raise AppException("\\u062a\\u0646\\u0647\\u0627 \\u0633\\u0641\\u0627\\u0631\\u0634\\u200c\\u0647\\u0627\\u06cc \\u062f\\u0631 \\u062d\\u0627\\u0644 \\u062a\\u0627\\u06cc\\u06cc\\u062f \\u0642\\u0627\\u0628\\u0644 \\u0644\\u063a\\u0648 \\u0647\\u0633\\u062a\\u0646\\u062f.", status_code=400)

        for item in order.items.select_related("product"):
            Product.objects.filter(pk=item.product_id).update(
                stock=F("stock") + item.quantity
            )

        order.status = "cancelled"
        order.save(update_fields=["status"])

        OrderStatusHistory.objects.create(
            order=order,
            status="cancelled",
            note="\\u0644\\u063a\\u0648 \\u062a\\u0648\\u0633\\u0637 \\u06a9\\u0627\\u0631\\u0628\\u0631",
            created_by=user,
        )

    return order


def update_order_status(
    order_id: int,
    new_status: str,
    admin_user,
    tracking_number: str = "",
    postal_tracking: str = "",
    note: str = "",
) -> Order:
    valid_statuses = {choice[0] for choice in Order.STATUS_CHOICES}
    if new_status not in valid_statuses:
        raise AppException(
            f"\\u0648\\u0636\\u0639\\u06cc\\u062a \\u0646\\u0627\\u0645\\u0639\\u062a\\u0628\\u0631 \\u0627\\u0633\\u062a. \\u0645\\u0642\\u0627\\u062f\\u06cc\\u0631 \\u0645\\u062c\\u0627\\u0632: {', '.join(sorted(valid_statuses))}",
            status_code=400,
        )

    with db_transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id)
        except Order.DoesNotExist:
            raise AppException("\\u0633\\u0641\\u0627\\u0631\\u0634 \\u06cc\\u0627\\u0641\\u062a \\u0646\\u0634\\u062f", status_code=404)

        update_fields = ["status"]
        order.status = new_status

        if tracking_number:
            order.tracking_number = tracking_number
            update_fields.append("tracking_number")

        if postal_tracking:
            order.postal_tracking = postal_tracking
            update_fields.append("postal_tracking")

        if new_status == "shipped" and not order.shipped_at:
            from django.utils import timezone
            order.shipped_at = timezone.now()
            update_fields.append("shipped_at")

        if new_status == "delivered" and not order.delivered_at:
            from django.utils import timezone
            order.delivered_at = timezone.now()
            update_fields.append("delivered_at")

        order.save(update_fields=update_fields)

        OrderStatusHistory.objects.create(
            order=order,
            status=new_status,
            note=note or f"\\u0648\\u0636\\u0639\\u06cc\\u062a \\u062a\\u0648\\u0633\\u0637 \\u0627\\u062f\\u0645\\u06cc\\u0646 \\u0628\\u0647 \\u00ab{new_status}\\u00bb \\u062a\\u063a\\u06cc\\u06cc\\u0631 \\u06a9\\u0631\\u062f",
            created_by=admin_user,
        )

    return order


def get_user_orders(user) -> List[Order]:
    return list(
        Order.objects.filter(user=user)
        .prefetch_related("items__product", "history")
        .order_by("-created_at")
    )


def get_user_order_detail(user, order_id: int) -> Order:
    try:
        return (
            Order.objects.filter(user=user)
            .prefetch_related("items__product", "history")
            .get(pk=order_id)
        )
    except Order.DoesNotExist:
        raise AppException("\\u0633\\u0641\\u0627\\u0631\\u0634 \\u06cc\\u0627\\u0641\\u062a \\u0646\\u0634\\u062f", status_code=404)
""")

print()
print("Files written successfully:")
files = [
    "payment/providers/base.py",
    "payment/providers/mock.py",
    "payment/providers/zarinpal.py",
    "payment/providers/__init__.py",
    "payment/orchestrator.py",
    "payment/services.py",
    "payment/api.py",
    "store/services.py",
]
for f in files:
    print(f"  [+] {f}")

print()
print("=" * 60)
print("Phase 16 patch applied successfully.")
print("=" * 60)
print()
print("Next steps:")
print("  1. pip install -r requirements/local.txt   (no new packages in this phase)")
print("  2. python manage.py check")
print("  3. python manage.py makemigrations --check  -->  No changes detected")
print("  4. python manage.py migrate")
print("  5. python manage.py runserver")
print("  6. Open http://127.0.0.1:8000/api/docs")
