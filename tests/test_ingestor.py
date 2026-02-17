from datetime import datetime, timezone

import pytest

from regime_engine.ingestor import (
    BarValidationError,
    normalize_bars,
    normalize_record,
)


def test_normalize_record_accepts_iso_z():
    rec = {
        "timestamp": "2026-02-12T00:00:00Z",
        "open": 100,
        "high": 105,
        "low": 99,
        "close": 102,
        "volume": 12345,
    }
    bar = normalize_record(rec)
    assert bar.timestamp.tzinfo is not None
    assert bar.timestamp.utcoffset() == timezone.utc.utcoffset(datetime.now(timezone.utc))
    assert bar.open == 100.0
    assert bar.volume == 12345.0


def test_normalize_record_accepts_alt_keys():
    rec = {"ts": "2026-02-12T00:00:00+00:00", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}
    bar = normalize_record(rec)
    assert bar.open == 1.0
    assert bar.high == 2.0
    assert bar.low == 0.5
    assert bar.close == 1.5
    assert bar.volume == 10.0


def test_missing_fields_raises():
    rec = {"timestamp": "2026-02-12T00:00:00Z", "open": 100, "high": 101, "close": 100}
    with pytest.raises(BarValidationError):
        normalize_record(rec)


def test_invalid_ohlc_raises():
    rec = {"timestamp": "2026-02-12T00:00:00Z", "open": 100, "high": 99, "low": 98, "close": 100}
    with pytest.raises(BarValidationError):
        normalize_record(rec)


def test_normalize_bars_sorts_and_enforces_increasing():
    records = [
        {"timestamp": "2026-02-12T00:00:02Z", "open": 1, "high": 2, "low": 0.5, "close": 1.2},
        {"timestamp": "2026-02-12T00:00:01Z", "open": 1, "high": 2, "low": 0.5, "close": 1.2},
    ]
    bars = normalize_bars(records)
    assert bars[0].timestamp < bars[1].timestamp

    # Duplicate timestamp should fail
    records_dup = [
        {"timestamp": "2026-02-12T00:00:01Z", "open": 1, "high": 2, "low": 0.5, "close": 1.2},
        {"timestamp": "2026-02-12T00:00:01Z", "open": 1, "high": 2, "low": 0.5, "close": 1.2},
    ]
    with pytest.raises(BarValidationError):
        normalize_bars(records_dup)
