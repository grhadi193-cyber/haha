from pydantic import BaseModel, field_validator
import re


class SendOTPRequest(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"09[0-9]{9}", v):
            raise ValueError("شماره موبایل معتبر نیست. فرمت: 09XXXXXXXXX")
        return v


class VerifyOTPRequest(BaseModel):
    phone_number: str
    code: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"09[0-9]{9}", v):
            raise ValueError("شماره موبایل معتبر نیست. فرمت: 09XXXXXXXXX")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"[0-9]{6}", v):
            raise ValueError("کد OTP باید ۶ رقم باشد.")
        return v


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: bool
