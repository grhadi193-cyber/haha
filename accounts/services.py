from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPRecord, User
from core.exceptions import OTPNotFoundError, OTPExpiredError, OTPInvalidError


def generate_otp(phone_number: str) -> str:
    """
    یک OTP شش‌رقمی تولید کرده، رکوردهای قبلی را پاک می‌کند و ذخیره می‌کند.
    کد را به‌صورت رشته برمی‌گرداند تا sms/services بتواند ارسال کند.
    """
    import random
    code = f"{random.randint(100000, 999999)}"

    # همه رکوردهای قبلی را پاک کن (جلوگیری از MultipleObjectsReturned)
    OTPRecord.objects.filter(phone_number=phone_number).delete()

    OTPRecord.objects.create(
        phone_number=phone_number,
        code=code,
        expires_at=timezone.now() + timezone.timedelta(seconds=120),
        is_used=False,
    )
    return code


def verify_otp_and_login(phone_number: str, code: str) -> dict:
    """
    OTP را تأیید کرده، کاربر را می‌سازد/پیدا می‌کند و dict با access_token برمی‌گرداند.
    """
    try:
        record = OTPRecord.objects.get(
            phone_number=phone_number,
            code=code,
            is_used=False,
        )
    except OTPRecord.DoesNotExist:
        raise OTPInvalidError()

    if timezone.now() > record.expires_at:
        record.delete()
        raise OTPExpiredError()

    record.is_used = True
    record.save(update_fields=["is_used"])

    user, _ = User.objects.get_or_create(
        phone_number=phone_number,
        defaults={"is_active": True},
    )

    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)

    return {"access_token": access_token}
