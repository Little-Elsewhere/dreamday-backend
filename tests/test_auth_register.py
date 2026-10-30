import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.messages import AuthMessages
from app.auth.models import EmailVerificationToken, User
from app.auth.schemas import RegisterRequest, normalize_email
from app.auth.service import (
  AuthService,
  AuthServiceError,
  AuthServiceErrorCode,
  deliver_token_email_in_background,
)
from app.core.security import hash_secret, verify_password
from tests.helpers import SessionFactoryAdapter, assert_validation_error


def test_normalize_email_strips_and_lowercases() -> None:
  assert normalize_email('  User@Example.COM ') == 'user@example.com'


def test_register_request_normalizes_email() -> None:
  payload = RegisterRequest(
    email='  User@Example.COM ',
    password='password-12345',  # pragma: allowlist secret
  )
  assert payload.email == 'user@example.com'
  assert payload.password == 'password-12345'  # pragma: allowlist secret


async def test_register_accepted_without_tokens(client: AsyncClient) -> None:
  response = await client.post(
    '/api/v1/auth/register',
    json={
      'email': 'New@Example.com',
      'password': 'password-12345',  # pragma: allowlist secret
    },
  )
  assert response.status_code == 202
  body = response.json()
  assert body == AuthMessages.REGISTRATION_ACCEPTED.model_dump()
  assert 'access_token' not in body
  assert 'refresh_token' not in body
  assert 'expires_in' not in body
  assert 'refresh_expires_in' not in body


async def test_register_rejects_short_and_oversized_password(
  client: AsyncClient,
) -> None:
  short = await client.post(
    '/api/v1/auth/register',
    json={
      'email': 'short-pass@example.com',
      'password': 'short',  # pragma: allowlist secret
    },
  )
  long = await client.post(
    '/api/v1/auth/register',
    json={
      'email': 'long-pass@example.com',
      'password': 'p' * 129,  # pragma: allowlist secret
    },
  )
  assert_validation_error(short, 'password')
  assert_validation_error(long, 'password')


async def test_register_rejects_invalid_or_missing_fields(
  client: AsyncClient,
) -> None:
  invalid_email = await client.post(
    '/api/v1/auth/register',
    json={
      'email': 'not-an-email',
      'password': 'password-12345',  # pragma: allowlist secret
    },
  )
  missing_password = await client.post(
    '/api/v1/auth/register',
    json={'email': 'missing-pass@example.com'},
  )
  missing_email = await client.post(
    '/api/v1/auth/register',
    json={'password': 'password-12345'},  # pragma: allowlist secret
  )
  empty_body = await client.post('/api/v1/auth/register', json={})
  assert_validation_error(invalid_email, 'email')
  assert_validation_error(missing_password, 'password')
  assert_validation_error(missing_email, 'email')
  assert_validation_error(empty_body, 'email', 'password')


async def test_register_accepts_password_boundary_length(
  client: AsyncClient,
) -> None:
  response = await client.post(
    '/api/v1/auth/register',
    json={
      'email': 'boundary-pass@example.com',
      'password': 'p' * 12,  # pragma: allowlist secret
    },
  )
  assert response.status_code == 202
  assert response.json() == AuthMessages.REGISTRATION_ACCEPTED.model_dump()


async def test_register_creates_user_and_verification_token(
  auth_service: AuthService, session
) -> None:
  token_email = await auth_service.register(
    'new@example.com',
    'password-12345',  # pragma: allowlist secret
  )

  user = await session.scalar(
    select(User).where(User.email == 'new@example.com')
  )
  assert user is not None
  assert user.email == 'new@example.com'
  assert user.is_active
  assert not user.is_email_verified
  assert verify_password('password-12345', user.password_hash)
  assert token_email.email == 'new@example.com'
  assert token_email.raw_token
  assert token_email.token_hash == hash_secret(token_email.raw_token)

  stored = await session.scalar(
    select(EmailVerificationToken).where(
      EmailVerificationToken.token_hash == token_email.token_hash
    )
  )
  assert stored is not None
  assert stored.user_id == user.id
  assert stored.consumed_at is None
  assert stored.expires_at > stored.created_at


async def test_register_rejects_existing_email(
  auth_service: AuthService, make_user
) -> None:
  await make_user(email='taken-service@example.com')

  with pytest.raises(AuthServiceError) as exc_info:
    await auth_service.register(
      'taken-service@example.com',
      'password-12345',  # pragma: allowlist secret
    )
  assert exc_info.value.code is AuthServiceErrorCode.EMAIL_ALREADY_REGISTERED


async def test_deliver_token_email_consumes_token_on_send_failure(
  session, make_user, monkeypatch
) -> None:
  user = await make_user(email='mailfail@example.com', is_email_verified=False)
  auth_service = AuthService(session)
  token_email = await auth_service._issue_purpose_token(
    user,
    repository=auth_service.verification_tokens,
    spec=auth_service._email_verification_spec(),
  )
  await session.commit()

  monkeypatch.setattr(
    'app.auth.service.SessionFactory',
    SessionFactoryAdapter(session),
  )

  async def boom(_email: str, _token: str) -> None:
    raise RuntimeError('smtp unavailable')

  await deliver_token_email_in_background(
    token_email.email,
    token_email.raw_token,
    token_email.token_hash,
    send=boom,
    model=EmailVerificationToken,
    failure_log='send failed',
  )

  stored = await session.scalar(
    select(EmailVerificationToken).where(
      EmailVerificationToken.token_hash == token_email.token_hash
    )
  )
  assert stored is not None
  assert stored.consumed_at is not None
