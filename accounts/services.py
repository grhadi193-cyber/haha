import random
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPRecord, User
from core.exceptions import OTPInvalidError, OTPExpiredError, OTPNotFoundError

logger = logging.getLogger(__name__)

OTP_EXPIRY_SECONDS = 120


def _make_jwt_for_user(user: User) -> str:
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


def generate_otp(phone_number: str) -> str:
    code = f"{random.randint(0, 999999):06d}"
    expires_at = timezone.now() + timedelta(seconds=OTP_EXPIRY_SECONDS)

    OTPRecord.objects.create(
        phone_number=phone_number,
        code=code,
        expires_at=expires_at,
        is_used=False,
    )

    from sms.services import send_otp_sms
    send_otp_sms(phone_number, code)  # positional args — avoids signature mismatch

    if settings.DEBUG:
        logger.debug("[OTP DEBUG] phone=%s code=%s", phone_number, code)

    return code


def verify_otp_and_login(phone_number: str, code: str) -> dict:
    record = (
        OTPRecord.objects.filter(phone_number=phone_number, is_used=False)
        .order_by("-created_at")
        .first()
    )

    if record is None:
        raise OTPNotFoundError()

    if record.is_expired:
        raise OTPExpiredError()

    if record.code != code:
        raise OTPInvalidError()

    record.is_used = True
    record.save(update_fields=["is_used"])

    user, created = User.objects.get_or_create(
        phone_number=phone_number,
        defaults={"is_active": True},
    )

    access_token = _make_jwt_for_user(user)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "is_new_user": created,
    }
