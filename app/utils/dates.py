from datetime import date, datetime, timedelta

from flask import current_app
from zoneinfo import ZoneInfo


def local_today():
    return datetime.now(ZoneInfo(current_app.config["APP_TIMEZONE"])).date()


def parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def month_bounds(year, month):
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    return start, end
