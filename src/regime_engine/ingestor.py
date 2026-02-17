# src/regime_engine/ingestor.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class BarValidationError(ValueError):
    pass


def _parse_ts(ts: Any) -> datetime:
    """
    Accepts:
      - datetime
      - ISO8601 string (with or without 'Z')
    Returns timezone-aware datetime in UTC.
    """
    if isinstance(ts, datetime):
        dt = ts
    else:
        s = str(ts).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)

    if dt.tzinfo is None:
        # assume UTC if naive
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def validate_bar(bar: Bar) -> None:
    if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0:
        raise BarValidationError("Prices must be > 0")

    if bar.high < max(bar.open, bar.close):
        raise BarValidationError("high must be >= max(open, close)")

    if bar.low > min(bar.open, bar.close):
        raise BarValidationError("low must be <= min(open, close)")

    if bar.low > bar.high:
        raise BarValidationError("low must be <= high")


def normalize_record(rec: Dict[str, Any]) -> Bar:
    """
    Normalizes various input schemas into the canonical Bar schema.
    Expected canonical keys (case-insensitive):
      timestamp, open, high, low, close, volume(optional)

    Also accepts:
      - time, date, datetime, ts (as timestamp)
      - o/h/l/c/v (as price keys)
    """
    keys = {str(k).lower(): k for k in rec.keys()}

    def get(*names: str, default=None):
        for n in names:
            if n in keys:
                return rec[keys[n]]
        return default

    ts = get("timestamp", "time", "date", "datetime", "ts")
    if ts is None:
        raise BarValidationError("Missing timestamp")

    o = get("open", "o")
    h = get("high", "h")
    l = get("low", "l")
    c = get("close", "c")

    if o is None or h is None or l is None or c is None:
        raise BarValidationError("Missing one of open/high/low/close")

    v = get("volume", "vol", "v", default=None)

    bar = Bar(
        timestamp=_parse_ts(ts),
        open=float(o),
        high=float(h),
        low=float(l),
        close=float(c),
        volume=None if v is None else float(v),
    )
    validate_bar(bar)
    return bar


def normalize_bars(records: Iterable[Dict[str, Any]]) -> List[Bar]:
    bars: List[Bar] = [normalize_record(r) for r in records]
    bars.sort(key=lambda b: b.timestamp)

    # ensure strictly increasing timestamps
    for i in range(1, len(bars)):
        if bars[i].timestamp <= bars[i - 1].timestamp:
            raise BarValidationError("Timestamps must be strictly increasing")

    return bars
