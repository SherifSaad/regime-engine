#!/usr/bin/env python3
"""
Crash Warning Precision/Recall (Event-based) for SPY regime engine.

Goal:
- For each drawdown event (peak->trough), measure whether the system warned BEFORE:
  - reaching -10% from peak
  - reaching -20% from peak
- Produce:
  - per-event table (with dates + lead times)
  - summary precision/recall-style metrics:
      * Recall: % of events where warning happened before threshold
      * Lead-time stats: median/mean days early (only when warned in time)
      * False positives: warnings that were NOT followed by a -10% event within N days

Inputs (default paths match your repo outputs):
- validation_outputs/regime_timeline.csv
- data/spy_sample.csv

Outputs:
- validation_outputs/warning_event_precision.csv
- validation_outputs/warning_event_summary.csv
- validation_outputs/warning_false_positives.csv
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

import numpy as np
import pandas as pd


DEFAULT_PRICE_CSV = "data/spy_sample.csv"
DEFAULT_TIMELINE_CSV = "validation_outputs/regime_timeline.csv"
OUT_EVENTS = "validation_outputs/warning_event_precision.csv"
OUT_SUMMARY = "validation_outputs/warning_event_summary.csv"
OUT_FP = "validation_outputs/warning_false_positives.csv"

# Event detection
MIN_EVENT_DD = 0.15  # 15% peak->trough drawdown to qualify as "event"
MIN_GAP_BETWEEN_PEAKS_DAYS = 60  # avoid tiny overlapping events

# Warning definition (keep this aligned with your current engine meaning)
WARNING_REGIMES = {"PANIC_RISK", "SHOCK"}

# False positive window
FP_LOOKAHEAD_DAYS = 60  # if a warning happens but no -10% occurs within this many trading days -> FP


def _require_file(path: str) -> None:
    if not os.path.exists(path):
        print(f"ERROR: missing file: {path}", file=sys.stderr)
        sys.exit(1)


def _load_prices(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Date" not in df.columns:
        raise ValueError("price csv must contain 'Date' column")
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    # Prefer Adj Close if present; else Close
    if "Adj Close" in df.columns:
        px = "Adj Close"
    elif "Close" in df.columns:
        px = "Close"
    else:
        raise ValueError("price csv must contain 'Adj Close' or 'Close'")
    df = df[["Date", px]].rename(columns={px: "close"})
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def _load_timeline(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Your file uses date like "2015-08-24 00:00:00+00:00" sometimes
    if "date" not in df.columns:
        raise ValueError("timeline csv must contain 'date' column")
    if "regime_label" in df.columns:
        regime_col = "regime_label"
    elif "regime" in df.columns:
        regime_col = "regime"
    else:
        raise ValueError("timeline csv must contain 'regime_label' or 'regime' column")

    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.tz_convert(None)
    df = df.dropna(subset=["date"]).copy()
    df = df.sort_values("date").reset_index(drop=True)
    df = df.rename(columns={regime_col: "regime_label"})
    df["regime_label"] = df["regime_label"].astype(str)
    return df[["date", "regime_label"]]


@dataclass
class DD_Event:
    peak_date: pd.Timestamp
    trough_date: pd.Timestamp
    max_dd: float  # negative number
    date_hit_10: Optional[pd.Timestamp]
    date_hit_20: Optional[pd.Timestamp]


def _compute_drawdown_events(prices: pd.DataFrame) -> List[DD_Event]:
    """
    Detect drawdown events using a simple peak-to-trough approach:
    - Walk forward tracking running peak.
    - Track trough after peak until a new peak breaks above prior peak.
    - Record event if max drawdown <= -MIN_EVENT_DD.
    """
    dates = prices["Date"].to_numpy()
    close = prices["close"].to_numpy(dtype=float)

    events: List[DD_Event] = []

    peak_idx = 0
    peak_px = close[0]
    trough_idx = 0
    trough_px = close[0]
    max_dd = 0.0

    # helper to finalize event
    def finalize_event(p_i: int, t_i: int, dd: float) -> None:
        if dd > -MIN_EVENT_DD:
            return
        peak_date = pd.Timestamp(dates[p_i])
        trough_date = pd.Timestamp(dates[t_i])

        # enforce separation between events (avoid tiny back-to-back)
        if events:
            last_peak = events[-1].peak_date
            if (peak_date - last_peak).days < MIN_GAP_BETWEEN_PEAKS_DAYS:
                return

        # Find date reaching -10% and -20% from peak within [peak..trough]
        peak_price = close[p_i]
        seg_dates = dates[p_i : t_i + 1]
        seg_close = close[p_i : t_i + 1]
        rel = (seg_close / peak_price) - 1.0

        date_10 = None
        date_20 = None
        hit10 = np.where(rel <= -0.10)[0]
        hit20 = np.where(rel <= -0.20)[0]
        if hit10.size > 0:
            date_10 = pd.Timestamp(seg_dates[int(hit10[0])])
        if hit20.size > 0:
            date_20 = pd.Timestamp(seg_dates[int(hit20[0])])

        events.append(
            DD_Event(
                peak_date=peak_date,
                trough_date=trough_date,
                max_dd=float(dd),
                date_hit_10=date_10,
                date_hit_20=date_20,
            )
        )

    for i in range(1, len(close)):
        px = close[i]

        # Update drawdown from current peak
        dd_i = (px / peak_px) - 1.0
        if dd_i < max_dd:
            max_dd = dd_i
            trough_idx = i
            trough_px = px

        # New peak resets the state; finalize previous event
        if px > peak_px:
            finalize_event(peak_idx, trough_idx, max_dd)
            peak_idx = i
            peak_px = px
            trough_idx = i
            trough_px = px
            max_dd = 0.0

    # finalize last segment
    finalize_event(peak_idx, trough_idx, max_dd)
    return events


def _first_warning_date_between(
    timeline: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> Optional[pd.Timestamp]:
    mask = (timeline["date"] >= start) & (timeline["date"] <= end) & (
        timeline["regime_label"].isin(WARNING_REGIMES)
    )
    sub = timeline.loc[mask]
    if sub.empty:
        return None
    return pd.Timestamp(sub.iloc[0]["date"])


def _trading_day_index(prices: pd.DataFrame) -> Dict[pd.Timestamp, int]:
    # map date->row index for trading-day distance
    return {pd.Timestamp(d): int(i) for i, d in enumerate(prices["Date"].tolist())}


def _tdiff_days(date_to_idx: Dict[pd.Timestamp, int], a: Optional[pd.Timestamp], b: Optional[pd.Timestamp]) -> Optional[int]:
    if a is None or b is None:
        return None
    if a not in date_to_idx or b not in date_to_idx:
        return None
    return int(date_to_idx[b] - date_to_idx[a])


def _false_positive_scan(
    prices: pd.DataFrame, timeline: pd.DataFrame
) -> pd.DataFrame:
    """
    Define a "warning day" as any day regime_label in WARNING_REGIMES.
    A warning is a false positive if, within the next FP_LOOKAHEAD_DAYS trading days,
    the price does NOT reach -10% from that warning day's close (peak-to-next window).
    """
    date_to_idx = _trading_day_index(prices)
    close_map = dict(zip(prices["Date"], prices["close"]))

    warn_days = timeline[timeline["regime_label"].isin(WARNING_REGIMES)][["date", "regime_label"]].copy()
    warn_days = warn_days[warn_days["date"].isin(prices["Date"])].copy()
    warn_days = warn_days.sort_values("date").reset_index(drop=True)

    rows = []
    dates = prices["Date"].tolist()
    close = prices["close"].to_numpy(float)

    for _, r in warn_days.iterrows():
        d = pd.Timestamp(r["date"])
        idx = date_to_idx.get(d, None)
        if idx is None:
            continue
        start_px = close[idx]
        end_idx = min(idx + FP_LOOKAHEAD_DAYS, len(close) - 1)
        window = close[idx : end_idx + 1]
        rel = (window / start_px) - 1.0
        hits = np.where(rel <= -0.10)[0]
        if hits.size == 0:
            # no -10% within lookahead -> false positive
            rows.append(
                {
                    "warning_date": d.date().isoformat(),
                    "warning_regime": r["regime_label"],
                    "lookahead_trading_days": end_idx - idx,
                    "min_return_in_window": float(rel.min()),
                }
            )

    return pd.DataFrame(rows)


def main() -> None:
    price_csv = DEFAULT_PRICE_CSV
    timeline_csv = DEFAULT_TIMELINE_CSV

    _require_file(price_csv)
    _require_file(timeline_csv)

    prices = _load_prices(price_csv)
    timeline = _load_timeline(timeline_csv)

    # Align timeline to price trading dates (drop non-trading dates)
    trading_dates = set(prices["Date"].tolist())
    timeline = timeline[timeline["date"].isin(trading_dates)].copy()
    timeline = timeline.sort_values("date").reset_index(drop=True)

    events = _compute_drawdown_events(prices)
    date_to_idx = _trading_day_index(prices)

    out_rows = []
    for e in events:
        # warning can happen from peak_date to trough_date (or earlier if you want pre-peak, but we keep it strict)
        warning_date = _first_warning_date_between(timeline, e.peak_date, e.trough_date)

        # lead time vs thresholds (in trading days)
        lead_to_10 = None
        lead_to_20 = None
        if e.date_hit_10 is not None and warning_date is not None:
            lead_to_10 = _tdiff_days(date_to_idx, warning_date, e.date_hit_10)
        if e.date_hit_20 is not None and warning_date is not None:
            lead_to_20 = _tdiff_days(date_to_idx, warning_date, e.date_hit_20)

        out_rows.append(
            {
                "event_peak_date": e.peak_date.date().isoformat(),
                "event_trough_date": e.trough_date.date().isoformat(),
                "event_max_drawdown": e.max_dd,
                "date_reaches_-10%": "" if e.date_hit_10 is None else e.date_hit_10.date().isoformat(),
                "date_reaches_-20%": "" if e.date_hit_20 is None else e.date_hit_20.date().isoformat(),
                "first_warning_date": "" if warning_date is None else warning_date.date().isoformat(),
                "lead_td_warning_to_-10%": "" if lead_to_10 is None else int(lead_to_10),
                "lead_td_warning_to_-20%": "" if lead_to_20 is None else int(lead_to_20),
                "warned_before_-10%": (warning_date is not None and e.date_hit_10 is not None and warning_date <= e.date_hit_10),
                "warned_before_-20%": (warning_date is not None and e.date_hit_20 is not None and warning_date <= e.date_hit_20),
            }
        )

    events_df = pd.DataFrame(out_rows)
    os.makedirs(os.path.dirname(OUT_EVENTS), exist_ok=True)
    events_df.to_csv(OUT_EVENTS, index=False)

    # Summary metrics (recall-like)
    # Only events that actually reached the threshold are eligible
    def summarize(th_col: str, lead_col: str, warn_col: str) -> Dict[str, object]:
        eligible = events_df[events_df[th_col].astype(str).str.len() > 0].copy()
        n_events = len(eligible)
        if n_events == 0:
            return {"n_events": 0}

        warned = eligible[eligible[warn_col] == True].copy()
        recall = len(warned) / n_events

        leads = pd.to_numeric(warned[lead_col], errors="coerce").dropna()
        return {
            "n_events": int(n_events),
            "n_warned_in_time": int(len(warned)),
            "recall": float(recall),
            "lead_td_median": float(leads.median()) if len(leads) else np.nan,
            "lead_td_mean": float(leads.mean()) if len(leads) else np.nan,
            "lead_td_p25": float(leads.quantile(0.25)) if len(leads) else np.nan,
            "lead_td_p75": float(leads.quantile(0.75)) if len(leads) else np.nan,
        }

    sum_10 = summarize("date_reaches_-10%", "lead_td_warning_to_-10%", "warned_before_-10%")
    sum_20 = summarize("date_reaches_-20%", "lead_td_warning_to_-20%", "warned_before_-20%")

    summary_df = pd.DataFrame(
        [
            {"threshold": "-10%", **sum_10},
            {"threshold": "-20%", **sum_20},
        ]
    )
    summary_df.to_csv(OUT_SUMMARY, index=False)

    # False positives scan
    fp_df = _false_positive_scan(prices, timeline)
    fp_df.to_csv(OUT_FP, index=False)

    print("DONE")
    print(f"Events:   {OUT_EVENTS}")
    print(f"Summary:  {OUT_SUMMARY}")
    print(f"FPos:     {OUT_FP}")
    if not summary_df.empty:
        print("\nSummary preview:")
        print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
