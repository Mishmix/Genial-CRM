"""Timezone utilities - Georgia (UTC+4)."""
from datetime import datetime, timezone, timedelta

# Georgia timezone (UTC+4)
GEORGIA_TZ = timezone(timedelta(hours=4))


def now_georgia() -> datetime:
    """Get current time in Georgia timezone (UTC+4)."""
    return datetime.now(GEORGIA_TZ).replace(tzinfo=None)


def utc_to_georgia(dt: datetime) -> datetime:
    """Convert UTC datetime to Georgia timezone."""
    if dt is None:
        return None
    # Assume naive datetime is UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(GEORGIA_TZ).replace(tzinfo=None)
