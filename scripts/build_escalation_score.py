# scripts/build_escalation_score.py
# Creates a continuous "Early Escalation" composite score from your existing regime timeline metrics.
# Output: validation_outputs/escalation_score_daily.csv

from __future__ import annotations

import os
import sys
import numpy as np
import pandas as pd

from regime_engine.escalation_v2 import compute_escalation_v2


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMELINE_CSV = os.path.join(ROOT, "validation_outputs", "regime_timeline.csv")
OUT_CSV = os.path.join(ROOT, "validation_outputs", "escalation_score_daily.csv")


REQUIRED_COLS = {
    "date",
    # regime label column can be "regime" or "regime_label" depending on your file
    # metrics:
    "instability_index",
    "downside_shock_risk",
    "risk_level",
    "structural_score",
    "market_bias",
    "confidence",
}

# Weights: core = 1.0 (acceleration adds on top; final score clipped to [0,1])
W = {
    "instability": 0.30,
    "downside": 0.30,
    "risk": 0.20,
    "structural_inv": 0.20,
}
W_ACCEL = {
    "instability_accel": 0.15,
    "downside_accel": 0.15,
}

ROLL_WIN = 252  # ~1y trading days for rolling quantiles
ACCEL_LOOKBACK = 5  # 1 week acceleration


