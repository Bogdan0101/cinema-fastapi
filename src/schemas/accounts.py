from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from src.security.password import validate_password_strength


class BaseEmailPasswordSchema(BaseModel):
    email: EmailStr
    password: str

    model_config = {"from_attributes": True}

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        return validate_password_strength(value)


class UserRegistrationRequestSchema(BaseEmailPasswordSchema):
    pass


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetCompleteRequestSchema(BaseEmailPasswordSchema):
    token: str


class UserLoginRequestSchema(BaseEmailPasswordSchema):
    pass


class UserLoginResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserRegistrationResponseSchema(BaseModel):
    id: int
    email: EmailStr

    model_config = {"from_attributes": True}


class UserActivationRequestSchema(BaseModel):
    email: EmailStr
    token: str


class MessageResponseSchema(BaseModel):
    message: str


class TokenRefreshRequestSchema(BaseModel):
    refresh_token: str


class TokenRefreshResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordChangeRequestSchema(BaseModel):
    old_password: str
    new_password: str
    model_config = {"from_attributes": True}

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value):
        return validate_password_strength(value)


class UserProfileSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None
    model_config = {"from_attributes": True}


class UserMeResponseSchema(BaseModel):
    id: int
    email: str
    is_active: bool
    group_name: str
    profile: UserProfileSchema
    model_config = {"from_attributes": True}
