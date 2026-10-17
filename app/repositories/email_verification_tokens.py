from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import EmailVerificationToken


class EmailVerificationTokenRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_by_token_hash(
    self, token_hash: str, *, for_update: bool = False
  ) -> EmailVerificationToken | None:
    statement = select(EmailVerificationToken).where(
      EmailVerificationToken.token_hash == token_hash
    )
    if for_update:
      statement = statement.with_for_update()
    return await self.session.scalar(statement)

  async def latest_active_created_at(
    self, user_id: UUID, now: datetime
  ) -> datetime | None:
    statement = (
      select(EmailVerificationToken.created_at)
      .where(
        EmailVerificationToken.user_id == user_id,
        EmailVerificationToken.consumed_at.is_(None),
        EmailVerificationToken.expires_at > now,
      )
      .order_by(EmailVerificationToken.created_at.desc())
      .limit(1)
    )
    return await self.session.scalar(statement)

  async def replace_pending_for_user(
    self,
    user_id: UUID,
    token: EmailVerificationToken,
    now: datetime,
  ) -> None:
    await self.session.execute(
      update(EmailVerificationToken)
      .where(
        EmailVerificationToken.user_id == user_id,
        EmailVerificationToken.consumed_at.is_(None),
      )
      .values(consumed_at=now)
    )
    self.session.add(token)
    await self.session.flush()

  def consume(self, token: EmailVerificationToken, at: datetime) -> None:
    token.consumed_at = at

  async def consume_by_token_hash(self, token_hash: str, at: datetime) -> None:
    await self.session.execute(
      update(EmailVerificationToken)
      .where(EmailVerificationToken.token_hash == token_hash)
      .values(consumed_at=at)
    )
