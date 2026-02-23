# core/asset_class_rules.py
"""
Asset class rules + symbol→class mapping.
Asset classes: Index, Stocks, FX, Crypto, Commodities, Futures, Fixed Income.
"""

from core.assets_registry import default_assets, get_asset

# Symbol → asset_class (derived from registry; used by scheduler/session logic)
def _build_symbol_to_class() -> dict:
    out = {}
    for a in default_assets():
        out[a.symbol.upper()] = a.asset_class
    return out

SYMBOL_TO_ASSET_CLASS = _build_symbol_to_class()

ASSET_CLASS_RULES = {
    "Index": {
        "history": {"15min_days": 30, "1h_days": 180, "4h_days": 730, "1day_days": 3650, "1week_days": 7300},
        "expects_weekends": False,
    },
    "Stocks": {
        "history": {"15min_days": 30, "1h_days": 180, "4h_days": 730, "1day_days": 3650, "1week_days": 7300},
        "expects_weekends": False,
    },
    "FX": {
        "history": {"15min_days": 45, "1h_days": 365, "4h_days": 1460, "1day_days": 3650, "1week_days": 7300},
        "expects_weekends": False,  # generally no trading on weekends
    },
    "Crypto": {
        "history": {"15min_days": 60, "1h_days": 365, "4h_days": 1460, "1day_days": 3650, "1week_days": 7300},
        "expects_weekends": True,
    },
    "Commodities": {
        "history": {"15min_days": 30, "1h_days": 365, "4h_days": 1460, "1day_days": 3650, "1week_days": 7300},
        "expects_weekends": False,
    },
    "Futures": {
        "history": {"15min_days": 30, "1h_days": 365, "4h_days": 1460, "1day_days": 3650, "1week_days": 7300},
        "expects_weekends": False,
    },
    "Fixed Income": {
        "history": {"15min_days": 30, "1h_days": 365, "4h_days": 1460, "1day_days": 7300, "1week_days": 9000},
        "expects_weekends": False,
    },
}

# ============================
# Session Profiles (Polling)
# ============================

from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

class SessionProfile:
    """
    Defines when polling is allowed for a given asset class.
    Times are in America/New_York by default (can be extended later).
    """
    def __init__(self, name: str, tz=NY_TZ, expects_weekends: bool = False,
                 windows=None):
        self.name = name
        self.tz = tz
        self.expects_weekends = expects_weekends
        # windows: list of (start_time, end_time) tuples in local tz
        # None means 24h
        self.windows = windows  # e.g., [(09:30, 16:00)]

    def is_open_now(self, now: datetime) -> bool:
        local = now.astimezone(self.tz)

        # Weekend gating
        if not self.expects_weekends and local.weekday() >= 5:
            return False

        # 24h session
        if not self.windows:
            return True

        t = local.time()
        for start, end in self.windows:
            if start <= t <= end:
                return True
        return False


# Session profiles by asset class
# NOTE: This is polling logic only (not backtesting calendar logic).
SESSION_PROFILES = {
    # US equities / ETFs: regular trading hours
    "Index": SessionProfile(
        name="US_EQUITY_RTH",
        tz=NY_TZ,
        expects_weekends=False,
        windows=[(dtime(9, 30), dtime(16, 0))]
    ),
    "Stocks": SessionProfile(
        name="US_EQUITY_RTH",
        tz=NY_TZ,
        expects_weekends=False,
        windows=[(dtime(9, 30), dtime(16, 0))]
    ),

    # Crypto: 24/7
    "Crypto": SessionProfile(
        name="CRYPTO_24x7",
        tz=NY_TZ,
        expects_weekends=True,
        windows=None
    ),

    # FX: 24/5 (we approximate as always open Mon–Fri)
    "FX": SessionProfile(
        name="FX_24x5",
        tz=NY_TZ,
        expects_weekends=False,
        windows=None
    ),

    # Commodities spot (like XAUUSD): often 24/5 depending on feed; treat as 24/5 for polling
    "Commodities": SessionProfile(
        name="COMMODITIES_24x5",
        tz=NY_TZ,
        expects_weekends=False,
        windows=None
    ),

    # Futures (ES/GC etc.): often near-24/5 with brief daily breaks.
    # We'll refine later; for now treat as 24/5 to avoid missing.
    "Futures": SessionProfile(
        name="FUTURES_24x5",
        tz=NY_TZ,
        expects_weekends=False,
        windows=None
    ),

    "Fixed Income": SessionProfile(
        name="RATES_24x5",
        tz=NY_TZ,
        expects_weekends=False,
        windows=None
    ),
}


def get_session_profile(symbol: str) -> SessionProfile:
    """
    Resolve session profile by symbol using SYMBOL_TO_ASSET_CLASS mapping.
    Falls back to 24/5 if unknown.
    """
    asset_class = SYMBOL_TO_ASSET_CLASS.get(symbol.upper())
    prof = SESSION_PROFILES.get(asset_class)
    if prof:
        return prof

    # Sensible default: 24/5 (no weekends)
    return SessionProfile(name="DEFAULT_24x5", tz=NY_TZ, expects_weekends=False, windows=None)


def should_poll(symbol: str, timeframe: str, now: datetime | None = None) -> bool:
    """
    Generic polling gate:
    1) Must be inside the session profile's open window
    2) Must be at a timeframe boundary (so new bar is plausible)

    This is designed to reduce vendor API usage while staying correct across asset classes.
    """
    if now is None:
        now = datetime.now(tz=NY_TZ)

    prof = get_session_profile(symbol)
    if not prof.is_open_now(now):
        return False

    local = now.astimezone(prof.tz)
    minute = local.minute
    hour = local.hour
    weekday = local.weekday()  # Mon=0

    # Boundary rules (simple + robust):
    def near_boundary(minute_value: int, period: int, grace: int = 1) -> bool:
        # True if we are within [0..grace] minutes after a boundary
        return (minute_value % period) in range(0, grace + 1)

    if timeframe == "15min":
        return near_boundary(minute, 15, grace=1)

    if timeframe == "1h":
        return minute in (0, 1)

    if timeframe == "4h":
        return (minute in (0, 1)) and (hour % 4 == 0)

    if timeframe == "1day":
        # For RTH assets, this will only be true inside their session window (e.g. at 16:00).
        # For 24/5, this fires at top of hour==0; acceptable for polling once/day.
        return (hour == 16 and minute == 0) if prof.name == "US_EQUITY_RTH" else (hour == 0 and minute == 0)

    if timeframe == "1week":
        # Friday close for RTH assets; otherwise Friday 00:00 for 24/5-ish assets
        if prof.name == "US_EQUITY_RTH":
            return (weekday == 4 and hour == 16 and minute == 0)
        return (weekday == 4 and hour == 0 and minute == 0)

    # Unknown timeframe: allow polling (safe)
    return True
