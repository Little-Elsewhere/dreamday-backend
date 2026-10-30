from datetime import datetime

from sqlalchemy import DateTime, TypeDecorator

from app.core.datetime import as_utc


class UtcDateTime(TypeDecorator):
  impl = DateTime(timezone=True)
  cache_ok = True

  def process_bind_param(
    self, value: datetime | None, dialect
  ) -> datetime | None:
    if value is None:
      return None
    return as_utc(value)

  def process_result_value(
    self, value: datetime | None, dialect
  ) -> datetime | None:
    if value is None:
      return None
    return as_utc(value)
