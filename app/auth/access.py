from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repositories.users import UserRepository


@dataclass(frozen=True)
class AuthUserInfo:
  id: UUID
  email: str


async def find_verified_user_by_email(
  session: AsyncSession, email: str
) -> AuthUserInfo | None:
  user = await UserRepository(session).get_by_email(email.lower())
  if user is None or not user.is_active or not user.is_email_verified:
    return None
  return AuthUserInfo(id=user.id, email=user.email)


async def map_user_emails(
  session: AsyncSession, user_ids: Sequence[UUID]
) -> dict[UUID, str]:
  emails: dict[UUID, str] = {}
  for user_id in user_ids:
    user = await UserRepository(session).get_by_id(user_id)
    if user is not None:
      emails[user_id] = user.email
  return emails
