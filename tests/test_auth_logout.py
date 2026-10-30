import pytest
from httpx import AsyncClient

from app.auth.messages import AuthMessages
from app.auth.service import AuthService, AuthServiceError, AuthServiceErrorCode
from tests.helpers import assert_validation_error


async def test_logout_unknown_refresh_token_is_idempotent(
  client: AsyncClient,
) -> None:
  response = await client.post(
    '/api/v1/auth/logout',
    json={'refresh_token': 'x' * 48},
  )
  assert response.status_code == 200
  assert response.json() == AuthMessages.LOGGED_OUT.model_dump()


async def test_logout_rejects_invalid_token_bounds(client: AsyncClient) -> None:
  too_short = await client.post(
    '/api/v1/auth/logout',
    json={'refresh_token': 'short'},
  )
  too_long = await client.post(
    '/api/v1/auth/logout',
    json={'refresh_token': 'x' * 257},
  )
  missing = await client.post('/api/v1/auth/logout', json={})
  assert_validation_error(too_short, 'refresh_token')
  assert_validation_error(too_long, 'refresh_token')
  assert_validation_error(missing, 'refresh_token')


async def test_logout_revokes_active_refresh_token(
  auth_service: AuthService, make_user, make_refresh_token, session
) -> None:
  user = await make_user(email='logout-service@example.com')
  raw, stored = await make_refresh_token(user)
  assert stored.revoked_at is None

  await auth_service.logout(raw)

  await session.refresh(stored)
  assert stored.revoked_at is not None
  assert stored.replaced_by_id is None

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.refresh(raw)
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_REFRESH_TOKEN

  await auth_service.logout(raw)
  await session.refresh(stored)
  assert stored.revoked_at is not None
