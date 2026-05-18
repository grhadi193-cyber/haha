import logging

from ninja import Router
from django.conf import settings

from .schemas import SendOTPRequest, VerifyOTPRequest, AuthTokenResponse
from .services import generate_otp, verify_otp_and_login

logger = logging.getLogger(__name__)

router = Router(tags=["Auth"])


@router.post(
    "/send-otp",
    summary="ارسال کد OTP",
    response={200: dict},
)
def send_otp(request, payload: SendOTPRequest):
    code = generate_otp(payload.phone_number)
    response: dict = {"detail": "کد OTP ارسال شد."}
    if settings.DEBUG:
        # Expose OTP in response body ONLY in DEBUG (dev convenience)
        response["debug_code"] = code
    return 200, response


@router.post(
    "/verify-otp",
    summary="تأیید کد OTP و دریافت توکن",
    response={200: AuthTokenResponse},
)
def verify_otp(request, payload: VerifyOTPRequest):
    data = verify_otp_and_login(
        phone_number=payload.phone_number,
        code=payload.code,
    )
    return 200, data
