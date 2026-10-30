from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.models import EmailVerificationToken, User
from app.auth.service import AuthService, AuthServiceError, AuthServiceErrorCode
from app.core.datetime import utc_now
from app.core.security import hash_secret
from tests.helpers import assert_validation_error


async def test_verify_email_rejects_invalid_token_bounds(
  client: AsyncClient,
) -> None:
  too_short = await client.post(
    '/api/v1/auth/verify-email',
    json={'token': 'short-token'},
  )
  too_long = await client.post(
    '/api/v1/auth/verify-email',
    json={'token': 'x' * 2049},
  )
  missing = await client.post('/api/v1/auth/verify-email', json={})
  assert_validation_error(too_short, 'token')
  assert_validation_error(too_long, 'token')
  assert_validation_error(missing, 'token')


async def test_verify_email_marks_user_verified(
  auth_service: AuthService, make_user, session
) -> None:
  user = await make_user(email='verify@example.com', is_email_verified=False)
  token_email = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.verification_tokens,
    spec=auth_service._email_verification_spec(),
  )
  await session.commit()
  assert token_email.token_hash == hash_secret(token_email.raw_token)

  await auth_service.verify_email(token_email.raw_token)

  refreshed = await session.get(User, user.id)
  assert refreshed is not None
  assert refreshed.is_email_verified
  assert refreshed.is_active

  stored = await session.scalar(
    select(EmailVerificationToken).where(
      EmailVerificationToken.token_hash == token_email.token_hash
    )
  )
  assert stored is not None
  assert stored.consumed_at is not None


async def test_verify_email_rejects_invalid_token(
  auth_service: AuthService,
) -> None:
  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.verify_email('x' * 48)
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_VERIFICATION_LINK


async def test_verify_email_rejects_expired_token(
  auth_service: AuthService, make_user, session
) -> None:
  user = await make_user(email='expired@example.com', is_email_verified=False)
  token_email = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.verification_tokens,
    spec=auth_service._email_verification_spec(),
  )
  stored = await session.scalar(
    select(EmailVerificationToken).where(
      EmailVerificationToken.token_hash == token_email.token_hash
    )
  )
  assert stored is not None
  stored.expires_at = utc_now() - timedelta(minutes=1)
  await session.commit()

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.verify_email(token_email.raw_token)
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_VERIFICATION_LINK

  refreshed = await session.get(User, user.id)
  assert refreshed is not None
  assert not refreshed.is_email_verified


async def test_verify_email_rejects_replayed_consumed_token(
  auth_service: AuthService, make_user, session
) -> None:
  user = await make_user(
    email='replay-verify@example.com', is_email_verified=False
  )
  token_email = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.verification_tokens,
    spec=auth_service._email_verification_spec(),
  )
  await session.commit()

  await auth_service.verify_email(token_email.raw_token)
  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.verify_email(token_email.raw_token)
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_VERIFICATION_LINK

  refreshed = await session.get(User, user.id)
  assert refreshed is not None
  assert refreshed.is_email_verified

  stored = await session.scalar(
    select(EmailVerificationToken).where(
      EmailVerificationToken.token_hash == token_email.token_hash
    )
  )
  assert stored is not None
  assert stored.consumed_at is not None


async def test_verify_email_rejects_token_for_inactive_user(
  auth_service: AuthService, make_user, session
) -> None:
  user = await make_user(
    email='inactive-verify@example.com',
    is_email_verified=False,
  )
  token_email = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.verification_tokens,
    spec=auth_service._email_verification_spec(),
  )
  await session.commit()

  stored_user = await session.get(User, user.id)
  assert stored_user is not None
  stored_user.is_active = False
  await session.commit()

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.verify_email(token_email.raw_token)
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_VERIFICATION_LINK

  refreshed = await session.get(User, user.id)
  assert refreshed is not None
  assert not refreshed.is_email_verified

  stored = await session.scalar(
    select(EmailVerificationToken).where(
      EmailVerificationToken.token_hash == token_email.token_hash
    )
  )
  assert stored is not None
  assert stored.consumed_at is not None


async def test_verify_email_rejects_password_reset_token(
  auth_service: AuthService, make_user, session
) -> None:
  user = await make_user(
    email='cross-verify@example.com', is_email_verified=False
  )
  reset = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.password_reset_tokens,
    spec=auth_service._password_reset_spec(),
  )
  await session.commit()

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.verify_email(reset.raw_token)
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_VERIFICATION_LINK

  refreshed = await session.get(User, user.id)
  assert refreshed is not None
  assert not refreshed.is_email_verified
