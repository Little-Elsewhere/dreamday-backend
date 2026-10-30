from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.messages import AuthMessages
from app.auth.models import PasswordResetToken
from app.auth.service import AuthService, AuthServiceError, AuthServiceErrorCode
from app.core.config import settings
from app.core.datetime import utc_now
from app.core.security import hash_secret
from tests.helpers import assert_validation_error


async def test_forgot_password_rejects_invalid_or_missing_email(
  client: AsyncClient,
) -> None:
  invalid_email = await client.post(
    '/api/v1/auth/forgot-password',
    json={'email': 'not-an-email'},
  )
  missing_email = await client.post('/api/v1/auth/forgot-password', json={})
  assert_validation_error(invalid_email, 'email')
  assert_validation_error(missing_email, 'email')


async def test_forgot_password_response_does_not_enumerate_accounts(
  client: AsyncClient, make_user
) -> None:
  await make_user(email='known-reset@example.com')

  unknown = await client.post(
    '/api/v1/auth/forgot-password',
    json={'email': 'nobody@example.com'},
  )
  known = await client.post(
    '/api/v1/auth/forgot-password',
    json={'email': 'known-reset@example.com'},
  )

  expected = AuthMessages.PASSWORD_RESET_EMAIL_ACCEPTED.model_dump()
  assert unknown.status_code == known.status_code == 202
  assert unknown.json() == known.json() == expected
  assert 'token' not in unknown.json()
  assert 'token' not in known.json()


async def test_forgot_password_returns_none_for_unknown_email(
  auth_service: AuthService,
) -> None:
  assert await auth_service.forgot_password('nobody@example.com') is None


async def test_password_reset_cooldown_reuses_token(
  auth_service: AuthService, make_user
) -> None:
  user = await make_user(email='cooldown@example.com')
  first = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.password_reset_tokens,
    spec=auth_service._password_reset_spec(),
  )
  await auth_service.session.commit()

  second = await auth_service.forgot_password('cooldown@example.com')
  assert second is not None
  assert second.email == 'cooldown@example.com'
  assert second.raw_token == first.raw_token
  assert second.token_hash == first.token_hash

  stored = await auth_service.session.scalar(
    select(PasswordResetToken).where(
      PasswordResetToken.token_hash == first.token_hash
    )
  )
  assert stored is not None
  assert stored.consumed_at is None
  assert stored.user_id == user.id


async def test_forgot_after_cooldown_invalidates_previous_reset_token(
  auth_service: AuthService, make_user, session
) -> None:
  user = await make_user(email='cooldown-reset@example.com')
  first = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.password_reset_tokens,
    spec=auth_service._password_reset_spec(),
  )
  await session.commit()

  stored = await session.scalar(
    select(PasswordResetToken).where(
      PasswordResetToken.token_hash == first.token_hash
    )
  )
  assert stored is not None
  stored.created_at = utc_now() - timedelta(
    seconds=settings.password_reset_resend_cooldown_seconds + 5
  )
  await session.commit()

  second = await auth_service.forgot_password('cooldown-reset@example.com')
  assert second is not None
  assert second.raw_token != first.raw_token
  assert second.token_hash == hash_secret(second.raw_token)

  await session.refresh(stored)
  assert stored.consumed_at is not None

  replacement = await session.scalar(
    select(PasswordResetToken).where(
      PasswordResetToken.token_hash == second.token_hash
    )
  )
  assert replacement is not None
  assert replacement.consumed_at is None
  assert replacement.user_id == user.id

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.reset_password(
      first.raw_token,
      'new-password-99',  # pragma: allowlist secret
    )
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_PASSWORD_RESET_LINK
