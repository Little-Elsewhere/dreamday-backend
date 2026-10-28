import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum, auto
from uuid import UUID, uuid4

import anyio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.email import send_verification_email
from app.auth.models import EmailVerificationToken, RefreshToken, User
from app.auth.repositories.email_verification_tokens import (
  EmailVerificationTokenRepository,
)
from app.auth.repositories.refresh_tokens import RefreshTokenRepository
from app.auth.repositories.users import UserRepository
from app.auth.schemas import TokenResponse
from app.core.config import settings
from app.core.database import SessionFactory
from app.core.security import (
  create_access_token,
  hash_password,
  hash_secret,
  verify_password,
)

logger = logging.getLogger(__name__)


class AuthServiceErrorCode(Enum):
  INVALID_VERIFICATION_LINK = auto()
  INVALID_CREDENTIALS = auto()
  EMAIL_NOT_VERIFIED = auto()
  ACCOUNT_DISABLED = auto()
  INVALID_REFRESH_TOKEN = auto()


class AuthServiceError(Exception):
  def __init__(self, code: AuthServiceErrorCode) -> None:
    self.code = code
    super().__init__(code.name)


@dataclass(frozen=True)
class VerificationEmail:
  email: str
  raw_token: str
  token_hash: str


def normalize_email(email: str) -> str:
  return email.strip().lower()


