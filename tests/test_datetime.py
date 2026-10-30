from datetime import UTC, datetime, timedelta, timezone

from app.core.datetime import (
  as_utc,
  format_utc_datetime,
  parse_utc_datetime,
  utc_now,
)
from app.core.types import UtcDateTime


def test_utc_now_is_timezone_aware_utc() -> None:
  now = utc_now()
  assert now.tzinfo is not None
  assert now.utcoffset() == timedelta(0)


def test_as_utc_treats_naive_as_utc() -> None:
  naive = datetime(2026, 10, 30, 12, 0, 0)
  assert as_utc(naive) == datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)


def test_as_utc_converts_other_offsets() -> None:
  plus_seven = timezone(timedelta(hours=7))
  local = datetime(2026, 10, 30, 19, 0, 0, tzinfo=plus_seven)
  assert as_utc(local) == datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)


def test_parse_and_format_utc_wire_strings() -> None:
  parsed = parse_utc_datetime('2026-10-30T19:00:00+07:00')
  assert parsed == datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)
  assert format_utc_datetime(parsed) == '2026-10-30T12:00:00Z'
  assert (
    format_utc_datetime(parse_utc_datetime('2026-10-30T12:00:00Z'))
    == '2026-10-30T12:00:00Z'
  )


def test_utc_datetime_bind_and_result_normalize_to_utc() -> None:
  column_type = UtcDateTime()
  plus_seven = timezone(timedelta(hours=7))
  local = datetime(2026, 10, 30, 19, 0, 0, tzinfo=plus_seven)

  bound = column_type.process_bind_param(local, dialect=None)
  assert bound == datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)

  result = column_type.process_result_value(
    datetime(2026, 10, 30, 12, 0, 0), dialect=None
  )
  assert result == datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)