def rolling_minmax_01(s: pd.Series, win: int) -> pd.Series:
    rmin = s.rolling(win, min_periods=max(20, win // 5)).min()
    rmax = s.rolling(win, min_periods=max(20, win // 5)).max()
    out = (s - rmin) / (rmax - rmin)
    return out.clip(0, 1)


def safe_diff(s: pd.Series, n: int) -> pd.Series:
    return s.diff(n)


def main() -> int:
    if not os.path.exists(TIMELINE_CSV):
        print(f"ERROR: missing {TIMELINE_CSV}")
        return 2

    df = pd.read_csv(TIMELINE_CSV)
    df.columns = [c.strip() for c in df.columns]

    # Harmonize regime label column name if present
    if "regime" in df.columns and "regime_label" not in df.columns:
        df["regime_label"] = df["regime"]
    elif "regime_label" not in df.columns:
        df["regime_label"] = ""

    # Validate required columns (date + metrics)
    missing = sorted([c for c in REQUIRED_COLS if c not in df.columns])
    if missing:
        print("ERROR: timeline is missing required columns:", missing)
        print("Found columns:", list(df.columns))
        return 2

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    # Ensure numeric
    for c in ["instability_index", "downside_shock_risk", "risk_level", "structural_score", "market_bias", "confidence"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Core normalized components (0..1), rolling min-max to avoid peeking
    df["instability_n"] = rolling_minmax_01(df["instability_index"], ROLL_WIN)
    df["downside_n"] = rolling_minmax_01(df["downside_shock_risk"], ROLL_WIN)
    df["risk_n"] = rolling_minmax_01(df["risk_level"], ROLL_WIN)

    # Structural score: high structural_score is "healthy" → invert so higher = worse
    # If structural_score can be outside [0,1], normalize first then invert.
    df["structural_n"] = rolling_minmax_01(df["structural_score"], ROLL_WIN)
    df["structural_inv_n"] = (1.0 - df["structural_n"]).clip(0, 1)

    # Acceleration terms (worsening momentum)
    inst_acc = safe_diff(df["instability_n"], ACCEL_LOOKBACK)
    down_acc = safe_diff(df["downside_n"], ACCEL_LOOKBACK)

    # Convert accel to 0..1 via rolling min-max, then clip
    df["instability_accel_n"] = rolling_minmax_01(inst_acc, ROLL_WIN)
    df["downside_accel_n"] = rolling_minmax_01(down_acc, ROLL_WIN)

    # Composite (core + accel), then clip to [0,1]
    core = (
        W["instability"] * df["instability_n"]
        + W["downside"] * df["downside_n"]
        + W["risk"] * df["risk_n"]
        + W["structural_inv"] * df["structural_inv_n"]
    )

    accel = (
        W_ACCEL["instability_accel"] * df["instability_accel_n"]
        + W_ACCEL["downside_accel"] * df["downside_accel_n"]
    )

    raw_score = core + accel
    # Rescale to 0..1 with rolling min-max as final guardrail
    df["escalation_score"] = rolling_minmax_01(raw_score, ROLL_WIN)

    # Escalation v2: merge with price data for close/ema, then compute
    price_path = os.path.join(ROOT, "data", "spy_sample.csv")
    if os.path.exists(price_path):
        px = pd.read_csv(price_path)
        px_date = "Date" if "Date" in px.columns else [c for c in px.columns if "date" in c.lower()][0]
        close_col = next((c for c in ["Adj Close", "Adj_Close", "Close", "close"] if c in px.columns), None)
        if close_col:
            px[px_date] = pd.to_datetime(px[px_date], errors="coerce")
            df["_date"] = df["date"].dt.date
            px["_date"] = px[px_date].dt.date
            merged = df.merge(px[[px_date, "_date", close_col]], on="_date", how="inner")
            merged = merged.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
            close = merged[close_col].astype(float).values
            from regime_engine.features import compute_ema
            ema_series = compute_ema(merged[close_col].astype(float), 100)
            ema = ema_series.values
            dsr = merged["downside_shock_risk"].astype(float).values
            iix = merged["instability_index"].astype(float).values
            ss = merged["structural_score"].astype(float).values
            if len(dsr) >= 15:  # min history for escalation_v2
                escalation_v2, esc_parts = compute_escalation_v2(
                    dsr=dsr,
                    iix=iix,
                    ss=ss,
                    close=close,
                    ema=ema,
                )
                print("ESCALATION_V2:", round(escalation_v2, 4))
                print("ESC_PARTS:", {k: round(v, 4) for k, v in esc_parts.items() if k != "raw"})

    # Add handy thresholds (in-sample rolling percentiles, no peeking)
    df["thr_90"] = df["escalation_score"].rolling(ROLL_WIN, min_periods=max(60, ROLL_WIN // 4)).quantile(0.90)
    df["thr_95"] = df["escalation_score"].rolling(ROLL_WIN, min_periods=max(60, ROLL_WIN // 4)).quantile(0.95)
    df["thr_975"] = df["escalation_score"].rolling(ROLL_WIN, min_periods=max(60, ROLL_WIN // 4)).quantile(0.975)

    # Flags
    df["flag_90"] = (df["escalation_score"] >= df["thr_90"]).astype(int)
    df["flag_95"] = (df["escalation_score"] >= df["thr_95"]).astype(int)
    df["flag_975"] = (df["escalation_score"] >= df["thr_975"]).astype(int)

    out_cols = [
        "date",
        "regime_label",
        "confidence",
        "market_bias",
        "instability_index",
        "downside_shock_risk",
        "risk_level",
        "structural_score",
        "instability_n",
        "downside_n",
        "risk_n",
        "structural_inv_n",
        "instability_accel_n",
        "downside_accel_n",
        "escalation_score",
        "thr_90",
        "thr_95",
        "thr_975",
        "flag_90",
        "flag_95",
        "flag_975",
    ]
    out = df[out_cols].copy()
    out.to_csv(OUT_CSV, index=False)

    # Minimal console summary
    last = out.dropna(subset=["escalation_score"]).tail(1)
    if not last.empty:
        r = last.iloc[0]
        print("DONE")
        print(f"Output: {OUT_CSV}")
        print(
            f"Latest: {r['date'].date()} score={r['escalation_score']:.3f} "
            f"(flag95={int(r['flag_95'])}, flag975={int(r['flag_975'])}) "
            f"regime={r['regime_label']}"
        )
    else:
        print("DONE (but escalation_score is all NaN — likely too little history for rolling windows)")
        print(f"Output: {OUT_CSV}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
