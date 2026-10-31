"""
paging.py — Common pagination, range, duration, and script-variable parsing utilities.

Shared across interactive CLI commands (/batch, /batchlist, /session, /tools, /replay)
to prevent range/limit parser drift and duplicated duration parsing.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def clean_var_name(raw: str | None, default: str = "") -> str:
    """Normalize a script variable name by stripping whitespace and leading '$'."""
    val = raw if raw is not None else default
    return val.strip().lstrip("$")


def parse_paging(opts: dict[str, str], default_limit: int | None = 10) -> tuple[int, int | None]:
    """Parse limit= and range= options into (offset, limit).

    Supports:
      - limit=N
      - range=start:end
      - range=:end (open start)
      - range=start: (open end)
      - range=N (offset N, default limit)
    """
    offset = 0
    limit = default_limit
    if "limit" in opts:
        try:
            limit = int(opts["limit"])
        except ValueError:
            print(f"Invalid limit value. Using default limit of {default_limit or 10}.")
    if "range" in opts:
        try:
            r = opts["range"]
            if ":" in r:
                s, e = r.split(":", 1)
                offset = int(s) if s else 0
                limit = (int(e) - offset) if e else None
            else:
                offset = int(r)
        except ValueError:
            print("Invalid range format. Use range=start:end, range=:end, or range=start:. "
                  f"Using default limit of {default_limit or 10}.")
    return offset, limit


def parse_since(raw: str) -> datetime | None:
    """Parse a relative duration string like '7d', '24h', '30m' into a datetime threshold."""
    try:
        if raw.endswith("d"):
            delta = timedelta(days=float(raw[:-1]))
        elif raw.endswith("h"):
            delta = timedelta(hours=float(raw[:-1]))
        elif raw.endswith("m"):
            delta = timedelta(minutes=float(raw[:-1]))
        else:
            print(f"Invalid since= unit '{raw}'. Use d (days), h (hours), or m (minutes). "
                  "E.g. since=7d")
            return None
        return datetime.now() - delta
    except ValueError:
        print(f"Invalid since= value '{raw}'. Use numeric values like since=7d, "
              "since=24h, since=30m")
        return None
