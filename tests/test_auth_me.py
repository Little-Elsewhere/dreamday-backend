from uuid import uuid4

from httpx import AsyncClient

from app.auth.messages import AuthMessages
from app.core.security import create_access_token
from tests.helpers import encode_access_token


async def test_me_returns_current_user(client: AsyncClient, make_user) -> None:
  user = await make_user(email='me@example.com')
  login = await client.post(
    '/api/v1/auth/login',
    json={
      'email': 'me@example.com',
      'password': 'password-12345',  # pragma: allowlist secret
    },
  )

  me = await client.get(
    '/api/v1/auth/me',
    headers={'Authorization': f'Bearer {login.json()["access_token"]}'},
  )
  assert me.status_code == 200
  body = me.json()
  assert body['id'] == str(user.id)
  assert body['email'] == 'me@example.com'
  assert body['is_email_verified'] is True
  created_at = body['created_at']
  assert created_at.endswith('Z')
  assert 'T' in created_at


async def test_me_requires_bearer(client: AsyncClient) -> None:
  response = await client.get('/api/v1/auth/me')
  assert response.status_code == 401
  assert (
    response.json()['detail']
    == AuthMessages.BEARER_ACCESS_TOKEN_REQUIRED.model_dump()
  )


async def test_me_rejects_expired_access_token(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='expired-access@example.com')
  token = encode_access_token(user_id=user.id, expired=True)

  response = await client.get(
    '/api/v1/auth/me',
    headers={'Authorization': f'Bearer {token}'},
  )
  assert response.status_code == 401
  assert (
    response.json()['detail']
    == AuthMessages.INVALID_OR_EXPIRED_ACCESS_TOKEN.model_dump()
  )


async def test_me_rejects_tampered_or_wrong_secret_token(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='bad-secret@example.com')
  token = encode_access_token(
    user_id=user.id,
    secret='wrong-secret-key-that-is-long-enough-32',  # pragma: allowlist secret
  )

  response = await client.get(
    '/api/v1/auth/me',
    headers={'Authorization': f'Bearer {token}'},
  )
  assert response.status_code == 401
  assert (
    response.json()['detail']
    == AuthMessages.INVALID_OR_EXPIRED_ACCESS_TOKEN.model_dump()
  )


async def test_me_rejects_wrong_issuer_and_audience(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='claims@example.com')

  wrong_iss = await client.get(
    '/api/v1/auth/me',
    headers={
      'Authorization': (
        f'Bearer {encode_access_token(user_id=user.id, iss="other")}'
      )
    },
  )
  wrong_aud = await client.get(
    '/api/v1/auth/me',
    headers={
      'Authorization': (
        f'Bearer {encode_access_token(user_id=user.id, aud="other")}'
      )
    },
  )
  assert wrong_iss.status_code == 401
  assert wrong_aud.status_code == 401
  assert (
    wrong_iss.json()['detail']
    == AuthMessages.INVALID_OR_EXPIRED_ACCESS_TOKEN.model_dump()
  )
  assert (
    wrong_aud.json()['detail']
    == AuthMessages.INVALID_OR_EXPIRED_ACCESS_TOKEN.model_dump()
  )


async def test_me_rejects_refresh_token_used_as_bearer(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='refresh-as-access@example.com')
  token = encode_access_token(user_id=user.id, typ='refresh')

  response = await client.get(
    '/api/v1/auth/me',
    headers={'Authorization': f'Bearer {token}'},
  )
  assert response.status_code == 401
  assert (
    response.json()['detail']
    == AuthMessages.INVALID_OR_EXPIRED_ACCESS_TOKEN.model_dump()
  )


async def test_me_rejects_disabled_user_access_token(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(email='disabled-me@example.com', is_active=False)
  token = create_access_token(user.id)

  response = await client.get(
    '/api/v1/auth/me',
    headers={'Authorization': f'Bearer {token}'},
  )
  assert response.status_code == 401
  assert (
    response.json()['detail']
    == AuthMessages.INVALID_OR_EXPIRED_ACCESS_TOKEN.model_dump()
  )


async def test_me_rejects_unverified_user_access_token(
  client: AsyncClient, make_user
) -> None:
  user = await make_user(
    email='unverified-me@example.com', is_email_verified=False
  )
  token = create_access_token(user.id)

  response = await client.get(
    '/api/v1/auth/me',
    headers={'Authorization': f'Bearer {token}'},
  )
  assert response.status_code == 401
  assert (
    response.json()['detail']
    == AuthMessages.INVALID_OR_EXPIRED_ACCESS_TOKEN.model_dump()
  )


async def test_me_rejects_access_token_for_unknown_user(
  client: AsyncClient,
) -> None:
  token = create_access_token(uuid4())

  response = await client.get(
    '/api/v1/auth/me',
    headers={'Authorization': f'Bearer {token}'},
  )
  assert response.status_code == 401
  assert (
    response.json()['detail']
    == AuthMessages.INVALID_OR_EXPIRED_ACCESS_TOKEN.model_dump()
  )
