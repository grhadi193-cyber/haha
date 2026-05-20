# apply_phase_12.py
# Phase 12 — Account Profile + کد ملی + آدرس کامل
# اجرا: python apply_phase_12.py  (از root پروژه)

import pathlib, textwrap, sys

ROOT = pathlib.Path(__file__).parent

files = {}

# ──────────────────────────────────────────────────────────────────────────────
# accounts/models.py
# ──────────────────────────────────────────────────────────────────────────────
files["accounts/models.py"] = """\
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
import secrets

from .managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(max_length=15, unique=True)
    full_name    = models.CharField(max_length=128, blank=True, default="")
    email        = models.EmailField(blank=True, null=True, unique=True)
    national_id  = models.CharField(max_length=10, blank=True, null=True, unique=True)
    is_active    = models.BooleanField(default=True)
    is_staff     = models.BooleanField(default=False)
    date_joined  = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD  = "phone_number"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name        = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self):
        return self.phone_number


class Address(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    title       = models.CharField(max_length=64, blank=True, default="")
    province    = models.CharField(max_length=64)
    city        = models.CharField(max_length=64)
    street      = models.TextField()
    postal_code = models.CharField(max_length=20)
    is_default  = models.BooleanField(default=False)

    class Meta:
        verbose_name        = "آدرس"
        verbose_name_plural = "آدرس\u200cها"

    def __str__(self):
        return f"{self.user.phone_number} \u2014 {self.city}"


class OTPRecord(models.Model):
    phone_number = models.CharField(max_length=15, unique=True)
    code         = models.CharField(max_length=6)
    created_at   = models.DateTimeField(auto_now_add=True)
    expires_at   = models.DateTimeField()
    is_used      = models.BooleanField(default=False)
    last_sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "کد OTP"
        verbose_name_plural = "کدهای OTP"

    def __str__(self):
        return f"{self.phone_number} \u2014 {self.code}"

    def generate_code(self):
        from django.conf import settings
        expiry_minutes = getattr(settings, "OTP_EXPIRY_MINUTES", 2)
        self.code       = str(secrets.randbelow(900000) + 100000)
        self.expires_at = timezone.now() + timezone.timedelta(minutes=expiry_minutes)
        self.last_sent_at = timezone.now()
        self.is_used    = False
        self.save(update_fields=["code", "expires_at", "last_sent_at", "is_used"])

    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at
"""

# ──────────────────────────────────────────────────────────────────────────────
# accounts/schemas.py
# ──────────────────────────────────────────────────────────────────────────────
files["accounts/schemas.py"] = """\
from datetime import datetime
from pydantic import BaseModel, field_validator
from typing import Optional
import re


class SendOTPIn(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^09[0-9]{9}$", v):
            raise ValueError("شماره موبایل معتبر نیست")
        return v


class VerifyOTPIn(BaseModel):
    phone_number: str
    code: str


class TokenOut(BaseModel):
    access: str
    refresh: str


class AddressIn(BaseModel):
    title:       str  = ""
    province:    str
    city:        str
    street:      str
    postal_code: str
    is_default:  bool = False


class AddressOut(BaseModel):
    id:          int
    title:       str
    province:    str
    city:        str
    street:      str
    postal_code: str
    is_default:  bool

    model_config = {"from_attributes": True}


class ProfileOut(BaseModel):
    id:          int
    phone_number: str
    full_name:   str
    email:       Optional[str] = None
    national_id: Optional[str] = None
    date_joined: datetime

    model_config = {"from_attributes": True}


class UpdateProfileIn(BaseModel):
    full_name:   Optional[str] = None
    email:       Optional[str] = None
    national_id: Optional[str] = None
"""

# ──────────────────────────────────────────────────────────────────────────────
# accounts/services.py
# ──────────────────────────────────────────────────────────────────────────────
files["accounts/services.py"] = """\
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
            raise AppException(
                f"لطفاً {int(60 - time_since_last)} ثانیه دیگر تلاش کنید.",
                status_code=429,
            )

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


def create_address(
    user: User,
    title: str,
    province: str,
    city: str,
    street: str,
    postal_code: str,
    is_default: bool,
) -> Address:
    if is_default:
        user.addresses.filter(is_default=True).update(is_default=False)
    return Address.objects.create(
        user=user,
        title=title,
        province=province,
        city=city,
        street=street,
        postal_code=postal_code,
        is_default=is_default,
    )


def delete_address(user: User, address_id: int) -> None:
    try:
        address = user.addresses.get(pk=address_id)
    except Address.DoesNotExist:
        raise AppException("آدرس یافت نشد", status_code=404)
    address.delete()


def get_profile(user: User) -> User:
    return user


def update_profile(
    user: User,
    full_name: Optional[str],
    email: Optional[str],
    national_id: Optional[str],
) -> User:
    updated_fields: list[str] = []

    if full_name is not None:
        user.full_name = full_name.strip()
        updated_fields.append("full_name")

    if email is not None:
        user.email = email.strip() or None
        updated_fields.append("email")

    if national_id is not None:
        nid = national_id.strip() or None
        if nid is not None:
            # بررسی unique بودن — کاربر دیگری همین کد ملی را ندارد
            if (
                User.objects.filter(national_id=nid)
                .exclude(pk=user.pk)
                .exists()
            ):
                raise AppException("کد ملی تکراری است", status_code=400)
        user.national_id = nid
        updated_fields.append("national_id")

    if updated_fields:
        user.save(update_fields=updated_fields)

    return user
"""

