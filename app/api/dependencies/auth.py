from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies.database import DatabaseSession
from app.core.security import decode_access_token
from app.messages.auth import AuthMessages
from app.models.auth import User
from app.repositories.users import UserRepository
from app.services.auth import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
  credentials: Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
  ],
  session: DatabaseSession,
) -> User:
  if credentials is None:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail=AuthMessages.BEARER_ACCESS_TOKEN_REQUIRED.model_dump(),
      headers={'WWW-Authenticate': 'Bearer'},
    )
  try:
    user_id = decode_access_token(credentials.credentials)
  except (jwt.InvalidTokenError, ValueError) as error:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail=AuthMessages.INVALID_OR_EXPIRED_ACCESS_TOKEN.model_dump(),
      headers={'WWW-Authenticate': 'Bearer'},
    ) from error

  user = await UserRepository(session).get_by_id(user_id)
  if user is None or not user.is_active or not user.is_email_verified:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail=AuthMessages.INVALID_OR_EXPIRED_ACCESS_TOKEN.model_dump(),
      headers={'WWW-Authenticate': 'Bearer'},
    )
  return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_auth_service(session: DatabaseSession) -> AuthService:
  return AuthService(session)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
