"""Resolves a date to a format key using content_calendar.yaml."""
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALENDAR_PATH = ROOT / "content_calendar.yaml"

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def load_calendar():
    with open(CALENDAR_PATH) as f:
        return yaml.safe_load(f)


def resolve_format(date):
    """Returns the format key for `date`, or None if nothing is scheduled."""
    cal = load_calendar()
    override_key = date.isoformat()
    if override_key in cal.get("overrides", {}):
        return cal["overrides"][override_key]
    weekday = WEEKDAYS[date.weekday()]
    return cal["weekday_defaults"].get(weekday)


def format_spec(format_key):
    cal = load_calendar()
    spec = cal["formats"].get(format_key)
    if spec is None:
        raise ValueError(f"Unknown format key: {format_key!r}")
    return spec
