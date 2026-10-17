from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
  return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
  return password_hash.verify(password, hashed_password)


def hash_secret(secret: str) -> str:
  return sha256(secret.encode('utf-8')).hexdigest()


def create_access_token(user_id: UUID) -> str:
  now = datetime.now(UTC)
  expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
  payload = {
    'sub': str(user_id),
    'typ': 'access',
    'iss': settings.jwt_issuer,
    'aud': settings.jwt_audience,
    'iat': now,
    'exp': expires_at,
    'jti': str(uuid4()),
  }
  return jwt.encode(
    payload,
    settings.jwt_secret_key.get_secret_value(),
    algorithm='HS256',
  )


def decode_access_token(token: str) -> UUID:
  payload = jwt.decode(
    token,
    settings.jwt_secret_key.get_secret_value(),
    algorithms=['HS256'],
    audience=settings.jwt_audience,
    issuer=settings.jwt_issuer,
    options={'require': ['exp', 'iat', 'sub', 'typ', 'jti']},
  )
  if payload.get('typ') != 'access':
    raise jwt.InvalidTokenError('Wrong token type')
  try:
    return UUID(payload['sub'])
  except (TypeError, ValueError) as error:
    raise jwt.InvalidTokenError('Invalid subject') from error
