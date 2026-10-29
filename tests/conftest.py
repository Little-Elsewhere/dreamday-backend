import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

# Settings load at import time; seed a complete test env before app imports.
_TEST_ENV = {
  'APP_NAME': 'Dreamday API Test',
  'APP_DEBUG': 'false',
  'DB_HOST': 'localhost',
  'DB_PORT': '5432',
  'POSTGRES_USER': 'dreamday',
  'POSTGRES_PASSWORD': 'dreamday-test-password',  # pragma: allowlist secret
  'POSTGRES_DB': 'dreamday_test',
  'JWT_SECRET_KEY': 'test-only-jwt-secret-key-32chars-min',  # pragma: allowlist secret
  'JWT_ISSUER': 'dreamday-test',
  'JWT_AUDIENCE': 'dreamday-test',
  'ACCESS_TOKEN_EXPIRE_MINUTES': '15',
  'REFRESH_TOKEN_EXPIRE_DAYS': '7',
  'EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES': '60',
  'EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS': '60',
  'EMAIL_VERIFICATION_URL': 'http://localhost:4000/verify-email',
  'PASSWORD_RESET_TOKEN_EXPIRE_MINUTES': '60',
  'PASSWORD_RESET_RESEND_COOLDOWN_SECONDS': '60',
  'PASSWORD_RESET_URL': 'http://localhost:4000/reset-password',  # pragma: allowlist secret
  'SMTP_HOST': 'localhost',
  'SMTP_PORT': '1025',
  'SMTP_USERNAME': '',
  'SMTP_PASSWORD': '',  # pragma: allowlist secret
  'SMTP_USE_TLS': 'false',
  'SMTP_START_TLS': 'false',
  'SMTP_TIMEOUT_SECONDS': '5',
  'SMTP_FROM_EMAIL': 'noreply@example.com',
  'SMTP_FROM_NAME': 'Dreamday Test',
}

for key, value in _TEST_ENV.items():
  os.environ.setdefault(key, value)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
  from app.main import app

  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url='http://test') as ac:
    yield ac
