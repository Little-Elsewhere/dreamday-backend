from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.core.datetime import UtcInstant

TripPace = Literal['relaxed', 'balanced', 'active']
TripLifecycle = Literal['draft', 'published']
TripVisibility = Literal['private', 'public']
TripMemberRole = Literal['owner', 'member']
ActivityType = Literal['explore', 'meal', 'travel', 'stay', 'free']
TripListStatus = Literal['all', 'upcoming', 'past']


class TripActivityCreate(BaseModel):
  title: str = Field(min_length=1, max_length=80)
  activity_date: date
  activity_type: ActivityType
  start_minute: int = Field(ge=0, le=1439)
  end_minute: int = Field(ge=1, le=1440)
  note: str = Field(default='', max_length=500)


class TripActivityUpdate(BaseModel):
  title: str | None = Field(default=None, min_length=1, max_length=80)
  activity_date: date | None = None
  activity_type: ActivityType | None = None
  start_minute: int | None = Field(default=None, ge=0, le=1439)
  end_minute: int | None = Field(default=None, ge=1, le=1440)
  note: str | None = Field(default=None, max_length=500)


class TripActivityResponse(BaseModel):
  id: UUID
  title: str
  activity_date: date
  activity_type: ActivityType
  start_minute: int
  end_minute: int
  note: str
  created_at: UtcInstant
  updated_at: UtcInstant


class TripCreateRequest(BaseModel):
  name: str = Field(default='', max_length=40)
  destination: str = Field(default='', max_length=40)
  description: str = Field(default='', max_length=100)
  start_date: date | None = None
  end_date: date | None = None
  pace: TripPace | None = None
  timezone: str = Field(default='Asia/Ho_Chi_Minh', min_length=1, max_length=64)
  visibility: TripVisibility = 'private'
  note: str = Field(default='', max_length=1000)


class TripUpdateRequest(BaseModel):
  name: str | None = Field(default=None, max_length=40)
  destination: str | None = Field(default=None, max_length=40)
  description: str | None = Field(default=None, max_length=100)
  start_date: date | None = None
  end_date: date | None = None
  pace: TripPace | None = None
  timezone: str | None = Field(default=None, min_length=1, max_length=64)
  visibility: TripVisibility | None = None
  note: str | None = Field(default=None, max_length=1000)


class TripCardResponse(BaseModel):
  id: UUID
  name: str
  destination: str
  description: str
  start_date: date | None
  end_date: date | None
  pace: TripPace | None
  timezone: str
  lifecycle: TripLifecycle
  visibility: TripVisibility
  cover_url: str | None
  status: Literal['upcoming', 'past'] | None
  duration_days: int | None
  created_at: UtcInstant
  updated_at: UtcInstant
  published_at: UtcInstant | None
  deleted_at: UtcInstant | None = None


class TripDetailResponse(TripCardResponse):
  note: str
  cover_path: str | None
  activities: list[TripActivityResponse]


class TripListResponse(BaseModel):
  items: list[TripCardResponse]
  total: int
  limit: int
  offset: int


class TripMemberCreateRequest(BaseModel):
  email: EmailStr


class TripMemberResponse(BaseModel):
  id: UUID
  user_id: UUID
  email: str
  role: TripMemberRole
  created_at: UtcInstant
  updated_at: UtcInstant


class TripMemberListResponse(BaseModel):
  items: list[TripMemberResponse]
