from pydantic import BaseModel, field_validator
import re
from typing import Optional


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
    title: str = ""
    province: str
    city: str
    street: str
    postal_code: str
    is_default: bool = False


class AddressOut(BaseModel):
    id: int
    title: str
    province: str
    city: str
    street: str
    postal_code: str
    is_default: bool

    model_config = {"from_attributes": True}


class ProfileOut(BaseModel):
    phone_number: str
    full_name: str
    email: Optional[str] = None

    model_config = {"from_attributes": True}


class UpdateProfileIn(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
