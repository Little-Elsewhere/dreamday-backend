from datetime import datetime
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import EmailVerificationToken, PasswordResetToken

PurposeTokenT = TypeVar(
  'PurposeTokenT', EmailVerificationToken, PasswordResetToken
)


class PurposeTokenRepository[PurposeTokenT]:
  def __init__(self, session: AsyncSession, model: type[PurposeTokenT]) -> None:
    self.session = session
    self.model = model

  async def get_by_token_hash(
    self, token_hash: str, *, for_update: bool = False
  ) -> PurposeTokenT | None:
    statement = select(self.model).where(self.model.token_hash == token_hash)
    if for_update:
      statement = statement.with_for_update()
    return await self.session.scalar(statement)

  async def get_latest_active(
    self, user_id: UUID, now: datetime, *, for_update: bool = False
  ) -> PurposeTokenT | None:
    statement = (
      select(self.model)
      .where(
        self.model.user_id == user_id,
        self.model.consumed_at.is_(None),
        self.model.expires_at > now,
      )
      .order_by(self.model.created_at.desc())
      .limit(1)
    )
    if for_update:
      statement = statement.with_for_update()
    return await self.session.scalar(statement)

  async def replace_pending_for_user(
    self,
    user_id: UUID,
    token: PurposeTokenT,
    now: datetime,
  ) -> None:
    await self.session.execute(
      update(self.model)
      .where(
        self.model.user_id == user_id,
        self.model.consumed_at.is_(None),
      )
      .values(consumed_at=now)
    )
    self.session.add(token)
    await self.session.flush()

  def consume(self, token: PurposeTokenT, at: datetime) -> None:
    token.consumed_at = at

  async def consume_by_token_hash(self, token_hash: str, at: datetime) -> None:
    await self.session.execute(
      update(self.model)
      .where(self.model.token_hash == token_hash)
      .values(consumed_at=at)
    )
