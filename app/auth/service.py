import logging
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum, auto
from uuid import UUID, uuid4

import anyio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import (
  EmailVerificationToken,
  PasswordResetToken,
  RefreshToken,
  User,
)
from app.auth.repositories.purpose_tokens import (
  PurposeTokenRepository,
  PurposeTokenT,
)
from app.auth.repositories.refresh_tokens import RefreshTokenRepository
from app.auth.repositories.users import UserRepository
from app.auth.schemas import TokenResponse
from app.core.config import settings
from app.core.database import SessionFactory
from app.core.datetime import utc_now
from app.core.security import (
  create_access_token,
  create_purpose_token,
  hash_password,
  hash_secret,
  verify_password,
)

logger = logging.getLogger(__name__)

SendTokenEmail = Callable[[str, str], Awaitable[None]]


class AuthServiceErrorCode(Enum):
  EMAIL_ALREADY_REGISTERED = auto()
  INVALID_VERIFICATION_LINK = auto()
  INVALID_CREDENTIALS = auto()
  EMAIL_NOT_VERIFIED = auto()
  ACCOUNT_DISABLED = auto()
  INVALID_REFRESH_TOKEN = auto()
  INVALID_PASSWORD_RESET_LINK = auto()
  INVALID_CURRENT_PASSWORD = auto()


@dataclass(frozen=True)
class TokenEmail:
  email: str
  raw_token: str
  token_hash: str


@dataclass(frozen=True)
class PurposeTokenSpec[PurposeTokenT]:
  typ: str
  model: type[PurposeTokenT]
  expire_minutes: int
  cooldown_seconds: int


class AuthServiceError(Exception):
  def __init__(self, code: AuthServiceErrorCode) -> None:
    self.code = code
    super().__init__(code.name)