# ──────────────────────────────────────────────────────────────────────────────
# accounts/api.py
# ──────────────────────────────────────────────────────────────────────────────
files["accounts/api.py"] = """\
from typing import List
from ninja import Router
from django.http import JsonResponse

from core.exceptions import AppException
from .schemas import (
    SendOTPIn, VerifyOTPIn, TokenOut,
    AddressIn, AddressOut,
    ProfileOut, UpdateProfileIn,
)
from . import services as svc

router = Router(tags=["Auth"])


def _get_auth_bearer():
    from store.api import AuthBearer
    return AuthBearer()


_auth = _get_auth_bearer()


@router.post("/send-otp", auth=None, summary="ارسال کد OTP")
def send_otp(request, payload: SendOTPIn):
    try:
        svc.send_otp(payload.phone_number)
    except AppException as e:
        return JsonResponse({"detail": e.detail}, status=e.status_code)
    return {"detail": "کد تایید ارسال شد"}


@router.post("/verify-otp", auth=None, response=TokenOut, summary="تایید OTP و دریافت توکن")
def verify_otp(request, payload: VerifyOTPIn):
    from rest_framework_simplejwt.tokens import RefreshToken
    try:
        user = svc.verify_otp(payload.phone_number, payload.code)
    except AppException as e:
        return JsonResponse({"detail": e.detail}, status=e.status_code)
    refresh = RefreshToken.for_user(user)
    return TokenOut(access=str(refresh.access_token), refresh=str(refresh))


@router.get("/addresses", auth=_auth, response=List[AddressOut], summary="لیست آدرس‌ها")
def list_addresses(request):
    return svc.get_addresses(request.auth)


@router.post("/addresses", auth=_auth, response=AddressOut, summary="افزودن آدرس")
def create_address(request, payload: AddressIn):
    return svc.create_address(
        request.auth,
        payload.title,
        payload.province,
        payload.city,
        payload.street,
        payload.postal_code,
        payload.is_default,
    )


@router.delete("/addresses/{address_id}", auth=_auth, summary="حذف آدرس")
def delete_address(request, address_id: int):
    try:
        svc.delete_address(request.auth, address_id)
    except AppException as e:
        return JsonResponse({"detail": e.detail}, status=e.status_code)
    return {"detail": "آدرس حذف شد"}


@router.get("/profile", auth=_auth, response=ProfileOut, summary="دریافت پروفایل کاربر")
def get_profile(request):
    return svc.get_profile(request.auth)


@router.patch("/profile", auth=_auth, response=ProfileOut, summary="ویرایش پروفایل کاربر")
def update_profile(request, payload: UpdateProfileIn):
    try:
        return svc.update_profile(
            request.auth,
            payload.full_name,
            payload.email,
            payload.national_id,
        )
    except AppException as e:
        return JsonResponse({"detail": e.detail}, status=e.status_code)


@router.get("/orders", auth=_auth, summary="لیست سفارش‌های کاربر")
def my_orders(request):
    from store.services import get_user_orders
    from store.schemas import UserOrderOut
    orders = get_user_orders(request.auth)
    return [UserOrderOut.model_validate(o) for o in orders]


@router.get("/orders/{order_id}", auth=_auth, summary="جزئیات سفارش کاربر")
def my_order_detail(request, order_id: int):
    from store.services import get_user_order_detail
    from store.schemas import UserOrderOut
    try:
        order = get_user_order_detail(request.auth, order_id)
    except AppException as e:
        return JsonResponse({"detail": e.detail}, status=e.status_code)
    return UserOrderOut.model_validate(order)
"""

# ──────────────────────────────────────────────────────────────────────────────
# accounts/migrations/0008_user_national_id.py
# ──────────────────────────────────────────────────────────────────────────────
files["accounts/migrations/0008_user_national_id.py"] = """\
# Generated by Phase 12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_alter_user_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="national_id",
            field=models.CharField(
                blank=True,
                max_length=10,
                null=True,
                unique=True,
                verbose_name="کد ملی",
            ),
        ),
    ]
"""

# ──────────────────────────────────────────────────────────────────────────────
# Write files
# ──────────────────────────────────────────────────────────────────────────────
written = []
for rel_path, content in files.items():
    target = ROOT / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    written.append(str(target))

print("\n✅  Phase 12 — فایل‌های نوشته‌شده:\n")
for p in written:
    print(f"   {p}")
print()
