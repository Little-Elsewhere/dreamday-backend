from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User


class UserRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_by_email(
    self, email: str, *, for_update: bool = False
  ) -> User | None:
    statement = select(User).where(User.email == email)
    if for_update:
      statement = statement.with_for_update()
    return await self.session.scalar(statement)

  async def get_by_id(self, user_id: UUID) -> User | None:
    return await self.session.get(User, user_id)

  def add(self, user: User) -> None:
    self.session.add(user)
