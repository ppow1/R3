"""Human-facing timezone presentation for canonical UTC operational timestamps.

Storage and API contracts keep their original UTC values. Presentation adds a
local rendering and an explicit normalized UTC correlation value.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_PRESENTATION_TIMEZONE = "America/New_York"


class TimestampPresentationError(ValueError):
    """Invalid timezone configuration or timestamp presentation request."""


@lru_cache(maxsize=64)
def resolve_timezone(name: str) -> ZoneInfo:
    if not isinstance(name, str) or not name.strip():
        raise TimestampPresentationError("presentation timezone must be a nonempty IANA timezone name")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise TimestampPresentationError(f"unknown IANA presentation timezone: {name!r}") from exc


def _parse_aware(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise TimestampPresentationError("timestamp is not valid ISO-8601") from exc
    else:
        raise TimestampPresentationError("timestamp must be an ISO-8601 string or datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TimestampPresentationError("timestamp has no timezone offset")
    return parsed


def format_timestamp(value: Any, timezone_name: str = DEFAULT_PRESENTATION_TIMEZONE) -> str:
    """Format one timestamp for people, retaining local zone and UTC correlation.

    Missing, malformed, and timezone-naive values are returned as explicit
    states; naive timestamps are never silently interpreted as UTC or local.
    Invalid configured zones raise so configuration activation can fail safely.
    """
    zone = resolve_timezone(timezone_name)
    if value is None or (isinstance(value, str) and not value.strip()):
        return "Unavailable (timestamp missing)"
    try:
        parsed = _parse_aware(value)
    except TimestampPresentationError as exc:
        detail = str(exc)
        if detail == "timestamp has no timezone offset":
            return f"Unconverted (timezone missing in source timestamp): {value}"
        if detail == "timestamp is not valid ISO-8601":
            return f"Unconverted (invalid timestamp): {value}"
        return f"Unconverted ({detail}): {value}"
    local = parsed.astimezone(zone)
    utc = parsed.astimezone(timezone.utc)
    timespec = "microseconds" if utc.microsecond else "seconds"
    local_value = local.isoformat(timespec=timespec)
    utc_value = utc.isoformat(timespec=timespec).replace("+00:00", "Z")
    abbreviation = local.tzname() or timezone_name
    return f"{local_value} {abbreviation} [{timezone_name}] | UTC {utc_value}"


def _is_timestamp_field(name: str) -> bool:
    lowered = name.casefold()
    return (lowered == "at" or lowered == "timestamp"
            or lowered.endswith(("_at", "_until", "_timestamp", "_expires")))


def add_human_timestamps(value: Any, timezone_name: str = DEFAULT_PRESENTATION_TIMEZONE) -> Any:
    """Copy a CLI/report payload, adding `*_local` fields while preserving raw values."""
    resolve_timezone(timezone_name)
    if isinstance(value, dict):
        projected = {key: add_human_timestamps(item, timezone_name)
                     for key, item in value.items()}
        for key, original in value.items():
            if isinstance(key, str) and _is_timestamp_field(key):
                projected[f"{key}_local"] = format_timestamp(original, timezone_name)
        return projected
    if isinstance(value, list):
        return [add_human_timestamps(item, timezone_name) for item in value]
    if isinstance(value, tuple):
        return [add_human_timestamps(item, timezone_name) for item in value]
    return value


def human_report(value: Any, timezone_name: str = DEFAULT_PRESENTATION_TIMEZONE) -> Any:
    """Add a clear timezone declaration and local timestamp companions to a report."""
    projected = add_human_timestamps(value, timezone_name)
    metadata = {"timezone": timezone_name,
                "timestamp_fields": "*_local fields are presentation; original fields remain canonical"}
    if isinstance(projected, dict):
        projected["_presentation"] = metadata
    else:
        projected = {"_presentation": metadata, "items": projected}
    return projected
