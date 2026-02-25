# core/timeframes.py
"""
Canonical timeframes: 15min, 1h, 4h, 1day, 1week.
All bar folders and API calls use these names. Aliases are normalized on input.
"""

TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]

# Launch defaults (what UI shows first)
DEFAULT_TIMEFRAMES = ["1h", "4h", "1day"]

# "Pro toggles" (supported by architecture, but off by default)
PRO_TIMEFRAMES = ["15min", "1week"]

# Display order for UI selector
TIMEFRAME_OPTIONS = ["15min", "1h", "4h", "1day", "1week"]

# Maps our UI timeframe keys to Twelve Data interval names
INTERVAL_MAP = {
    "15min": "15min",
    "1h": "1h",
    "4h": "4h",
    "1day": "1day",
    "1week": "1week",
}

# Aliases → canonical. Use normalize_timeframe() at API/storage boundaries.
TIMEFRAME_ALIASES = {
    "1d": "1day",
    "1w": "1week",
    "1hour": "1h",
    "15mins": "15min",
    "4hour": "4h",
    "4hours": "4h",
}


def normalize_timeframe(tf: str) -> str:
    """Return canonical timeframe. Unknown values pass through."""
    if not tf:
        return tf
    key = tf.strip().lower()
    return TIMEFRAME_ALIASES.get(key, tf)
