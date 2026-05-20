import logging
from decimal import Decimal
from django.conf import settings
from django.db import transaction as db_transaction

from store.models import Order
from sms.services import send_order_success_sms
from .models import Transaction
from .providers import MockProvider, ZarinpalProvider

logger = logging.getLogger(__name__)

def get_provider(name: str):
    if settings.DEBUG:
        return MockProvider()
    if name == "zarinpal":
        return ZarinpalProvider()
    # default to zarinpal
    return ZarinpalProvider()

def start_payment(order: Order, provider_name: str = "zarinpal") -> tuple[str, int]:
    provider = get_provider(provider_name)
    
    amount = Decimal(str(order.total_price))
    txn = Transaction.objects.create(
        order=order,
        amount=amount,
        status=Transaction.Status.PENDING,
        provider=provider.name
    )

    try:
        payment_url = provider.initiate(txn)
        txn.save(update_fields=["ref_id", "gateway_response"])
        return payment_url, txn.pk
    except Exception as exc:
        txn.status = Transaction.Status.FAILED
        txn.gateway_response = {"error": str(exc)}
        txn.save(update_fields=["status", "gateway_response"])
        logger.exception(f"[Payment] Gateway initiation failed for order #{order.pk}")
        raise

def verify_payment(transaction_id: int, raw_params: dict) -> bool:
    try:
        txn = Transaction.objects.select_for_update().get(pk=transaction_id)
    except Transaction.DoesNotExist:
        logger.error(f"[Payment] verify() called with unknown transaction_id={transaction_id}")
        return False

    if txn.status == Transaction.Status.SUCCESS:
        return True
    if txn.status == Transaction.Status.FAILED:
        return False

    provider = get_provider(txn.provider)
    
    try:
        with db_transaction.atomic():
            success = provider.verify(txn, raw_params)
            txn.status = Transaction.Status.SUCCESS if success else Transaction.Status.FAILED
            txn.save(update_fields=["status", "ref_id", "gateway_response"])

            if success:
                _mark_order_paid(txn)
        return success
    except Exception as exc:
        txn.status = Transaction.Status.FAILED
        txn.gateway_response = {**txn.gateway_response, "verify_error": str(exc)}
        txn.save(update_fields=["status", "gateway_response"])
        logger.exception(f"[Payment] Gateway verify failed for transaction #{transaction_id}")
        return False

def _mark_order_paid(txn: Transaction) -> None:
    order = Order.objects.select_for_update().get(pk=txn.order_id)
    order.status = "paid"
    order.save(update_fields=["status"])

    try:
        send_order_success_sms(phone_number=order.user.phone_number, order_id=order.pk)
    except Exception as sms_exc:
        logger.error(f"[Payment] SMS failed after payment for order #{order.pk}: {sms_exc}")
