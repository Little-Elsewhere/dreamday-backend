import os
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
  AsyncEngine,
  AsyncSession,
  async_sessionmaker,
  create_async_engine,
)
from sqlalchemy.pool import StaticPool

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

import app.auth.models  # noqa: E402, F401
from app.auth.models import RefreshToken, User  # noqa: E402
from app.auth.service import AuthService, create_refresh_token_record  # noqa: E402
from app.core.base import Base  # noqa: E402
from app.core.database import get_session  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from tests.helpers import SessionFactoryAdapter  # noqa: E402


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
  engine = create_async_engine(
    'sqlite+aiosqlite://',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
  )

  @event.listens_for(engine.sync_engine, 'connect')
  def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()

  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  yield engine
  await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
  session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
  )
  async with session_factory() as db_session:
    yield db_session


@pytest.fixture
async def auth_service(session: AsyncSession):
  return AuthService(session)


@pytest.fixture
async def client(
  session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
  async def override_get_session() -> AsyncIterator[AsyncSession]:
    yield session

  async def _noop_send(_email: str, _token: str) -> None:
    return None

  monkeypatch.setattr('app.auth.router.send_verification_email', _noop_send)
  monkeypatch.setattr('app.auth.router.send_password_reset_email', _noop_send)
  monkeypatch.setattr(
    'app.auth.service.SessionFactory',
    SessionFactoryAdapter(session),
  )

  app.dependency_overrides[get_session] = override_get_session
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url='http://test') as ac:
    yield ac
  app.dependency_overrides.clear()


@pytest.fixture
def make_user(session: AsyncSession):
  async def _make_user(
    *,
    email: str = 'user@example.com',
    password: str = 'password-12345',  # pragma: allowlist secret
    is_email_verified: bool = True,
    is_active: bool = True,
  ) -> User:
    user = User(
      id=uuid4(),
      email=email,
      password_hash=hash_password(password),
      is_email_verified=is_email_verified,
      is_active=is_active,
      created_at=datetime.now(UTC),
    )
    session.add(user)
    await session.commit()
    return user

  return _make_user


@pytest.fixture
def make_refresh_token(session: AsyncSession):
  async def _make_refresh_token(
    user: User,
    *,
    raw_token: str | None = None,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
  ) -> tuple[str, RefreshToken]:
    raw = raw_token or secrets.token_urlsafe(48)
    token = create_refresh_token_record(
      user.id,
      uuid4(),
      raw,
      expires_at or (datetime.now(UTC) + timedelta(days=7)),
    )
    token.revoked_at = revoked_at
    session.add(token)
    await session.commit()
    return raw, token

  return _make_refresh_token
