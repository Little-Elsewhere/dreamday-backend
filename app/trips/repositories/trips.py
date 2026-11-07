from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.trips.models import Trip, TripActivity, TripMember


class TripRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  def add(self, trip: Trip) -> None:
    self.session.add(trip)

  def add_member(self, member: TripMember) -> None:
    self.session.add(member)

  async def get_by_id(
    self,
    trip_id: UUID,
    *,
    include_deleted: bool = False,
    with_activities: bool = False,
    with_members: bool = False,
  ) -> Trip | None:
    statement: Select[tuple[Trip]] = select(Trip).where(Trip.id == trip_id)
    if not include_deleted:
      statement = statement.where(Trip.deleted_at.is_(None))
    options = []
    if with_activities:
      options.append(selectinload(Trip.activities))
    if with_members:
      options.append(selectinload(Trip.members))
    if options:
      statement = statement.options(*options)
    return await self.session.scalar(statement)

  async def get_active_draft(self, user_id: UUID) -> Trip | None:
    statement = (
      select(Trip)
      .where(
        Trip.user_id == user_id,
        Trip.lifecycle == 'draft',
        Trip.deleted_at.is_(None),
      )
      .options(selectinload(Trip.activities), selectinload(Trip.members))
    )
    return await self.session.scalar(statement)

  async def get_member(self, trip_id: UUID, user_id: UUID) -> TripMember | None:
    statement = select(TripMember).where(
      TripMember.trip_id == trip_id,
      TripMember.user_id == user_id,
    )
    return await self.session.scalar(statement)

  async def list_members(self, trip_id: UUID) -> list[TripMember]:
    statement = (
      select(TripMember)
      .where(TripMember.trip_id == trip_id)
      .order_by(TripMember.created_at.asc())
    )
    rows = await self.session.scalars(statement)
    return list(rows.all())

  async def list_for_member(
    self,
    user_id: UUID,
    *,
    deleted: bool = False,
    status: str = 'all',
    q: str | None = None,
    today: date | None = None,
    limit: int = 6,
    offset: int = 0,
  ) -> tuple[list[Trip], int]:
    filters = [TripMember.user_id == user_id]
    if deleted:
      filters.append(Trip.deleted_at.is_not(None))
    else:
      filters.append(Trip.deleted_at.is_(None))

    if q:
      pattern = f'%{q.strip()}%'
      filters.append(
        or_(Trip.name.ilike(pattern), Trip.destination.ilike(pattern))
      )

    if status in {'upcoming', 'past'} and today is not None:
      if status == 'upcoming':
        filters.append(or_(Trip.end_date.is_(None), Trip.end_date >= today))
      else:
        filters.append(Trip.end_date.is_not(None))
        filters.append(Trip.end_date < today)

    count_statement = (
      select(func.count())
      .select_from(Trip)
      .join(TripMember, TripMember.trip_id == Trip.id)
      .where(*filters)
    )
    total = int(await self.session.scalar(count_statement) or 0)

    statement = (
      select(Trip)
      .join(TripMember, TripMember.trip_id == Trip.id)
      .where(*filters)
      .order_by(Trip.updated_at.desc())
      .limit(limit)
      .offset(offset)
    )
    rows = await self.session.scalars(statement)
    return list(rows.all()), total

  async def soft_delete_active_activities(self, trip: Trip, deleted_at) -> None:
    for activity in trip.activities:
      if activity.deleted_at is None:
        activity.deleted_at = deleted_at
        activity.deleted_with_trip = True

  async def restore_cascade_activities(self, trip: Trip) -> None:
    for activity in trip.activities:
      if activity.deleted_with_trip and activity.deleted_at is not None:
        activity.deleted_at = None
        activity.deleted_with_trip = False


class TripActivityRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  def add(self, activity: TripActivity) -> None:
    self.session.add(activity)

  async def get_by_id(
    self,
    activity_id: UUID,
    *,
    trip_id: UUID,
    include_deleted: bool = False,
  ) -> TripActivity | None:
    statement = select(TripActivity).where(
      TripActivity.id == activity_id,
      TripActivity.trip_id == trip_id,
    )
    if not include_deleted:
      statement = statement.where(TripActivity.deleted_at.is_(None))
    return await self.session.scalar(statement)
