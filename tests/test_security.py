import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core.config import settings
from app.core.datetime import utc_now
from app.core.security import (
  create_access_token,
  create_purpose_token,
  decode_access_token,
  hash_password,
  hash_secret,
  verify_password,
)


def test_hash_and_verify_password() -> None:
  hashed = hash_password('correct-horse-battery')
  assert hashed != 'correct-horse-battery'
  assert hashed.startswith('$argon2')
  assert verify_password('correct-horse-battery', hashed)
  assert not verify_password('wrong-password', hashed)


def test_hash_secret_is_deterministic_sha256() -> None:
  assert hash_secret('opaque-token') == hash_secret('opaque-token')
  assert hash_secret('opaque-token') != hash_secret('other-token')
  assert len(hash_secret('opaque-token')) == 64


def test_access_token_round_trip() -> None:
  user_id = uuid4()
  token = create_access_token(user_id)
  assert decode_access_token(token) == user_id


def _access_payload(
  *,
  sub: str | None = None,
  typ: str = 'access',
  iss: str | None = None,
  aud: str | None = None,
  iat: datetime | None = None,
  exp: datetime | None = None,
) -> dict:
  now = utc_now()
  return {
    'sub': sub if sub is not None else str(uuid4()),
    'typ': typ,
    'iss': iss if iss is not None else settings.jwt_issuer,
    'aud': aud if aud is not None else settings.jwt_audience,
    'iat': iat if iat is not None else now,
    'exp': exp if exp is not None else now + timedelta(minutes=15),
    'jti': str(uuid4()),
  }


def test_decode_access_token_rejects_wrong_type() -> None:
  token = jwt.encode(
    _access_payload(typ='refresh'),
    settings.jwt_secret_key.get_secret_value(),
    algorithm='HS256',
  )
  with pytest.raises(jwt.InvalidTokenError):
    decode_access_token(token)


def test_decode_access_token_rejects_invalid_subject() -> None:
  token = jwt.encode(
    _access_payload(sub='not-a-uuid'),
    settings.jwt_secret_key.get_secret_value(),
    algorithm='HS256',
  )
  with pytest.raises(jwt.InvalidTokenError):
    decode_access_token(token)


def test_decode_access_token_rejects_expired() -> None:
  now = utc_now()
  token = jwt.encode(
    _access_payload(
      iat=now - timedelta(hours=2),
      exp=now - timedelta(hours=1),
    ),
    settings.jwt_secret_key.get_secret_value(),
    algorithm='HS256',
  )
  with pytest.raises(jwt.InvalidTokenError):
    decode_access_token(token)


def test_decode_access_token_rejects_wrong_issuer() -> None:
  token = jwt.encode(
    _access_payload(iss='other-issuer'),
    settings.jwt_secret_key.get_secret_value(),
    algorithm='HS256',
  )
  with pytest.raises(jwt.InvalidTokenError):
    decode_access_token(token)


def test_decode_access_token_rejects_wrong_audience() -> None:
  token = jwt.encode(
    _access_payload(aud='other-audience'),
    settings.jwt_secret_key.get_secret_value(),
    algorithm='HS256',
  )
  with pytest.raises(jwt.InvalidTokenError):
    decode_access_token(token)


def test_decode_access_token_rejects_wrong_secret() -> None:
  token = jwt.encode(
    _access_payload(),
    'wrong-secret-key-that-is-long-enough-32',
    algorithm='HS256',
  )
  with pytest.raises(jwt.InvalidTokenError):
    decode_access_token(token)


def test_decode_access_token_rejects_alg_none() -> None:
  def b64url(data: dict) -> str:
    raw = json.dumps(data, separators=(',', ':')).encode('utf-8')
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')

  now = utc_now()
  payload = {
    'sub': str(uuid4()),
    'typ': 'access',
    'iss': settings.jwt_issuer,
    'aud': settings.jwt_audience,
    'iat': int(now.timestamp()),
    'exp': int((now + timedelta(minutes=15)).timestamp()),
    'jti': str(uuid4()),
  }
  token = f'{b64url({"alg": "none", "typ": "JWT"})}.{b64url(payload)}.'
  with pytest.raises(jwt.InvalidTokenError):
    decode_access_token(token)


def test_create_purpose_token_encodes_claims() -> None:
  user_id = uuid4()
  token_id = uuid4()
  issued_at = datetime.now(UTC).replace(microsecond=0)
  expires_at = issued_at + timedelta(minutes=60)
  token = create_purpose_token(
    typ='email_verify',
    user_id=user_id,
    email='user@example.com',
    token_id=token_id,
    issued_at=issued_at,
    expires_at=expires_at,
  )
  payload = jwt.decode(
    token,
    settings.jwt_secret_key.get_secret_value(),
    algorithms=['HS256'],
  )
  assert payload['sub'] == str(user_id)
  assert payload['email'] == 'user@example.com'
  assert payload['typ'] == 'email_verify'
  assert payload['jti'] == str(token_id)
