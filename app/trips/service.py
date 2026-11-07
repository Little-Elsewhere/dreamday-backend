from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import find_verified_user_by_email, map_user_emails
from app.core.datetime import utc_now
from app.core.storage import (
  COVER_CONTENT_TYPES,
  MAX_COVER_BYTES,
  ObjectStorage,
  cover_object_key,
)
from app.trips.models import (
  DEFAULT_TRIP_TIMEZONE,
  Trip,
  TripActivity,
  TripMember,
)
from app.trips.repositories.trips import TripActivityRepository, TripRepository
from app.trips.schemas import (
  TripActivityCreate,
  TripActivityResponse,
  TripActivityUpdate,
  TripCardResponse,
  TripCreateRequest,
  TripDetailResponse,
  TripListResponse,
  TripMemberCreateRequest,
  TripMemberListResponse,
  TripMemberResponse,
  TripUpdateRequest,
)


class TripServiceErrorCode(StrEnum):
  TRIP_NOT_FOUND = 'trip_not_found'
  DRAFT_ALREADY_EXISTS = 'draft_already_exists'
  DRAFT_NOT_FOUND = 'draft_not_found'
  INVALID_TRIP_DATES = 'invalid_trip_dates'
  PUBLISH_VALIDATION_FAILED = 'publish_validation_failed'
  ACTIVITY_NOT_FOUND = 'activity_not_found'
  ACTIVITY_OUTSIDE_TRIP = 'activity_outside_trip'
  INVALID_ACTIVITY_TIME = 'invalid_activity_time'
  TRIP_DELETED = 'trip_deleted'
  TRIP_NOT_DELETED = 'trip_not_deleted'
  INVALID_COVER = 'invalid_cover'
  ACTIVITY_DELETED = 'activity_deleted'
  ACTIVITY_NOT_DELETED = 'activity_not_deleted'
  FORBIDDEN = 'forbidden'
  COVER_NOT_FOUND = 'cover_not_found'
  MEMBER_NOT_FOUND = 'member_not_found'
  USER_NOT_FOUND = 'user_not_found'
  ALREADY_A_MEMBER = 'already_a_member'
  CANNOT_REMOVE_OWNER = 'cannot_remove_owner'


@dataclass
class TripServiceError(Exception):
  code: TripServiceErrorCode


def _duration_days(start: date | None, end: date | None) -> int | None:
  if start is None or end is None:
    return None
  return (end - start).days + 1


def _today_in_timezone(timezone_name: str) -> date:
  try:
    zone = ZoneInfo(timezone_name)
  except ZoneInfoNotFoundError:
    zone = ZoneInfo(DEFAULT_TRIP_TIMEZONE)
  return datetime.now(zone).date()


def _trip_status(end: date | None, *, timezone_name: str) -> str | None:
  if end is None:
    return 'upcoming'
  today = _today_in_timezone(timezone_name)
  return 'upcoming' if end >= today else 'past'


def _cover_proxy_url(trip: Trip) -> str | None:
  if not trip.cover_path:
    return None
  return f'/api/v1/trips/{trip.id}/cover'


def _is_publicly_viewable(trip: Trip) -> bool:
  return (
    trip.deleted_at is None
    and trip.lifecycle == 'published'
    and trip.visibility == 'public'
  )


def _active_activities(trip: Trip) -> list[TripActivity]:
  return sorted(
    (a for a in trip.activities if a.deleted_at is None),
    key=lambda a: (a.activity_date, a.start_minute, a.title),
  )


def _activity_response(activity: TripActivity) -> TripActivityResponse:
  return TripActivityResponse(
    id=activity.id,
    title=activity.title,
    activity_date=activity.activity_date,
    activity_type=activity.activity_type,  # type: ignore[arg-type]
    start_minute=activity.start_minute,
    end_minute=activity.end_minute,
    note=activity.note,
    created_at=activity.created_at,
    updated_at=activity.updated_at,
  )


def _card_response(
  trip: Trip, *, include_deleted: bool = False
) -> TripCardResponse:
  return TripCardResponse(
    id=trip.id,
    name=trip.name,
    destination=trip.destination,
    description=trip.description,
    start_date=trip.start_date,
    end_date=trip.end_date,
    pace=trip.pace,  # type: ignore[arg-type]
    timezone=trip.timezone,
    lifecycle=trip.lifecycle,  # type: ignore[arg-type]
    visibility=trip.visibility,  # type: ignore[arg-type]
    cover_url=_cover_proxy_url(trip),
    status=_trip_status(trip.end_date, timezone_name=trip.timezone),
    duration_days=_duration_days(trip.start_date, trip.end_date),
    created_at=trip.created_at,
    updated_at=trip.updated_at,
    published_at=trip.published_at,
    deleted_at=trip.deleted_at if include_deleted else None,
  )


