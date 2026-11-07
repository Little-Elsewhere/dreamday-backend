from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
  Boolean,
  Date,
  ForeignKey,
  Index,
  Integer,
  String,
  Text,
  Uuid,
  func,
  text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base
from app.core.types import UtcDateTime

TRIP_PACES = ('relaxed', 'balanced', 'active')
TRIP_LIFECYCLES = ('draft', 'published')
ACTIVITY_TYPES = ('explore', 'meal', 'travel', 'stay', 'free')
DEFAULT_TRIP_TIMEZONE = 'Asia/Ho_Chi_Minh'


class Trip(Base):
  __tablename__ = 'trips'
  __table_args__ = (
    Index(
      'uq_trips_one_active_draft_per_user',
      'user_id',
      unique=True,
      postgresql_where=text("lifecycle = 'draft' AND deleted_at IS NULL"),
      sqlite_where=text("lifecycle = 'draft' AND deleted_at IS NULL"),
    ),
    Index('ix_trips_user_id_deleted_at', 'user_id', 'deleted_at'),
  )

  id: Mapped[UUID] = mapped_column(
    Uuid(as_uuid=True), primary_key=True, default=uuid4
  )
  user_id: Mapped[UUID] = mapped_column(
    Uuid(as_uuid=True),
    ForeignKey('users.id', ondelete='CASCADE'),
    nullable=False,
  )
  name: Mapped[str] = mapped_column(
    String(40), nullable=False, default='', server_default=''
  )
  destination: Mapped[str] = mapped_column(
    String(40), nullable=False, default='', server_default=''
  )
  description: Mapped[str] = mapped_column(
    String(100), nullable=False, default='', server_default=''
  )
  start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
  end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
  pace: Mapped[str | None] = mapped_column(String(16), nullable=True)
  timezone: Mapped[str] = mapped_column(
    String(64),
    nullable=False,
    default=DEFAULT_TRIP_TIMEZONE,
    server_default=DEFAULT_TRIP_TIMEZONE,
  )
  lifecycle: Mapped[str] = mapped_column(
    String(16),
    nullable=False,
    default='draft',
    server_default='draft',
  )
  note: Mapped[str] = mapped_column(
    Text, nullable=False, default='', server_default=''
  )
  cover_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
  cover_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
  created_at: Mapped[datetime] = mapped_column(
    UtcDateTime, server_default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    UtcDateTime,
    server_default=func.now(),
    onupdate=func.now(),
    nullable=False,
  )
  published_at: Mapped[datetime | None] = mapped_column(
    UtcDateTime, nullable=True
  )
  deleted_at: Mapped[datetime | None] = mapped_column(
    UtcDateTime, nullable=True
  )

  activities: Mapped[list[TripActivity]] = relationship(
    back_populates='trip',
    cascade='all, delete-orphan',
  )


class TripActivity(Base):
  __tablename__ = 'trip_activities'
  __table_args__ = (
    Index('ix_trip_activities_trip_id_deleted_at', 'trip_id', 'deleted_at'),
  )

  id: Mapped[UUID] = mapped_column(
    Uuid(as_uuid=True), primary_key=True, default=uuid4
  )
  trip_id: Mapped[UUID] = mapped_column(
    Uuid(as_uuid=True),
    ForeignKey('trips.id', ondelete='CASCADE'),
    nullable=False,
  )
  title: Mapped[str] = mapped_column(String(80), nullable=False)
  activity_date: Mapped[date] = mapped_column(Date, nullable=False)
  activity_type: Mapped[str] = mapped_column(String(16), nullable=False)
  start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
  end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
  note: Mapped[str] = mapped_column(
    String(500), nullable=False, default='', server_default=''
  )
  deleted_with_trip: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=False, server_default='false'
  )
  created_at: Mapped[datetime] = mapped_column(
    UtcDateTime, server_default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    UtcDateTime,
    server_default=func.now(),
    onupdate=func.now(),
    nullable=False,
  )
  deleted_at: Mapped[datetime | None] = mapped_column(
    UtcDateTime, nullable=True
  )

  trip: Mapped[Trip] = relationship(back_populates='activities')
