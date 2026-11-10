---
paths:
  - app/**/*.py
  - migrations/**/*.py
---

# UTC datetime contract

The API exchanges **instants in UTC** only, as ISO-8601 with a `Z` suffix (e.g. `2026-10-30T12:00:00Z`).

- **Now:** use `utc_now()` from `app.core.datetime`. Never call `datetime.now()` without a zone or `datetime.utcnow()`.
- **Storage:** map instant columns with `UtcDateTime` from `app.core.types` (`timestamptz`). Do not use naive `DateTime`.
- **Schemas:** type instant fields in Pydantic schemas as `UtcInstant`, which parses any offset to UTC and serializes with `Z`.
- **Local time:** convert to a zone only for business logic that needs a local calendar date (e.g. "today" for a trip's timezone). Never store or return local-offset datetimes.

```python
# ❌ BAD — naive / local datetimes leak into storage and JSON
created_at: datetime
expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
issued = datetime.utcnow()

# ✅ GOOD
from app.core.datetime import UtcInstant, utc_now
from app.core.types import UtcDateTime

created_at: UtcInstant
expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
issued = utc_now()
```
