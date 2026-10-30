import pytest
from httpx import AsyncClient

from app.auth.messages import AuthMessages
from app.auth.schemas import LoginRequest
from app.auth.service import AuthService, AuthServiceError, AuthServiceErrorCode
from tests.helpers import (
  assert_refresh_token_persisted,
  assert_token_response,
  assert_validation_error,
)


def test_login_request_allows_any_nonempty_password() -> None:
  payload = LoginRequest(email='user@example.com', password='x')
  assert payload.password == 'x'


async def test_login_rejects_invalid_email_and_password_bounds(
  client: AsyncClient,
) -> None:
  invalid_email = await client.post(
    '/api/v1/auth/login',
    json={
      'email': 'not-an-email',
      'password': 'password-12345',  # pragma: allowlist secret
    },
  )
  empty_password = await client.post(
    '/api/v1/auth/login',
    json={'email': 'empty-pass@example.com', 'password': ''},
  )
  long_password = await client.post(
    '/api/v1/auth/login',
    json={
      'email': 'long-pass@example.com',
      'password': 'p' * 129,  # pragma: allowlist secret
    },
  )
  missing_fields = await client.post('/api/v1/auth/login', json={})
  assert_validation_error(invalid_email, 'email')
  assert_validation_error(empty_password, 'password')
  assert_validation_error(long_password, 'password')
  assert_validation_error(missing_fields, 'email', 'password')


async def test_login_normalizes_email(
  client: AsyncClient, make_user, session
) -> None:
  user = await make_user(email='normalize-login@example.com')

  response = await client.post(
    '/api/v1/auth/login',
    json={
      'email': '  Normalize-Login@Example.com ',
      'password': 'password-12345',  # pragma: allowlist secret
    },
  )
  assert response.status_code == 200
  tokens = response.json()
  assert_token_response(tokens, user_id=user.id)
  await assert_refresh_token_persisted(
    session,
    raw_refresh_token=tokens['refresh_token'],
    user_id=user.id,
  )


async def test_login_missing_user_and_wrong_password_share_invalid_credentials(
  client: AsyncClient, make_user
) -> None:
  await make_user(email='known-login@example.com')

  missing = await client.post(
    '/api/v1/auth/login',
    json={
      'email': 'missing-login@example.com',
      'password': 'password-12345',  # pragma: allowlist secret
    },
  )
  wrong = await client.post(
    '/api/v1/auth/login',
    json={
      'email': 'known-login@example.com',
      'password': 'not-the-password',  # pragma: allowlist secret
    },
  )

  expected = AuthMessages.INVALID_CREDENTIALS.model_dump()
  assert missing.status_code == wrong.status_code == 401
  assert missing.json()['detail'] == wrong.json()['detail'] == expected
  assert missing.headers.get('www-authenticate') == 'Bearer'
  assert wrong.headers.get('www-authenticate') == 'Bearer'


async def test_login_success_returns_token_pair(
  auth_service: AuthService, make_user, session
) -> None:
  user = await make_user(email='login-service@example.com')
  tokens = await auth_service.login(
    'login-service@example.com',
    'password-12345',  # pragma: allowlist secret
  )
  assert_token_response(tokens, user_id=user.id)
  await assert_refresh_token_persisted(
    session,
    raw_refresh_token=tokens.refresh_token,
    user_id=user.id,
  )


@pytest.mark.parametrize(
  ('email', 'password', 'is_verified', 'is_active', 'expected'),
  [
    (
      'missing@example.com',
      'password-12345',  # pragma: allowlist secret
      True,
      True,
      AuthServiceErrorCode.INVALID_CREDENTIALS,
    ),
    (
      'login-errors@example.com',
      'wrong-password-1',  # pragma: allowlist secret
      True,
      True,
      AuthServiceErrorCode.INVALID_CREDENTIALS,
    ),
    (
      'login-errors@example.com',
      'password-12345',  # pragma: allowlist secret
      False,
      True,
      AuthServiceErrorCode.EMAIL_NOT_VERIFIED,
    ),
    (
      'login-errors@example.com',
      'password-12345',  # pragma: allowlist secret
      True,
      False,
      AuthServiceErrorCode.ACCOUNT_DISABLED,
    ),
  ],
)
async def test_login_error_paths(
  auth_service: AuthService,
  make_user,
  email: str,
  password: str,
  is_verified: bool,
  is_active: bool,
  expected: AuthServiceErrorCode,
) -> None:
  if email == 'login-errors@example.com':
    await make_user(
      email=email,
      is_email_verified=is_verified,
      is_active=is_active,
    )

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.login(email, password)
  assert exc_info.value.code is expected