def _detail_response(trip: Trip) -> TripDetailResponse:
  card = _card_response(trip, include_deleted=trip.deleted_at is not None)
  return TripDetailResponse(
    **card.model_dump(),
    note=trip.note,
    cover_path=trip.cover_path,
    activities=[_activity_response(a) for a in _active_activities(trip)],
  )


def _validate_date_range(start: date | None, end: date | None) -> None:
  if start is not None and end is not None and end < start:
    raise TripServiceError(TripServiceErrorCode.INVALID_TRIP_DATES)


def _validate_activity_time(start_minute: int, end_minute: int) -> None:
  if end_minute <= start_minute:
    raise TripServiceError(TripServiceErrorCode.INVALID_ACTIVITY_TIME)


def _validate_activity_within_trip(trip: Trip, activity_date: date) -> None:
  if trip.start_date is not None and activity_date < trip.start_date:
    raise TripServiceError(TripServiceErrorCode.ACTIVITY_OUTSIDE_TRIP)
  if trip.end_date is not None and activity_date > trip.end_date:
    raise TripServiceError(TripServiceErrorCode.ACTIVITY_OUTSIDE_TRIP)


class TripService:
  def __init__(
    self,
    session: AsyncSession,
    storage: ObjectStorage,
  ) -> None:
    self.session = session
    self.storage = storage
    self.trips = TripRepository(session)
    self.activities = TripActivityRepository(session)

  def can_view_trip(self, user_id: UUID | None, trip: Trip) -> bool:
    if trip.deleted_at is not None:
      return False
    if _is_publicly_viewable(trip):
      return True
    if user_id is None:
      return False
    return any(member.user_id == user_id for member in trip.members)

  def can_edit_trip(self, user_id: UUID, trip: Trip) -> bool:
    if trip.deleted_at is not None:
      return False
    return any(
      member.user_id == user_id and member.role == 'owner'
      for member in trip.members
    )

  async def create_draft(
    self, user_id: UUID, payload: TripCreateRequest
  ) -> TripDetailResponse:
    existing = await self.trips.get_active_draft(user_id)
    if existing is not None:
      raise TripServiceError(TripServiceErrorCode.DRAFT_ALREADY_EXISTS)

    _validate_date_range(payload.start_date, payload.end_date)
    now = utc_now()
    trip = Trip(
      user_id=user_id,
      name=payload.name.strip(),
      destination=payload.destination.strip(),
      description=payload.description.strip(),
      start_date=payload.start_date,
      end_date=payload.end_date,
      pace=payload.pace,
      timezone=payload.timezone.strip() or DEFAULT_TRIP_TIMEZONE,
      visibility=payload.visibility,
      note=payload.note,
      lifecycle='draft',
      created_at=now,
      updated_at=now,
    )
    self.trips.add(trip)
    await self.session.flush()
    self.trips.add_member(
      TripMember(
        id=uuid4(),
        trip_id=trip.id,
        user_id=user_id,
        role='owner',
        created_at=now,
        updated_at=now,
      )
    )
    await self.session.commit()
    loaded = await self.trips.get_by_id(
      trip.id, with_activities=True, with_members=True
    )
    assert loaded is not None
    return _detail_response(loaded)

  async def get_draft(self, user_id: UUID) -> TripDetailResponse:
    trip = await self.trips.get_active_draft(user_id)
    if trip is None:
      raise TripServiceError(TripServiceErrorCode.DRAFT_NOT_FOUND)
    return _detail_response(trip)

  async def get_trip(
    self,
    user_id: UUID | None,
    trip_id: UUID,
    *,
    include_deleted: bool = False,
  ) -> TripDetailResponse:
    trip = await self._load_trip(
      trip_id,
      include_deleted=include_deleted,
      with_activities=True,
      with_members=True,
    )
    if include_deleted:
      if user_id is None or not self.can_edit_trip(user_id, trip):
        # Soft-deleted trips are owner-only.
        member = (
          await self.trips.get_member(trip.id, user_id) if user_id else None
        )
        if member is None or member.role != 'owner':
          raise TripServiceError(TripServiceErrorCode.TRIP_NOT_FOUND)
    elif not self.can_view_trip(user_id, trip):
      raise TripServiceError(TripServiceErrorCode.TRIP_NOT_FOUND)
    return _detail_response(trip)

  async def list_trips(
    self,
    user_id: UUID,
    *,
    deleted: bool = False,
    status: str = 'all',
    q: str | None = None,
    limit: int = 6,
    offset: int = 0,
  ) -> TripListResponse:
    today = _today_in_timezone(DEFAULT_TRIP_TIMEZONE)
    items, total = await self.trips.list_for_member(
      user_id,
      deleted=deleted,
      status=status,
      q=q,
      today=today,
      limit=limit,
      offset=offset,
    )
    return TripListResponse(
      items=[_card_response(trip, include_deleted=deleted) for trip in items],
      total=total,
      limit=limit,
      offset=offset,
    )

  async def update_trip(
    self, user_id: UUID, trip_id: UUID, payload: TripUpdateRequest
  ) -> TripDetailResponse:
    trip = await self._require_editable_trip(user_id, trip_id)
    data = payload.model_dump(exclude_unset=True)
    start = data.get('start_date', trip.start_date)
    end = data.get('end_date', trip.end_date)
    _validate_date_range(start, end)

    for field, value in data.items():
      if isinstance(value, str) and field in {
        'name',
        'destination',
        'description',
        'timezone',
      }:
        value = value.strip()
      setattr(trip, field, value)

    trip.updated_at = utc_now()
    await self.session.commit()
    loaded = await self.trips.get_by_id(
      trip_id, with_activities=True, with_members=True
    )
    assert loaded is not None
    return _detail_response(loaded)

  async def publish(self, user_id: UUID, trip_id: UUID) -> TripDetailResponse:
    trip = await self._require_editable_trip(
      user_id, trip_id, with_activities=True
    )
    if (
      not trip.name.strip()
      or trip.start_date is None
      or trip.end_date is None
      or trip.pace is None
      or not trip.timezone.strip()
    ):
      raise TripServiceError(TripServiceErrorCode.PUBLISH_VALIDATION_FAILED)
    _validate_date_range(trip.start_date, trip.end_date)

    for activity in _active_activities(trip):
      _validate_activity_within_trip(trip, activity.activity_date)

    now = utc_now()
    trip.lifecycle = 'published'
    if trip.published_at is None:
      trip.published_at = now
    trip.updated_at = now
    await self.session.commit()
    loaded = await self.trips.get_by_id(
      trip_id, with_activities=True, with_members=True
    )
    assert loaded is not None
    return _detail_response(loaded)

  async def soft_delete(self, user_id: UUID, trip_id: UUID) -> None:
    trip = await self._require_editable_trip(
      user_id, trip_id, with_activities=True
    )
    now = utc_now()
    trip.deleted_at = now
    trip.updated_at = now
    await self.trips.soft_delete_active_activities(trip, now)
    await self.session.commit()

  async def restore(self, user_id: UUID, trip_id: UUID) -> TripDetailResponse:
    trip = await self.trips.get_by_id(
      trip_id,
      include_deleted=True,
      with_activities=True,
      with_members=True,
    )
    if trip is None:
      raise TripServiceError(TripServiceErrorCode.TRIP_NOT_FOUND)
    member = await self.trips.get_member(trip.id, user_id)
    if member is None or member.role != 'owner':
      raise TripServiceError(TripServiceErrorCode.TRIP_NOT_FOUND)
    if trip.deleted_at is None:
      raise TripServiceError(TripServiceErrorCode.TRIP_NOT_DELETED)

    if trip.lifecycle == 'draft':
      existing = await self.trips.get_active_draft(user_id)
      if existing is not None and existing.id != trip.id:
        raise TripServiceError(TripServiceErrorCode.DRAFT_ALREADY_EXISTS)

    trip.deleted_at = None
    trip.updated_at = utc_now()
    await self.trips.restore_cascade_activities(trip)
    await self.session.commit()
    loaded = await self.trips.get_by_id(
      trip_id, with_activities=True, with_members=True
    )
    assert loaded is not None
    return _detail_response(loaded)

  async def upload_cover(
    self,
    user_id: UUID,
    trip_id: UUID,
    *,
    body: bytes,
    content_type: str,
  ) -> TripDetailResponse:
    trip = await self._require_editable_trip(user_id, trip_id)
    if (
      content_type not in COVER_CONTENT_TYPES
      or len(body) == 0
      or len(body) > MAX_COVER_BYTES
    ):
      raise TripServiceError(TripServiceErrorCode.INVALID_COVER)

    key = cover_object_key(
      user_id=user_id, trip_id=trip_id, content_type=content_type
    )
    previous_key = trip.cover_path
    await self.storage.put_bytes(key=key, body=body, content_type=content_type)
    trip.cover_path = key
    trip.cover_url = None
    trip.updated_at = utc_now()
    await self.session.commit()

    if previous_key and previous_key != key:
      await self.storage.delete_object(previous_key)

    loaded = await self.trips.get_by_id(
      trip_id, with_activities=True, with_members=True
    )
    assert loaded is not None
    return _detail_response(loaded)

  async def remove_cover(
    self, user_id: UUID, trip_id: UUID
  ) -> TripDetailResponse:
    trip = await self._require_editable_trip(user_id, trip_id)
    previous_key = trip.cover_path
    trip.cover_path = None
    trip.cover_url = None
    trip.updated_at = utc_now()
    await self.session.commit()
    if previous_key:
      await self.storage.delete_object(previous_key)
    loaded = await self.trips.get_by_id(
      trip_id, with_activities=True, with_members=True
    )
    assert loaded is not None
    return _detail_response(loaded)

  async def get_cover_bytes(
    self, user_id: UUID | None, trip_id: UUID
  ) -> tuple[bytes, str]:
    trip = await self._load_trip(trip_id, with_members=True)
    if not self.can_view_trip(user_id, trip):
      raise TripServiceError(TripServiceErrorCode.TRIP_NOT_FOUND)
    if not trip.cover_path:
      raise TripServiceError(TripServiceErrorCode.COVER_NOT_FOUND)
    try:
      return await self.storage.get_bytes(trip.cover_path)
    except (ClientError, FileNotFoundError) as error:
      raise TripServiceError(TripServiceErrorCode.COVER_NOT_FOUND) from error

  async def list_members(
    self, user_id: UUID, trip_id: UUID
  ) -> TripMemberListResponse:
    trip = await self._load_trip(trip_id, with_members=True)
    if not self.can_view_trip(user_id, trip):
      raise TripServiceError(TripServiceErrorCode.TRIP_NOT_FOUND)
    members = await self.trips.list_members(trip_id)
    emails = await map_user_emails(
      self.session, [member.user_id for member in members]
    )
    items: list[TripMemberResponse] = []
    for member in members:
      email = emails.get(member.user_id)
      if email is None:
        continue
      items.append(
        TripMemberResponse(
          id=member.id,
          user_id=member.user_id,
          email=email,
          role=member.role,  # type: ignore[arg-type]
          created_at=member.created_at,
          updated_at=member.updated_at,
        )
      )
    return TripMemberListResponse(items=items)

  async def add_member(
    self,
    user_id: UUID,
    trip_id: UUID,
    payload: TripMemberCreateRequest,
  ) -> TripMemberResponse:
    trip = await self._require_editable_trip(
      user_id, trip_id, with_members=True
    )
    invitee = await find_verified_user_by_email(
      self.session, str(payload.email)
    )
    if invitee is None:
      raise TripServiceError(TripServiceErrorCode.USER_NOT_FOUND)
    existing = await self.trips.get_member(trip.id, invitee.id)
    if existing is not None:
      raise TripServiceError(TripServiceErrorCode.ALREADY_A_MEMBER)

    now = utc_now()
    member = TripMember(
      id=uuid4(),
      trip_id=trip.id,
      user_id=invitee.id,
      role='member',
      created_at=now,
      updated_at=now,
    )
    self.trips.add_member(member)
    trip.updated_at = now
    await self.session.commit()
    await self.session.refresh(member)
    return TripMemberResponse(
      id=member.id,
      user_id=member.user_id,
      email=invitee.email,
      role='member',
      created_at=member.created_at,
      updated_at=member.updated_at,
    )

  async def remove_member(
    self, user_id: UUID, trip_id: UUID, member_user_id: UUID
  ) -> None:
    trip = await self._require_editable_trip(
      user_id, trip_id, with_members=True
    )
    member = await self.trips.get_member(trip.id, member_user_id)
    if member is None:
      raise TripServiceError(TripServiceErrorCode.MEMBER_NOT_FOUND)
    if member.role == 'owner':
      raise TripServiceError(TripServiceErrorCode.CANNOT_REMOVE_OWNER)
    await self.session.delete(member)
    trip.updated_at = utc_now()
    await self.session.commit()

  async def create_activity(
    self,
    user_id: UUID,
    trip_id: UUID,
    payload: TripActivityCreate,
  ) -> TripActivityResponse:
    trip = await self._require_editable_trip(user_id, trip_id)
    _validate_activity_time(payload.start_minute, payload.end_minute)
    _validate_activity_within_trip(trip, payload.activity_date)
    now = utc_now()
    activity = TripActivity(
      trip_id=trip.id,
      title=payload.title.strip(),
      activity_date=payload.activity_date,
      activity_type=payload.activity_type,
      start_minute=payload.start_minute,
      end_minute=payload.end_minute,
      note=payload.note,
      created_at=now,
      updated_at=now,
    )
    self.activities.add(activity)
    trip.updated_at = now
    await self.session.commit()
    await self.session.refresh(activity)
    return _activity_response(activity)

  async def update_activity(
    self,
    user_id: UUID,
    trip_id: UUID,
    activity_id: UUID,
    payload: TripActivityUpdate,
  ) -> TripActivityResponse:
    trip = await self._require_editable_trip(user_id, trip_id)
    activity = await self.activities.get_by_id(activity_id, trip_id=trip_id)
    if activity is None:
      raise TripServiceError(TripServiceErrorCode.ACTIVITY_NOT_FOUND)

    data = payload.model_dump(exclude_unset=True)
    start_minute = data.get('start_minute', activity.start_minute)
    end_minute = data.get('end_minute', activity.end_minute)
    activity_date = data.get('activity_date', activity.activity_date)
    _validate_activity_time(start_minute, end_minute)
    _validate_activity_within_trip(trip, activity_date)

    for field, value in data.items():
      if field == 'title' and isinstance(value, str):
        value = value.strip()
      setattr(activity, field, value)

    now = utc_now()
    activity.updated_at = now
    trip.updated_at = now
    await self.session.commit()
    await self.session.refresh(activity)
    return _activity_response(activity)

  async def soft_delete_activity(
    self, user_id: UUID, trip_id: UUID, activity_id: UUID
  ) -> None:
    trip = await self._require_editable_trip(user_id, trip_id)
    activity = await self.activities.get_by_id(activity_id, trip_id=trip_id)
    if activity is None:
      raise TripServiceError(TripServiceErrorCode.ACTIVITY_NOT_FOUND)
    now = utc_now()
    activity.deleted_at = now
    activity.deleted_with_trip = False
    activity.updated_at = now
    trip.updated_at = now
    await self.session.commit()

  async def restore_activity(
    self, user_id: UUID, trip_id: UUID, activity_id: UUID
  ) -> TripActivityResponse:
    trip = await self._require_editable_trip(user_id, trip_id)
    activity = await self.activities.get_by_id(
      activity_id, trip_id=trip_id, include_deleted=True
    )
    if activity is None:
      raise TripServiceError(TripServiceErrorCode.ACTIVITY_NOT_FOUND)
    if activity.deleted_at is None:
      raise TripServiceError(TripServiceErrorCode.ACTIVITY_NOT_DELETED)

    _validate_activity_within_trip(trip, activity.activity_date)
    now = utc_now()
    activity.deleted_at = None
    activity.deleted_with_trip = False
    activity.updated_at = now
    trip.updated_at = now
    await self.session.commit()
    await self.session.refresh(activity)
    return _activity_response(activity)

  async def _load_trip(
    self,
    trip_id: UUID,
    *,
    include_deleted: bool = False,
    with_activities: bool = False,
    with_members: bool = False,
  ) -> Trip:
    trip = await self.trips.get_by_id(
      trip_id,
      include_deleted=include_deleted,
      with_activities=with_activities,
      with_members=with_members,
    )
    if trip is None:
      raise TripServiceError(TripServiceErrorCode.TRIP_NOT_FOUND)
    return trip

  async def _require_editable_trip(
    self,
    user_id: UUID,
    trip_id: UUID,
    *,
    with_activities: bool = False,
    with_members: bool = True,
  ) -> Trip:
    trip = await self._load_trip(
      trip_id,
      include_deleted=True,
      with_activities=with_activities,
      with_members=with_members,
    )
    if trip.deleted_at is not None:
      raise TripServiceError(TripServiceErrorCode.TRIP_DELETED)
    if not self.can_edit_trip(user_id, trip):
      raise TripServiceError(TripServiceErrorCode.FORBIDDEN)
    return trip
