from typing import Optional
from django.utils import timezone

from core.exceptions import AppException
from sms.services import send_otp as send_otp_code

from .models import User, Address, OTPRecord


def send_otp(phone_number: str) -> None:
    record, created = OTPRecord.objects.get_or_create(
        phone_number=phone_number,
        defaults={"code": "000000", "expires_at": timezone.now()},
    )
    
    if not created:
        time_since_last = (timezone.now() - record.last_sent_at).total_seconds()
        if time_since_last < 60:
            raise AppException(f"لطفاً {int(60 - time_since_last)} ثانیه دیگر تلاش کنید.", status_code=429)

    record.generate_code()
    send_otp_code(phone_number, record.code)


def verify_otp(phone_number: str, code: str) -> User:
    try:
        record = OTPRecord.objects.get(phone_number=phone_number, is_used=False)
    except OTPRecord.DoesNotExist:
        raise AppException("کد تایید یافت نشد", status_code=400)

    if record.is_expired():
        raise AppException("کد تایید منقضی شده است", status_code=400)

    if record.code != code:
        raise AppException("کد تایید اشتباه است", status_code=400)

    record.is_used = True
    record.save(update_fields=["is_used"])

    user, _ = User.objects.get_or_create(phone_number=phone_number)
    user.is_active = True
    user.save(update_fields=["is_active"])
    return user


def get_addresses(user: User) -> list:
    return list(user.addresses.all())


def create_address(user: User, title: str, province: str, city: str,
                   street: str, postal_code: str, is_default: bool) -> Address:
    if is_default:
        user.addresses.filter(is_default=True).update(is_default=False)
    return Address.objects.create(
        user=user, title=title, province=province, city=city,
        street=street, postal_code=postal_code, is_default=is_default,
    )


def delete_address(user: User, address_id: int) -> None:
    try:
        address = user.addresses.get(pk=address_id)
    except Address.DoesNotExist:
        raise AppException("آدرس یافت نشد", status_code=404)
    address.delete()


def get_profile(user: User) -> User:
    return user


def update_profile(user: User, full_name: Optional[str], email: Optional[str]) -> User:
    updated_fields = []
    if full_name is not None:
        user.full_name = full_name.strip()
        updated_fields.append("full_name")
    if email is not None:
        user.email = email.strip()
        updated_fields.append("email")
    if updated_fields:
        user.save(update_fields=updated_fields)
    return user
