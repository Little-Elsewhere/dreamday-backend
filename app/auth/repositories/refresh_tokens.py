from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken


class RefreshTokenRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_by_token_hash(
    self, token_hash: str, *, for_update: bool = False
  ) -> RefreshToken | None:
    statement = select(RefreshToken).where(
      RefreshToken.token_hash == token_hash
    )
    if for_update:
      statement = statement.with_for_update()
    return await self.session.scalar(statement)

  async def revoke_active_family(
    self, family_id: UUID, revoked_at: datetime
  ) -> None:
    await self.session.execute(
      update(RefreshToken)
      .where(
        RefreshToken.family_id == family_id,
        RefreshToken.revoked_at.is_(None),
      )
      .values(revoked_at=revoked_at)
    )

  def add(self, token: RefreshToken) -> None:
    self.session.add(token)

  def revoke(
    self,
    token: RefreshToken,
    revoked_at: datetime,
    *,
    replaced_by_id: UUID | None = None,
  ) -> None:
    token.revoked_at = revoked_at
    if replaced_by_id is not None:
      token.replaced_by_id = replaced_by_id
