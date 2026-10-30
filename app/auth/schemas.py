from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, EmailStr, Field

from app.core.datetime import UtcInstant


def normalize_email(email: str) -> str:
  return email.strip().lower()


NormalizedEmail = Annotated[EmailStr, BeforeValidator(normalize_email)]


class RegisterRequest(BaseModel):
  email: NormalizedEmail
  password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
  email: NormalizedEmail
  password: str = Field(min_length=1, max_length=128)


class EmailRequest(BaseModel):
  email: NormalizedEmail


class EmailVerificationRequest(BaseModel):
  token: str = Field(min_length=32, max_length=2048)


class PasswordResetConfirmRequest(BaseModel):
  token: str = Field(min_length=32, max_length=2048)
  password: str = Field(min_length=12, max_length=128)


class UpdatePasswordRequest(BaseModel):
  current_password: str = Field(min_length=1, max_length=128)
  new_password: str = Field(min_length=12, max_length=128)


class RefreshRequest(BaseModel):
  refresh_token: str = Field(min_length=32, max_length=256)


class LogoutRequest(BaseModel):
  refresh_token: str = Field(min_length=32, max_length=256)


class TokenResponse(BaseModel):
  access_token: str
  token_type: Literal['bearer'] = 'bearer'
  expires_in: int
  refresh_token: str
  refresh_expires_in: int


class UserResponse(BaseModel):
  id: UUID
  email: EmailStr
  is_email_verified: bool
  created_at: UtcInstant
