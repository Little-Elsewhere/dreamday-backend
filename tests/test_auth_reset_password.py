import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.models import PasswordResetToken, User
from app.auth.service import AuthService, AuthServiceError, AuthServiceErrorCode
from app.core.security import hash_secret, verify_password
from tests.helpers import (
  assert_refresh_token_persisted,
  assert_token_response,
  assert_validation_error,
)


async def test_reset_password_rejects_invalid_field_bounds(
  client: AsyncClient,
) -> None:
  short_token = await client.post(
    '/api/v1/auth/reset-password',
    json={
      'token': 'short',
      'password': 'password-12345',  # pragma: allowlist secret
    },
  )
  long_token = await client.post(
    '/api/v1/auth/reset-password',
    json={
      'token': 'x' * 2049,
      'password': 'password-12345',  # pragma: allowlist secret
    },
  )
  short_password = await client.post(
    '/api/v1/auth/reset-password',
    json={
      'token': 'x' * 48,
      'password': 'short',  # pragma: allowlist secret
    },
  )
  long_password = await client.post(
    '/api/v1/auth/reset-password',
    json={
      'token': 'x' * 48,
      'password': 'p' * 129,  # pragma: allowlist secret
    },
  )
  missing_fields = await client.post('/api/v1/auth/reset-password', json={})
  assert_validation_error(short_token, 'token')
  assert_validation_error(long_token, 'token')
  assert_validation_error(short_password, 'password')
  assert_validation_error(long_password, 'password')
  assert_validation_error(missing_fields, 'token', 'password')


async def test_forgot_and_reset_password(
  auth_service: AuthService, make_user, make_refresh_token, session
) -> None:
  user = await make_user(email='reset@example.com', is_email_verified=False)
  old_raw, refresh = await make_refresh_token(user)

  reset_email = await auth_service.forgot_password('reset@example.com')
  assert reset_email is not None
  assert reset_email.email == 'reset@example.com'
  assert reset_email.raw_token
  assert reset_email.token_hash == hash_secret(reset_email.raw_token)

  await auth_service.reset_password(
    reset_email.raw_token,
    'new-password-99',  # pragma: allowlist secret
  )

  refreshed = await session.get(User, user.id)
  assert refreshed is not None
  assert refreshed.is_email_verified
  assert refreshed.is_active
  assert verify_password('new-password-99', refreshed.password_hash)
  assert not verify_password('password-12345', refreshed.password_hash)

  stored_reset = await session.scalar(
    select(PasswordResetToken).where(
      PasswordResetToken.token_hash == reset_email.token_hash
    )
  )
  assert stored_reset is not None
  assert stored_reset.consumed_at is not None

  await session.refresh(refresh)
  assert refresh.revoked_at is not None

  with pytest.raises(AuthServiceError) as reuse_info:
    await auth_service.refresh(old_raw)
  assert reuse_info.value.code is AuthServiceErrorCode.INVALID_REFRESH_TOKEN

  with pytest.raises(AuthServiceError) as old_login:
    await auth_service.login(
      'reset@example.com',
      'password-12345',  # pragma: allowlist secret
    )
  assert old_login.value.code is AuthServiceErrorCode.INVALID_CREDENTIALS

  tokens = await auth_service.login(
    'reset@example.com',
    'new-password-99',  # pragma: allowlist secret
  )
  assert_token_response(tokens, user_id=user.id)
  await assert_refresh_token_persisted(
    session,
    raw_refresh_token=tokens.refresh_token,
    user_id=user.id,
  )


async def test_reset_password_rejects_invalid_token(
  auth_service: AuthService,
) -> None:
  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.reset_password(
      'x' * 48,
      'new-password-99',  # pragma: allowlist secret
    )
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_PASSWORD_RESET_LINK


async def test_reset_password_rejects_replayed_consumed_token(
  auth_service: AuthService, make_user, session
) -> None:
  user = await make_user(email='replay-reset@example.com')
  token_email = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.password_reset_tokens,
    spec=auth_service._password_reset_spec(),
  )
  await session.commit()

  await auth_service.reset_password(
    token_email.raw_token,
    'new-password-99',  # pragma: allowlist secret
  )
  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.reset_password(
      token_email.raw_token,
      'another-password',  # pragma: allowlist secret
    )
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_PASSWORD_RESET_LINK

  refreshed = await session.get(User, user.id)
  assert refreshed is not None
  assert verify_password('new-password-99', refreshed.password_hash)
  assert not verify_password('another-password', refreshed.password_hash)


async def test_reset_password_rejects_token_for_inactive_user(
  auth_service: AuthService, make_user, session
) -> None:
  user = await make_user(email='inactive-reset@example.com')
  token_email = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.password_reset_tokens,
    spec=auth_service._password_reset_spec(),
  )
  await session.commit()

  stored_user = await session.get(User, user.id)
  assert stored_user is not None
  stored_user.is_active = False
  await session.commit()

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.reset_password(
      token_email.raw_token,
      'new-password-99',  # pragma: allowlist secret
    )
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_PASSWORD_RESET_LINK

  refreshed = await session.get(User, user.id)
  assert refreshed is not None
  assert verify_password('password-12345', refreshed.password_hash)

  stored = await session.scalar(
    select(PasswordResetToken).where(
      PasswordResetToken.token_hash == token_email.token_hash
    )
  )
  assert stored is not None
  assert stored.consumed_at is not None


async def test_reset_password_rejects_email_verification_token(
  auth_service: AuthService, make_user, session
) -> None:
  user = await make_user(
    email='cross-reset@example.com', is_email_verified=False
  )
  verification = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.verification_tokens,
    spec=auth_service._email_verification_spec(),
  )
  await session.commit()

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.reset_password(
      verification.raw_token,
      'new-password-99',  # pragma: allowlist secret
    )
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_PASSWORD_RESET_LINK

  refreshed = await session.get(User, user.id)
  assert refreshed is not None
  assert not refreshed.is_email_verified
  assert verify_password('password-12345', refreshed.password_hash)
