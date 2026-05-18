"""
SMS service layer.

Rules:
- No HttpRequest dependency anywhere in this module.
- In DEBUG mode: skip real API call, print to console, return True.
- In PRODUCTION: call Kavenegar SDK, write SMSLog record.
- All exceptions are caught; callers receive a plain bool.
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _log_to_db(recipient: str, message: str, success: bool, error: str | None) -> None:
    """Persist an SMSLog record. Import here to avoid circular imports at module load."""
    try:
        from sms.models import SMSLog  # noqa: PLC0415

        SMSLog.objects.create(
            recipient=recipient,
            message=message,
            success=success,
            error_message=error,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("SMSLog write failed: %s", exc)


def _send_via_kavenegar(phone: str, message: str) -> tuple[bool, str | None]:
    """
    Send an SMS through the Kavenegar REST SDK.

    Returns (success, error_message).
    """
    try:
        from kavenegar import KavenegarAPI, APIException, HTTPException  # noqa: PLC0415

        api_key: str = settings.KAVENEGAR_API_KEY
        if not api_key:
            return False, "KAVENEGAR_API_KEY is not configured."

        api = KavenegarAPI(api_key)
        params = {
            "sender": "",   # uses account default sender
            "receptor": phone,
            "message": message,
        }
        api.sms_send(params)
        return True, None

    except Exception as exc:  # noqa: BLE001
        error_str = str(exc)
        logger.error("Kavenegar send failed for %s: %s", phone, error_str)
        return False, error_str


# ── Public service functions ─────────────────────────────────────────────────

def send_otp_sms(phone: str, otp: str) -> bool:
    """
    Send a one-time password via SMS.

    Args:
        phone: Recipient phone number (e.g. "09123456789").
        otp:   The OTP string to include in the message.

    Returns:
        True if the message was dispatched successfully, False otherwise.
    """
    message = "کد تأیید شما: " + str(otp) + " - این کد تا ۵ دقیقه معتبر است."

    if settings.DEBUG:
        print(f"[SMS-DEBUG] OTP for {phone}: {otp}")
        logger.debug("OTP SMS skipped (DEBUG=True) — phone=%s otp=%s", phone, otp)
        return True

    success, error = _send_via_kavenegar(phone, message)
    _log_to_db(phone, message, success, error)
    return success


def send_order_success_sms(phone: str, order_id: int) -> bool:
    """
    Notify a customer that their order was placed successfully.

    Args:
        phone:    Recipient phone number.
        order_id: The ID of the newly created order.

    Returns:
        True if the message was dispatched successfully, False otherwise.
    """
    message = f"سفارش شما با شماره {order_id} با موفقیت ثبت شد. ممنون از خرید شما!"

    if settings.DEBUG:
        print(f"[SMS-DEBUG] Order success SMS for {phone} — order_id={order_id}")
        logger.debug(
            "Order SMS skipped (DEBUG=True) — phone=%s order_id=%s", phone, order_id
        )
        return True

    success, error = _send_via_kavenegar(phone, message)
    _log_to_db(phone, message, success, error)
    return success
