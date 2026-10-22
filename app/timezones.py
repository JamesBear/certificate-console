"""Timezone helpers.

Rule: a tenant stores an IANA zone name. Every local date is derived with zoneinfo at the
moment it is needed — never from a stored UTC offset, and never by slicing an ISO string.
Sydney is +11 in January and +10 in July; a fixed offset would be wrong for half the year.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def local(iso: str, tz: str) -> datetime:
    return parse_iso(iso).astimezone(ZoneInfo(tz))


def local_date(iso: str, tz: str) -> str:
    return local(iso, tz).strftime("%Y-%m-%d")


def local_year(iso: str, tz: str) -> int:
    return local(iso, tz).year


def _offset_label(value: datetime) -> str:
    raw = value.strftime("%z")  # +1100
    if not raw:
        return "UTC"
    sign = raw[0]
    hours, minutes = raw[1:3], raw[3:5]
    label = f"UTC{sign}{int(hours)}"
    if minutes != "00":
        label += f":{minutes}"
    return label


def zone_label(iso: str, tz: str) -> str:
    """e.g. "AEDT · UTC+11" — proves the rendering is zone-aware, not offset-aware."""
    at = local(iso, tz)
    abbr = at.tzname() or tz
    return f"{abbr} · {_offset_label(at)}"


def zone_abbr(tz: str, at: datetime | None = None) -> str:
    return (at or utc_now()).astimezone(ZoneInfo(tz)).tzname() or tz