class AuthService:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    self.users = UserRepository(session)
    self.verification_tokens = EmailVerificationTokenRepository(session)
    self.refresh_tokens = RefreshTokenRepository(session)

  async def register(
    self, email: str, password: str
  ) -> VerificationEmail | None:
    email = normalize_email(email)
    hashed_password = await anyio.to_thread.run_sync(hash_password, password)
    user = await self.users.get_by_email(email, for_update=True)

    if user is None:
      user = User(email=email, password_hash=hashed_password)
      self.users.add(user)
      try:
        await self.session.flush()
      except IntegrityError:
        await self.session.rollback()
        return None
    elif (
      not user.is_active
      or user.is_email_verified
      or not await self._verification_token_can_be_sent(user.id)
    ):
      return None

    verification_email = await self._issue_verification_token(user)
    try:
      await self.session.commit()
    except IntegrityError:
      await self.session.rollback()
      return None
    return verification_email

  async def resend_verification(self, email: str) -> VerificationEmail | None:
    email = normalize_email(email)
    user = await self.users.get_by_email(email, for_update=True)
    if (
      user is None
      or not user.is_active
      or user.is_email_verified
      or not await self._verification_token_can_be_sent(user.id)
    ):
      return None

    verification_email = await self._issue_verification_token(user)
    await self.session.commit()
    return verification_email

  async def verify_email(self, raw_token: str) -> None:
    now = datetime.now(UTC)
    verification = await self.verification_tokens.get_by_token_hash(
      hash_secret(raw_token), for_update=True
    )
    if (
      verification is None
      or verification.consumed_at is not None
      or verification.expires_at <= now
    ):
      raise AuthServiceError(AuthServiceErrorCode.INVALID_VERIFICATION_LINK)

    user = await self.users.get_by_id(verification.user_id)
    if user is None or not user.is_active:
      self.verification_tokens.consume(verification, now)
      await self.session.commit()
      raise AuthServiceError(AuthServiceErrorCode.INVALID_VERIFICATION_LINK)

    self.verification_tokens.consume(verification, now)
    user.is_email_verified = True
    await self.session.commit()

  async def login(self, email: str, password: str) -> TokenResponse:
    email = normalize_email(email)
    user = await self.users.get_by_email(email)
    if user is None:
      await anyio.to_thread.run_sync(hash_password, password)
      raise AuthServiceError(AuthServiceErrorCode.INVALID_CREDENTIALS)

    is_password_valid = await anyio.to_thread.run_sync(
      verify_password, password, user.password_hash
    )
    if not is_password_valid:
      raise AuthServiceError(AuthServiceErrorCode.INVALID_CREDENTIALS)
    if not user.is_email_verified:
      raise AuthServiceError(AuthServiceErrorCode.EMAIL_NOT_VERIFIED)
    if not user.is_active:
      raise AuthServiceError(AuthServiceErrorCode.ACCOUNT_DISABLED)
    return await self._create_auth_tokens(user)

  async def refresh(self, raw_token: str) -> TokenResponse:
    now = datetime.now(UTC)
    stored_token = await self.refresh_tokens.get_by_token_hash(
      hash_secret(raw_token), for_update=True
    )
    if stored_token is None:
      raise AuthServiceError(AuthServiceErrorCode.INVALID_REFRESH_TOKEN)

    if stored_token.revoked_at is not None:
      await self.refresh_tokens.revoke_active_family(
        stored_token.family_id, now
      )
      await self.session.commit()
      raise AuthServiceError(AuthServiceErrorCode.INVALID_REFRESH_TOKEN)

    if stored_token.expires_at <= now:
      self.refresh_tokens.revoke(stored_token, now)
      await self.session.commit()
      raise AuthServiceError(AuthServiceErrorCode.INVALID_REFRESH_TOKEN)

    user = await self.users.get_by_id(stored_token.user_id)
    if user is None or not user.is_active or not user.is_email_verified:
      await self.refresh_tokens.revoke_active_family(
        stored_token.family_id, now
      )
      await self.session.commit()
      raise AuthServiceError(AuthServiceErrorCode.INVALID_REFRESH_TOKEN)

    raw_replacement_token = secrets.token_urlsafe(48)
    new_expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    replacement = create_refresh_token_record(
      user.id, stored_token.family_id, raw_replacement_token, new_expires_at
    )
    self.refresh_tokens.add(replacement)
    await self.session.flush()
    self.refresh_tokens.revoke(stored_token, now, replaced_by_id=replacement.id)
    token_response = create_token_response(user.id, raw_replacement_token)
    await self.session.commit()
    return token_response

  async def logout(self, raw_token: str) -> None:
    stored_token = await self.refresh_tokens.get_by_token_hash(
      hash_secret(raw_token), for_update=True
    )
    if stored_token is not None and stored_token.revoked_at is None:
      self.refresh_tokens.revoke(stored_token, datetime.now(UTC))
      await self.session.commit()

  async def _verification_token_can_be_sent(self, user_id: UUID) -> bool:
    now = datetime.now(UTC)
    latest_created_at = await self.verification_tokens.latest_active_created_at(
      user_id, now
    )
    if latest_created_at is None:
      return True
    return (
      now - latest_created_at
    ).total_seconds() >= settings.email_verification_resend_cooldown_seconds

  async def _issue_verification_token(self, user: User) -> VerificationEmail:
    now = datetime.now(UTC)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_secret(raw_token)
    verification = EmailVerificationToken(
      user_id=user.id,
      token_hash=token_hash,
      expires_at=now
      + timedelta(minutes=settings.email_verification_token_expire_minutes),
    )
    await self.verification_tokens.replace_pending_for_user(
      user.id, verification, now
    )
    return VerificationEmail(user.email, raw_token, token_hash)

  async def _create_auth_tokens(self, user: User) -> TokenResponse:
    now = datetime.now(UTC)
    raw_refresh_token = secrets.token_urlsafe(48)
    family_id = uuid4()
    refresh_expires_at = now + timedelta(
      days=settings.refresh_token_expire_days
    )
    self.refresh_tokens.add(
      create_refresh_token_record(
        user.id, family_id, raw_refresh_token, refresh_expires_at
      )
    )
    token_response = create_token_response(user.id, raw_refresh_token)
    await self.session.commit()
    return token_response


def create_refresh_token_record(
  user_id: UUID, family_id: UUID, raw_token: str, expires_at: datetime
) -> RefreshToken:
  return RefreshToken(
    user_id=user_id,
    family_id=family_id,
    token_hash=hash_secret(raw_token),
    expires_at=expires_at,
  )


def create_token_response(user_id: UUID, refresh_token: str) -> TokenResponse:
  return TokenResponse(
    access_token=create_access_token(user_id),
    expires_in=settings.access_token_expire_minutes * 60,
    refresh_token=refresh_token,
    refresh_expires_in=settings.refresh_token_expire_days * 24 * 60 * 60,
  )


async def deliver_verification_email_in_background(
  email: str, raw_token: str, token_hash: str
) -> None:
  async with SessionFactory() as session:
    try:
      await send_verification_email(email, raw_token)
    except Exception:
      logger.exception('Could not send an email verification message')
      repository = EmailVerificationTokenRepository(session)
      await repository.consume_by_token_hash(token_hash, datetime.now(UTC))
      await session.commit()
