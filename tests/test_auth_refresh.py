from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.models import RefreshToken
from app.auth.service import AuthService, AuthServiceError, AuthServiceErrorCode
from app.core.datetime import utc_now
from app.core.security import hash_secret
from tests.helpers import assert_token_response, assert_validation_error


async def test_refresh_rejects_invalid_token_bounds(
  client: AsyncClient,
) -> None:
  too_short = await client.post(
    '/api/v1/auth/refresh',
    json={'refresh_token': 'short'},
  )
  too_long = await client.post(
    '/api/v1/auth/refresh',
    json={'refresh_token': 'x' * 257},
  )
  missing = await client.post('/api/v1/auth/refresh', json={})
  assert_validation_error(too_short, 'refresh_token')
  assert_validation_error(too_long, 'refresh_token')
  assert_validation_error(missing, 'refresh_token')


async def test_refresh_rotates_and_revokes_previous(
  auth_service: AuthService, make_user, make_refresh_token, session
) -> None:
  user = await make_user(email='refresh-rotate@example.com')
  raw, stored = await make_refresh_token(user)

  tokens = await auth_service.refresh(raw)
  assert_token_response(tokens, user_id=user.id)
  assert tokens.refresh_token != raw

  await session.refresh(stored)
  assert stored.revoked_at is not None
  assert stored.replaced_by_id is not None

  replacement = await session.get(RefreshToken, stored.replaced_by_id)
  assert replacement is not None
  assert replacement.user_id == user.id
  assert replacement.family_id == stored.family_id
  assert replacement.token_hash == hash_secret(tokens.refresh_token)
  assert replacement.revoked_at is None
  assert replacement.expires_at > utc_now()


async def test_refresh_reuse_of_revoked_token_revokes_family(
  auth_service: AuthService, make_user, make_refresh_token, session
) -> None:
  user = await make_user(email='refresh-family@example.com')
  raw, stored = await make_refresh_token(user)
  rotated = await auth_service.refresh(raw)
  assert_token_response(rotated, user_id=user.id)

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.refresh(raw)
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_REFRESH_TOKEN

  family_tokens = (
    await session.scalars(
      select(RefreshToken).where(RefreshToken.family_id == stored.family_id)
    )
  ).all()
  assert len(family_tokens) >= 2
  assert all(token.revoked_at is not None for token in family_tokens)

  with pytest.raises(AuthServiceError) as rotated_info:
    await auth_service.refresh(rotated.refresh_token)
  assert rotated_info.value.code is AuthServiceErrorCode.INVALID_REFRESH_TOKEN


async def test_refresh_rejects_expired_token(
  auth_service: AuthService, make_user, make_refresh_token, session
) -> None:
  user = await make_user(email='refresh-expired@example.com')
  raw, stored = await make_refresh_token(
    user, expires_at=utc_now() - timedelta(seconds=1)
  )

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.refresh(raw)
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_REFRESH_TOKEN

  await session.refresh(stored)
  assert stored.revoked_at is not None


async def test_refresh_rejects_token_when_user_disabled(
  auth_service: AuthService, make_user, make_refresh_token, session
) -> None:
  user = await make_user(email='refresh-disabled@example.com')
  raw, stored = await make_refresh_token(user)
  user.is_active = False
  await session.commit()

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.refresh(raw)
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_REFRESH_TOKEN

  await session.refresh(stored)
  assert stored.revoked_at is not None


async def test_refresh_rejects_token_when_user_unverified(
  auth_service: AuthService, make_user, make_refresh_token, session
) -> None:
  user = await make_user(email='refresh-unverified@example.com')
  raw, stored = await make_refresh_token(user)
  user.is_email_verified = False
  await session.commit()

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.refresh(raw)
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_REFRESH_TOKEN

  await session.refresh(stored)
  assert stored.revoked_at is not None
