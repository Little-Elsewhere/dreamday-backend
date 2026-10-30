from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.messages import AuthMessages
from app.auth.models import EmailVerificationToken, User
from app.auth.service import AuthService, AuthServiceError, AuthServiceErrorCode
from app.core.config import settings
from app.core.datetime import utc_now
from app.core.security import hash_secret
from tests.helpers import assert_validation_error


async def test_resend_verification_rejects_invalid_or_missing_email(
  client: AsyncClient,
) -> None:
  invalid_email = await client.post(
    '/api/v1/auth/resend-verification',
    json={'email': 'not-an-email'},
  )
  missing_email = await client.post(
    '/api/v1/auth/resend-verification',
    json={},
  )
  assert_validation_error(invalid_email, 'email')
  assert_validation_error(missing_email, 'email')


async def test_resend_verification_response_does_not_enumerate_accounts(
  client: AsyncClient, make_user
) -> None:
  await make_user(email='known-unverified@example.com', is_email_verified=False)
  await make_user(email='known-verified@example.com', is_email_verified=True)

  unknown = await client.post(
    '/api/v1/auth/resend-verification',
    json={'email': 'nobody@example.com'},
  )
  unverified = await client.post(
    '/api/v1/auth/resend-verification',
    json={'email': 'known-unverified@example.com'},
  )
  verified = await client.post(
    '/api/v1/auth/resend-verification',
    json={'email': 'known-verified@example.com'},
  )

  expected = AuthMessages.VERIFICATION_RESEND_ACCEPTED.model_dump()
  assert (
    unknown.status_code == unverified.status_code == verified.status_code == 202
  )
  assert unknown.json() == unverified.json() == verified.json() == expected
  assert 'token' not in unknown.json()
  assert 'token' not in unverified.json()
  assert 'token' not in verified.json()


async def test_resend_verification_returns_none_for_verified_or_missing(
  auth_service: AuthService, make_user
) -> None:
  await make_user(email='verified-resend@example.com', is_email_verified=True)

  assert await auth_service.resend_verification('missing@example.com') is None
  assert (
    await auth_service.resend_verification('verified-resend@example.com')
    is None
  )


async def test_resend_verification_reuses_token_during_cooldown(
  auth_service: AuthService, make_user
) -> None:
  user = await make_user(
    email='cooldown-reuse@example.com', is_email_verified=False
  )
  first = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.verification_tokens,
    spec=auth_service._email_verification_spec(),
  )
  await auth_service.session.commit()

  second = await auth_service.resend_verification('cooldown-reuse@example.com')
  assert second is not None
  assert second.email == 'cooldown-reuse@example.com'
  assert second.raw_token == first.raw_token
  assert second.token_hash == first.token_hash

  stored = await auth_service.session.scalar(
    select(EmailVerificationToken).where(
      EmailVerificationToken.token_hash == first.token_hash
    )
  )
  assert stored is not None
  assert stored.consumed_at is None
  assert stored.user_id == user.id


async def test_resend_after_cooldown_invalidates_previous_verification_token(
  auth_service: AuthService, make_user, session
) -> None:
  user = await make_user(
    email='cooldown-verify@example.com', is_email_verified=False
  )
  first = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.verification_tokens,
    spec=auth_service._email_verification_spec(),
  )
  await session.commit()

  stored = await session.scalar(
    select(EmailVerificationToken).where(
      EmailVerificationToken.token_hash == first.token_hash
    )
  )
  assert stored is not None
  stored.created_at = utc_now() - timedelta(
    seconds=settings.email_verification_resend_cooldown_seconds + 5
  )
  await session.commit()

  second = await auth_service.resend_verification('cooldown-verify@example.com')
  assert second is not None
  assert second.raw_token != first.raw_token
  assert second.token_hash == hash_secret(second.raw_token)

  await session.refresh(stored)
  assert stored.consumed_at is not None

  replacement = await session.scalar(
    select(EmailVerificationToken).where(
      EmailVerificationToken.token_hash == second.token_hash
    )
  )
  assert replacement is not None
  assert replacement.consumed_at is None

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.verify_email(first.raw_token)
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_VERIFICATION_LINK

  await auth_service.verify_email(second.raw_token)
  refreshed = await session.get(User, user.id)
  assert refreshed is not None
  assert refreshed.is_email_verified

  await session.refresh(replacement)
  assert replacement.consumed_at is not None
