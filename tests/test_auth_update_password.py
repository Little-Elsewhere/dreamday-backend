import pytest
from httpx import AsyncClient

from app.auth.messages import AuthMessages
from app.auth.service import AuthService, AuthServiceError, AuthServiceErrorCode
from app.core.security import create_access_token, verify_password
from tests.helpers import (
  assert_refresh_token_persisted,
  assert_token_response,
  assert_validation_error,
)


async def test_update_password_requires_valid_access_token(
  client: AsyncClient,
) -> None:
  response = await client.post(
    '/api/v1/auth/update-password',
    json={
      'current_password': 'password-12345',  # pragma: allowlist secret
      'new_password': 'brand-new-pass1',  # pragma: allowlist secret
    },
  )
  assert response.status_code == 401
  assert (
    response.json()['detail']
    == AuthMessages.BEARER_ACCESS_TOKEN_REQUIRED.model_dump()
  )
  assert response.headers.get('www-authenticate') == 'Bearer'


async def test_update_password_rejects_invalid_field_bounds(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='validate-update@example.com')
  headers = {'Authorization': f'Bearer {create_access_token(user.id)}'}

  short_new = await client.post(
    '/api/v1/auth/update-password',
    headers=headers,
    json={
      'current_password': 'password-12345',  # pragma: allowlist secret
      'new_password': 'short',  # pragma: allowlist secret
    },
  )
  long_new = await client.post(
    '/api/v1/auth/update-password',
    headers=headers,
    json={
      'current_password': 'password-12345',  # pragma: allowlist secret
      'new_password': 'p' * 129,  # pragma: allowlist secret
    },
  )
  empty_current = await client.post(
    '/api/v1/auth/update-password',
    headers=headers,
    json={
      'current_password': '',
      'new_password': 'brand-new-pass1',  # pragma: allowlist secret
    },
  )
  long_current = await client.post(
    '/api/v1/auth/update-password',
    headers=headers,
    json={
      'current_password': 'c' * 129,  # pragma: allowlist secret
      'new_password': 'brand-new-pass1',  # pragma: allowlist secret
    },
  )
  missing_fields = await client.post(
    '/api/v1/auth/update-password',
    headers=headers,
    json={},
  )
  assert_validation_error(short_new, 'new_password')
  assert_validation_error(long_new, 'new_password')
  assert_validation_error(empty_current, 'current_password')
  assert_validation_error(long_current, 'current_password')
  assert_validation_error(missing_fields, 'current_password', 'new_password')


async def test_update_password_requires_current_and_issues_new_tokens(
  auth_service: AuthService, make_user, make_refresh_token, session
) -> None:
  user = await make_user(email='update@example.com')
  old_raw, old_refresh = await make_refresh_token(user)

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.update_password(
      user,
      'wrong-current-1',  # pragma: allowlist secret
      'brand-new-pass1',  # pragma: allowlist secret
    )
  assert exc_info.value.code is AuthServiceErrorCode.INVALID_CURRENT_PASSWORD
  assert verify_password('password-12345', user.password_hash)

  tokens = await auth_service.update_password(
    user,
    'password-12345',  # pragma: allowlist secret
    'brand-new-pass1',  # pragma: allowlist secret
  )
  assert_token_response(tokens, user_id=user.id)
  assert tokens.refresh_token != old_raw
  assert verify_password('brand-new-pass1', user.password_hash)
  assert not verify_password('password-12345', user.password_hash)
  await assert_refresh_token_persisted(
    session,
    raw_refresh_token=tokens.refresh_token,
    user_id=user.id,
  )

  await session.refresh(old_refresh)
  assert old_refresh.revoked_at is not None

  with pytest.raises(AuthServiceError) as reuse_info:
    await auth_service.refresh(old_raw)
  assert reuse_info.value.code is AuthServiceErrorCode.INVALID_REFRESH_TOKEN

  rotated = await auth_service.refresh(tokens.refresh_token)
  assert_token_response(rotated, user_id=user.id)
  assert rotated.refresh_token != tokens.refresh_token
  await assert_refresh_token_persisted(
    session,
    raw_refresh_token=rotated.refresh_token,
    user_id=user.id,
  )
