from ninja import Router
from django.http import JsonResponse

from .schemas import SendOTPRequest, VerifyOTPRequest, AuthTokenResponse
from .services import generate_otp, verify_otp_and_login
from sms.services import send_otp as send_otp_sms
from core.exceptions import OTPInvalidError, OTPExpiredError

router = Router(tags=["Auth"])


@router.post("/send-otp", auth=None)
def send_otp(request, payload: SendOTPRequest):
    code = generate_otp(payload.phone_number)
    send_otp_sms(payload.phone_number, code)

    response: dict = {"detail": "OTP sent"}

    # در حالت DEBUG کد را در پاسخ هم برمی‌گردانیم (فقط برای تست)
    from django.conf import settings
    if settings.DEBUG:
        response["debug_code"] = code

    return response


@router.post("/verify-otp", response=AuthTokenResponse, auth=None)
def verify_otp(request, payload: VerifyOTPRequest):
    try:
        result = verify_otp_and_login(payload.phone_number, payload.code)
    except (OTPInvalidError, OTPExpiredError) as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    return AuthTokenResponse(access_token=result["access_token"])
