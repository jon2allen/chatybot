"""
Flexible date parser supporting relative offsets, human relative words, standard dates, and ranges.
"""

from datetime import datetime, timedelta
import calendar
import re
from typing import Optional, Tuple


def parse_datetime_expr(val: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Parse a single date or relative time string into a naive datetime.
    
    Supports:
      - 'now'
      - 'today', 'yesterday'
      - 'thisweek', 'lastweek'
      - 'thismonth', 'lastmonth'
      - 'thisyear', 'lastyear'
      - Relative offsets: '7d', '24h', '30m', '2w' (or with minus: '-7d')
      - ISO-like & standard formats:
        - 'YYYY-MM-DD'
        - 'YYYY-MM-DD HH:MM:SS'
        - 'YYYY-MM-DDTHH:MM:SS'
        - 'YYYY-MM-DDTHH:MM:SS.ffffff'
        - 'MM/DD/YYYY'
        - 'MM/DD/YYYY HH:MM:SS'
    """
    if not val or not isinstance(val, str):
        return None

    raw = val.strip().lower()
    now_dt = now or datetime.now()

    if raw == "now":
        return now_dt

    if raw == "today":
        return datetime(now_dt.year, now_dt.month, now_dt.day, 0, 0, 0)

    if raw == "yesterday":
        yest = now_dt - timedelta(days=1)
        return datetime(yest.year, yest.month, yest.day, 0, 0, 0)

    if raw in ("thisweek", "this_week"):
        start_week = now_dt - timedelta(days=now_dt.weekday())
        return datetime(start_week.year, start_week.month, start_week.day, 0, 0, 0)

    if raw in ("lastweek", "last_week"):
        start_last_week = (now_dt - timedelta(days=now_dt.weekday())) - timedelta(days=7)
        return datetime(start_last_week.year, start_last_week.month, start_last_week.day, 0, 0, 0)

    if raw in ("thismonth", "this_month"):
        return datetime(now_dt.year, now_dt.month, 1, 0, 0, 0)

    if raw in ("lastmonth", "last_month"):
        year = now_dt.year
        month = now_dt.month - 1
        if month == 0:
            month = 12
            year -= 1
        return datetime(year, month, 1, 0, 0, 0)

    if raw in ("thisyear", "this_year"):
        return datetime(now_dt.year, 1, 1, 0, 0, 0)

    if raw in ("lastyear", "last_year"):
        return datetime(now_dt.year - 1, 1, 1, 0, 0, 0)

    # Relative unit offset: e.g. '7d', '24h', '30m', '2w', '+7d', '-1d'
    offset_match = re.match(r"^([+-]?)(\d+)([dhmsw])$", raw)
    if offset_match:
        sign = offset_match.group(1)
        num = int(offset_match.group(2))
        unit = offset_match.group(3)
        delta = None
        if unit == "d":
            delta = timedelta(days=num)
        elif unit == "h":
            delta = timedelta(hours=num)
        elif unit == "m":
            delta = timedelta(minutes=num)
        elif unit == "s":
            delta = timedelta(seconds=num)
        elif unit == "w":
            delta = timedelta(weeks=num)

        if delta is not None:
            return now_dt + delta if sign == "+" else now_dt - delta

    # Date string matching
    original_val = val.strip()
    # Try ISO formats - strip trailing 'Z' if present
    iso_clean = original_val[:-1] if original_val.endswith("Z") else original_val
    iso_clean = iso_clean.rstrip()
    if "T" in iso_clean:
        try:
            return datetime.fromisoformat(iso_clean)
        except ValueError:
            pass

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(original_val, fmt)
        except ValueError:
            continue

    return None


def parse_date_range(range_expr: str, now: Optional[datetime] = None) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse a range expression into (start_dt, end_dt).
    Supports:
      - '03/01/2026 to 05/01/2026'
      - '2026-03-01..2026-05-01'
      - '2026-03-01:2026-05-01'
      - 'lastmonth to today'
    """
    if not range_expr or not isinstance(range_expr, str):
        return None, None

    clean = range_expr.strip()
    parts = []

    if " to " in clean.lower():
        parts = re.split(r"\s+to\s+", clean, flags=re.IGNORECASE, maxsplit=1)
    elif ".." in clean:
        parts = clean.split("..", 1)
    elif ":" in clean:
        # Avoid splitting timestamps like 14:30:00.
        # A range separator colon separates two dates (e.g. 2026-03-01:2026-05-01 or with spaces)
        if " : " in clean:
            parts = clean.split(" : ", 1)
        else:
            date_colon = re.search(r"(\d{1,4}[-/]\d{1,2}[-/]\d{1,4}):(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})", clean)
            if date_colon:
                idx = date_colon.start(1) + len(date_colon.group(1))
                parts = [clean[:idx], clean[idx+1:]]
            elif not re.search(r"\b\d{1,2}:\d{2}\b", clean):
                parts = clean.split(":", 1)

    if len(parts) == 2:
        start_dt = parse_datetime_expr(parts[0], now=now)
        end_dt = parse_datetime_expr(parts[1], now=now)
        # If end_dt is purely date (00:00:00), expand to end of that day
        if end_dt and end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        return start_dt, end_dt

    return None, None
