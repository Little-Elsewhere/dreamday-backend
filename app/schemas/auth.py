from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
  email: EmailStr
  password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
  email: EmailStr
  password: str = Field(min_length=1, max_length=128)


class EmailRequest(BaseModel):
  email: EmailStr


class EmailVerificationRequest(BaseModel):
  token: str = Field(min_length=32, max_length=256)


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
  created_at: datetime