class AuthService:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    self.users = UserRepository(session)
    self.verification_tokens = PurposeTokenRepository(
      session, EmailVerificationToken
    )
    self.password_reset_tokens = PurposeTokenRepository(
      session, PasswordResetToken
    )
    self.refresh_tokens = RefreshTokenRepository(session)

  async def register(self, email: str, password: str) -> TokenEmail:
    if await self.users.get_by_email(email) is not None:
      raise AuthServiceError(AuthServiceErrorCode.EMAIL_ALREADY_REGISTERED)

    hashed_password = await anyio.to_thread.run_sync(hash_password, password)
    user = User(email=email, password_hash=hashed_password)
    self.users.add(user)
    try:
      await self.session.flush()
    except IntegrityError as error:
      await self.session.rollback()
      raise AuthServiceError(
        AuthServiceErrorCode.EMAIL_ALREADY_REGISTERED
      ) from error

    verification_email = await self._issue_purpose_token(
      user,
      repository=self.verification_tokens,
      spec=self._email_verification_spec(),
    )
    await self.session.commit()
    return verification_email

  async def resend_verification(self, email: str) -> TokenEmail | None:
    user = await self.users.get_by_email(email, for_update=True)
    if user is None or not user.is_active or user.is_email_verified:
      return None

    verification_email = await self._prepare_purpose_token_email(
      user,
      repository=self.verification_tokens,
      spec=self._email_verification_spec(),
    )
    await self.session.commit()
    return verification_email

  async def verify_email(self, raw_token: str) -> None:
    now = utc_now()
    verification, user = await self._require_active_purpose_token(
      raw_token,
      repository=self.verification_tokens,
      error_code=AuthServiceErrorCode.INVALID_VERIFICATION_LINK,
      now=now,
    )
    self.verification_tokens.consume(verification, now)
    user.is_email_verified = True
    await self.session.commit()

  async def forgot_password(self, email: str) -> TokenEmail | None:
    user = await self.users.get_by_email(email, for_update=True)
    if user is None or not user.is_active:
      return None

    reset_email = await self._prepare_purpose_token_email(
      user,
      repository=self.password_reset_tokens,
      spec=self._password_reset_spec(),
    )
    await self.session.commit()
    return reset_email

  async def reset_password(self, raw_token: str, password: str) -> None:
    now = utc_now()
    reset, user = await self._require_active_purpose_token(
      raw_token,
      repository=self.password_reset_tokens,
      error_code=AuthServiceErrorCode.INVALID_PASSWORD_RESET_LINK,
      now=now,
    )
    hashed_password = await anyio.to_thread.run_sync(hash_password, password)
    self.password_reset_tokens.consume(reset, now)
    user.password_hash = hashed_password
    user.is_email_verified = True
    await self.refresh_tokens.revoke_all_for_user(user.id, now)
    await self.session.commit()

  async def update_password(
    self, user: User, current_password: str, new_password: str
  ) -> TokenResponse:
    is_current_valid = await anyio.to_thread.run_sync(
      verify_password, current_password, user.password_hash
    )
    if not is_current_valid:
      raise AuthServiceError(AuthServiceErrorCode.INVALID_CURRENT_PASSWORD)

    hashed_password = await anyio.to_thread.run_sync(
      hash_password, new_password
    )
    user.password_hash = hashed_password
    await self.refresh_tokens.revoke_all_for_user(user.id, utc_now())
    return await self._create_auth_tokens(user)

  async def login(self, email: str, password: str) -> TokenResponse:
    user = await self.users.get_by_email(email)
    if user is None:
      raise AuthServiceError(AuthServiceErrorCode.INVALID_CREDENTIALS)

    is_password_valid = await anyio.to_thread.run_sync(
      verify_password, password, user.password_hash
    )
    if not is_password_valid:
      raise AuthServiceError(AuthServiceErrorCode.INVALID_CREDENTIALS)
    if not user.is_active:
      raise AuthServiceError(AuthServiceErrorCode.ACCOUNT_DISABLED)
    if not user.is_email_verified:
      raise AuthServiceError(AuthServiceErrorCode.EMAIL_NOT_VERIFIED)
    return await self._create_auth_tokens(user)

  async def refresh(self, raw_token: str) -> TokenResponse:
    now = utc_now()
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
      self.refresh_tokens.revoke(stored_token, utc_now())
      await self.session.commit()

  def _email_verification_spec(
    self,
  ) -> PurposeTokenSpec[EmailVerificationToken]:
    return PurposeTokenSpec(
      typ='email_verify',
      model=EmailVerificationToken,
      expire_minutes=settings.email_verification_token_expire_minutes,
      cooldown_seconds=settings.email_verification_resend_cooldown_seconds,
    )

  def _password_reset_spec(self) -> PurposeTokenSpec[PasswordResetToken]:
    return PurposeTokenSpec(
      typ='password_reset',
      model=PasswordResetToken,
      expire_minutes=settings.password_reset_token_expire_minutes,
      cooldown_seconds=settings.password_reset_resend_cooldown_seconds,
    )

  async def _require_active_purpose_token(
    self,
    raw_token: str,
    *,
    repository: PurposeTokenRepository[PurposeTokenT],
    error_code: AuthServiceErrorCode,
    now: datetime,
  ) -> tuple[PurposeTokenT, User]:
    stored = await repository.get_by_token_hash(
      hash_secret(raw_token), for_update=True
    )
    if (
      stored is None
      or stored.consumed_at is not None
      or stored.expires_at <= now
    ):
      raise AuthServiceError(error_code)

    user = await self.users.get_by_id(stored.user_id)
    if user is None or not user.is_active:
      repository.consume(stored, now)
      await self.session.commit()
      raise AuthServiceError(error_code)
    return stored, user

  async def _prepare_purpose_token_email(
    self,
    user: User,
    *,
    repository: PurposeTokenRepository[PurposeTokenT],
    spec: PurposeTokenSpec[PurposeTokenT],
  ) -> TokenEmail:
    now = utc_now()
    active = await repository.get_latest_active(user.id, now, for_update=True)
    if active is not None:
      age_seconds = (now - active.created_at).total_seconds()
      if age_seconds < spec.cooldown_seconds:
        reused = self._token_email_from_record(user, active, typ=spec.typ)
        if reused is not None:
          return reused
    return await self._issue_purpose_token(
      user, repository=repository, spec=spec
    )

  def _token_email_from_record(
    self,
    user: User,
    token: EmailVerificationToken | PasswordResetToken,
    *,
    typ: str,
  ) -> TokenEmail | None:
    raw_token = create_purpose_token(
      typ=typ,
      user_id=user.id,
      email=user.email,
      token_id=token.id,
      issued_at=token.created_at,
      expires_at=token.expires_at,
    )
    token_hash = hash_secret(raw_token)
    if token_hash != token.token_hash:
      return None
    return TokenEmail(user.email, raw_token, token_hash)

  async def _issue_purpose_token(
    self,
    user: User,
    *,
    repository: PurposeTokenRepository[PurposeTokenT],
    spec: PurposeTokenSpec[PurposeTokenT],
  ) -> TokenEmail:
    issued_at_ts = int(utc_now().timestamp())
    issued_at = datetime.fromtimestamp(issued_at_ts, UTC)
    expires_at = issued_at + timedelta(minutes=spec.expire_minutes)
    token_id = uuid4()
    raw_token = create_purpose_token(
      typ=spec.typ,
      user_id=user.id,
      email=user.email,
      token_id=token_id,
      issued_at=issued_at,
      expires_at=expires_at,
    )
    token_hash = hash_secret(raw_token)
    record = spec.model(
      id=token_id,
      user_id=user.id,
      token_hash=token_hash,
      expires_at=expires_at,
      created_at=issued_at,
    )
    await repository.replace_pending_for_user(user.id, record, issued_at)
    return TokenEmail(user.email, raw_token, token_hash)

  async def _create_auth_tokens(self, user: User) -> TokenResponse:
    now = utc_now()
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


async def deliver_token_email_in_background(
  email: str,
  raw_token: str,
  token_hash: str,
  *,
  send: SendTokenEmail,
  model: type[EmailVerificationToken] | type[PasswordResetToken],
  failure_log: str,
) -> None:
  async with SessionFactory() as session:
    try:
      await send(email, raw_token)
    except Exception:
      logger.exception(failure_log)
      repository = PurposeTokenRepository(session, model)
      await repository.consume_by_token_hash(token_hash, utc_now())
      await session.commit()
