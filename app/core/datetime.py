from datetime import UTC, datetime
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer


def utc_now() -> datetime:
  return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
  if value.tzinfo is None:
    return value.replace(tzinfo=UTC)
  return value.astimezone(UTC)


def parse_utc_datetime(value: object) -> datetime:
  if isinstance(value, datetime):
    return as_utc(value)
  if isinstance(value, str):
    normalized = value.strip()
    if normalized.endswith('Z'):
      normalized = f'{normalized[:-1]}+00:00'
    return as_utc(datetime.fromisoformat(normalized))
  raise TypeError('Expected a datetime or ISO-8601 string')


def format_utc_datetime(value: datetime) -> str:
  return as_utc(value).isoformat().replace('+00:00', 'Z')


UtcInstant = Annotated[
  datetime,
  BeforeValidator(parse_utc_datetime),
  PlainSerializer(format_utc_datetime, return_type=str, when_used='json'),
]
