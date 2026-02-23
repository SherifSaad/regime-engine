# core/timeframes.py

TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]

# Launch defaults (what UI shows first)
DEFAULT_TIMEFRAMES = ["1h", "4h", "1day"]

# "Pro toggles" (supported by architecture, but off by default)
PRO_TIMEFRAMES = ["15min", "1week"]

# Display order for UI selector: 15min, 1h, 4h, 1d, 1w
TIMEFRAME_OPTIONS = ["15min", "1h", "4h", "1day", "1week"]

# Maps our UI timeframe keys to Twelve Data interval names later
INTERVAL_MAP = {
    "15min": "15min",
    "1h": "1h",
    "4h": "4h",
    "1day": "1day",
    "1week": "1week",
}
