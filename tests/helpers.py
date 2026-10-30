from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from httpx import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken
from app.auth.schemas import TokenResponse
from app.core.config import settings
from app.core.datetime import utc_now
from app.core.security import decode_access_token, hash_secret


def assert_token_response(
  tokens: TokenResponse | dict[str, Any],
  *,
  user_id: UUID | None = None,
) -> UUID:
  body = tokens.model_dump() if isinstance(tokens, TokenResponse) else tokens
  assert body['token_type'] == 'bearer'
  assert isinstance(body['access_token'], str) and body['access_token']
  assert isinstance(body['refresh_token'], str) and body['refresh_token']
  assert 32 <= len(body['refresh_token']) <= 256
  assert body['expires_in'] == settings.access_token_expire_minutes * 60
  assert (
    body['refresh_expires_in']
    == settings.refresh_token_expire_days * 24 * 60 * 60
  )

  subject = decode_access_token(body['access_token'])
  if user_id is not None:
    assert subject == user_id
  return subject


async def assert_refresh_token_persisted(
  session: AsyncSession,
  *,
  raw_refresh_token: str,
  user_id: UUID,
) -> RefreshToken:
  stored = await session.scalar(
    select(RefreshToken).where(
      RefreshToken.token_hash == hash_secret(raw_refresh_token)
    )
  )
  assert stored is not None
  assert stored.user_id == user_id
  assert stored.revoked_at is None
  assert stored.expires_at > utc_now()
  return stored


def assert_validation_error(response: Response, *fields: str) -> None:
  assert response.status_code == 422, response.text
  detail = response.json()['detail']
  assert isinstance(detail, list) and detail
  reported = {
    item['loc'][-1]
    for item in detail
    if isinstance(item.get('loc'), list) and item['loc']
  }
  expected = set(fields)
  assert expected <= reported, (
    f'expected validation fields {sorted(expected)}, got {sorted(reported)}'
  )


class SessionFactoryAdapter:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  def __call__(self) -> SessionFactoryAdapter:
    return self

  async def __aenter__(self) -> AsyncSession:
    return self._session

  async def __aexit__(self, *_exc: object) -> None:
    return None


def encode_access_token(
  *,
  user_id: UUID | None = None,
  typ: str = 'access',
  secret: str | None = None,
  iss: str | None = None,
  aud: str | None = None,
  expired: bool = False,
) -> str:
  now = utc_now()
  payload = {
    'sub': str(user_id or uuid4()),
    'typ': typ,
    'iss': iss if iss is not None else settings.jwt_issuer,
    'aud': aud if aud is not None else settings.jwt_audience,
    'iat': now - timedelta(hours=2) if expired else now,
    'exp': now - timedelta(hours=1) if expired else now + timedelta(minutes=15),
    'jti': str(uuid4()),
  }
  return jwt.encode(
    payload,
    secret or settings.jwt_secret_key.get_secret_value(),
    algorithm='HS256',
  )
