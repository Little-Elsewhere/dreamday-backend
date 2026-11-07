from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.messages import AuthMessages
from app.auth.models import User
from app.auth.repositories.users import UserRepository
from app.auth.service import AuthService
from app.core.security import decode_access_token
from app.shared.dependencies import DatabaseSession

bearer_scheme = HTTPBearer(auto_error=False)


def _invalid_access_token_error() -> HTTPException:
  return HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail=AuthMessages.INVALID_OR_EXPIRED_ACCESS_TOKEN.model_dump(),
    headers={'WWW-Authenticate': 'Bearer'},
  )


async def _resolve_access_token_user(
  credentials: HTTPAuthorizationCredentials | None,
  session: AsyncSession,
  *,
  required: bool,
) -> User | None:
  if credentials is None:
    if required:
      raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=AuthMessages.BEARER_ACCESS_TOKEN_REQUIRED.model_dump(),
        headers={'WWW-Authenticate': 'Bearer'},
      )
    return None
  try:
    user_id = decode_access_token(credentials.credentials)
  except (jwt.InvalidTokenError, ValueError) as error:
    raise _invalid_access_token_error() from error

  user = await UserRepository(session).get_by_id(user_id)
  if user is None or not user.is_active or not user.is_email_verified:
    raise _invalid_access_token_error()
  return user


async def get_current_user(
  credentials: Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
  ],
  session: DatabaseSession,
) -> User:
  user = await _resolve_access_token_user(credentials, session, required=True)
  assert user is not None
  return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_current_user(
  credentials: Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
  ],
  session: DatabaseSession,
) -> User | None:
  return await _resolve_access_token_user(credentials, session, required=False)


OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]


def get_auth_service(session: DatabaseSession) -> AuthService:
  return AuthService(session)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
