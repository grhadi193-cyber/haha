"""
PaymentGateway service — wraps az-iranian-bank-gateways (Zarinpal sandbox by default).

DECISIONS enforced:
- verify() is idempotent: calling it twice on an already-paid transaction is a no-op.
- Verify is always server-side; raw callback params are never trusted alone.
- On success: Order.status → 'paid'  +  send_order_success_sms() called explicitly.
- services.py never imports HttpRequest.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction as db_transaction

from store.models import Order
from sms.services import send_order_success_sms
from .models import Transaction

logger = logging.getLogger(__name__)


def _get_gateway():
    """
    Lazily import and return a configured azbankgateways bank instance.
    Using ZarinPal (sandbox-friendly).  Switch bank class via PAYMENT_BANK setting.
    """
    from azbankgateways import bankfactories, models as bank_models, default_settings as bank_settings  # noqa: F401
    from azbankgateways.banks import ZarinPal

    factory = bankfactories.BankFactory()
    bank = factory.create(bank_type=bank_models.BankType.ZARINPAL)
    bank.set_amount(0)          # will be set per-call
    bank.set_mobile_number("")  # optional
    return bank


class PaymentGateway:
    # ------------------------------------------------------------------ #
    #  initiate                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def initiate(order: Order) -> tuple[str, int]:
        """
        Create a pending Transaction and obtain a payment URL from the gateway.

        Returns (payment_url, transaction_id).

        In DEBUG mode the real gateway call is skipped and a fake sandbox URL
        is returned so the project stays fully runnable without gateway keys.
        """
        amount = Decimal(str(order.total_price))

        txn = Transaction.objects.create(
            order=order,
            amount=amount,
            status=Transaction.Status.PENDING,
        )

        if settings.DEBUG:
            # ── sandbox short-circuit ───────────────────────────────────
            fake_url = (
                f"http://127.0.0.1:8000/api/payment/callback"
                f"?Authority=SANDBOX_{txn.pk}&Status=OK&transaction_id={txn.pk}"
            )
            txn.gateway_response = {"debug": True, "fake_url": fake_url}
            txn.save(update_fields=["gateway_response"])
            logger.debug("[Payment] DEBUG mode — skipping real gateway. fake_url=%s", fake_url)
            return fake_url, txn.pk

        # ── real gateway call ───────────────────────────────────────────
        try:
            from azbankgateways import bankfactories, models as bank_models

            factory = bankfactories.BankFactory()
            bank = factory.create(bank_type=bank_models.BankType.ZARINPAL)

            # az-iranian-bank-gateways expects amount in Rials (×10 for Toman→Rial)
            bank.set_amount(int(amount) * 10)
            bank.set_mobile_number(order.user.phone_number)
            bank.set_client_callback_url(settings.PAYMENT_CALLBACK_URL)
            bank.set_order_id(str(order.pk))

            redirect_url = bank.redirect_gateway_url()

            txn.ref_id           = bank.get_transaction_id() or ""
            txn.gateway_response = {"gateway_token": txn.ref_id}
            txn.save(update_fields=["ref_id", "gateway_response"])

            return redirect_url, txn.pk

        except Exception as exc:
            txn.status           = Transaction.Status.FAILED
            txn.gateway_response = {"error": str(exc)}
            txn.save(update_fields=["status", "gateway_response"])
            logger.exception("[Payment] Gateway initiation failed for order #%s", order.pk)
            raise

    # ------------------------------------------------------------------ #
    #  verify                                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def verify(transaction_id: int, raw_params: dict) -> bool:
        """
        Server-side verify.  Idempotent — safe to call multiple times.

        Returns True if payment is/was successful, False otherwise.
        """
        try:
            txn = Transaction.objects.select_for_update().get(pk=transaction_id)
        except Transaction.DoesNotExist:
            logger.error("[Payment] verify() called with unknown transaction_id=%s", transaction_id)
            return False

        # ── idempotency guard ───────────────────────────────────────────
        if txn.status == Transaction.Status.SUCCESS:
            logger.info("[Payment] Transaction #%s already SUCCESS — skipping re-verify.", transaction_id)
            return True

        if txn.status == Transaction.Status.FAILED:
            logger.warning("[Payment] Transaction #%s already FAILED — cannot re-verify.", transaction_id)
            return False

        if settings.DEBUG:
            # ── sandbox short-circuit ───────────────────────────────────
            authority = raw_params.get("Authority", "")
            status    = raw_params.get("Status", "")

            success = authority.startswith("SANDBOX_") and status == "OK"

            with db_transaction.atomic():
                txn.status           = Transaction.Status.SUCCESS if success else Transaction.Status.FAILED
                txn.ref_id           = authority
                txn.gateway_response = {**txn.gateway_response, "verify_params": raw_params, "debug": True}
                txn.save(update_fields=["status", "ref_id", "gateway_response"])

                if success:
                    PaymentGateway._mark_order_paid(txn)

            return success

        # ── real gateway verify ─────────────────────────────────────────
        try:
            from azbankgateways import bankfactories, models as bank_models

            factory = bankfactories.BankFactory()
            bank = factory.create(bank_type=bank_models.BankType.ZARINPAL)

            bank.set_gateway_callback_parameters(raw_params, bank_models.BankType.ZARINPAL)
            bank.verify_from_gateway(request=None)

            tracking_code = bank.get_tracking_code()
            success = bank.is_success()

            with db_transaction.atomic():
                txn.status           = Transaction.Status.SUCCESS if success else Transaction.Status.FAILED
                txn.ref_id           = str(tracking_code or "")
                txn.gateway_response = {
                    **txn.gateway_response,
                    "tracking_code": tracking_code,
                    "verify_params": raw_params,
                }
                txn.save(update_fields=["status", "ref_id", "gateway_response"])

                if success:
                    PaymentGateway._mark_order_paid(txn)

            return success

        except Exception as exc:
            txn.status           = Transaction.Status.FAILED
            txn.gateway_response = {**txn.gateway_response, "verify_error": str(exc)}
            txn.save(update_fields=["status", "gateway_response"])
            logger.exception("[Payment] Gateway verify failed for transaction #%s", transaction_id)
            return False

    # ------------------------------------------------------------------ #
    #  internal helpers                                                    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _mark_order_paid(txn: Transaction) -> None:
        """
        Update Order status → paid and send success SMS.
        Must be called inside an atomic block.
        """
        order = Order.objects.select_for_update().get(pk=txn.order_id)
        order.status = "paid"
        order.save(update_fields=["status"])

        # Explicit SMS call — no signals
        try:
            send_order_success_sms(
                phone_number=order.user.phone_number,
                order_id=order.pk,
            )
        except Exception as sms_exc:
            # SMS failure must NOT roll back the payment
            logger.error("[Payment] SMS failed after payment for order #%s: %s", order.pk, sms_exc)
