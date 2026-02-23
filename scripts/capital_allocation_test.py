#!/usr/bin/env python3
"""
Capital Allocation Test (B): Compare Buy & Hold vs Risk-Managed portfolios
using escalation_bucket as a hedge/cash trigger.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from regime_engine.escalation_buckets import compute_bucket_from_percentile
from regime_engine.escalation_v2 import rolling_percentile_transform
from regime_engine.features import realized_vol_annualized, rolling_percentile_rank
from regime_engine.hysteresis import hysteresis_high_state, bucket_from_high_state

from validate_regimes import load_csv, add_forward_returns, run_engine_over_history


# =========================
# Core performance metrics
# =========================

def equity_curve_from_exposure(
    close: pd.Series,
    exposure: pd.Series,
    transaction_cost_bps: float = 0.0
):
    """
    Returns (equity, turnover_series, cost_series)
    """
    close = close.astype(float)
    exposure = exposure.astype(float)

    daily_ret = close.pct_change().fillna(0.0)

    exp_shifted = exposure.shift(1).fillna(0.0)
    strat_ret = exp_shifted * daily_ret

    turnover = exposure.diff().abs().fillna(0.0)  # |Δ exposure|
    cost = turnover * transaction_cost_bps

    strat_ret_after_cost = strat_ret - cost
    equity = (1.0 + strat_ret_after_cost).cumprod()

    return equity, turnover, cost

def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())

def ulcer_index(equity: pd.Series) -> float:
    """
    Ulcer Index: sqrt(mean(drawdown%^2))
    Here drawdown is negative; convert to percent magnitude.
    """
    peak = equity.cummax()
    dd = equity / peak - 1.0
    dd_pct = 100.0 * dd
    ui = float(np.sqrt(np.mean(np.square(dd_pct))))
    return ui

def cagr(equity: pd.Series, periods_per_year: int = 252) -> float:
    n = len(equity)
    if n < 2:
        return np.nan
    years = (n - 1) / periods_per_year
    if years <= 0:
        return np.nan
    return float(equity.iloc[-1] ** (1.0 / years) - 1.0)

def calmar_ratio(cagr_val: float, max_dd_val: float) -> float:
    if max_dd_val >= 0:
        return np.nan
    return float(cagr_val / abs(max_dd_val))

def prob_tail_20d(close: pd.Series, threshold: float = -0.10, horizon: int = 20) -> float:
    """
    Probability that forward 20d return <= threshold, unconditional on strategy.
    """
    fwd = close.shift(-horizon) / close - 1.0
    fwd = fwd.dropna()
    if len(fwd) == 0:
        return np.nan
    return float(np.mean(fwd.values <= threshold))

def strategy_forward_return_20d(equity: pd.Series, horizon: int = 20) -> pd.Series:
    return equity.shift(-horizon) / equity - 1.0


# =========================
# Exposure policies
# =========================

STRATEGY_LABELS = {"REDUCE_ON_HIGH": "PANIC_RISK", "CASH_ON_HIGH": "CASH_ON_HIGH", "BH": "BH"}


def exposure_policy_from_bucket(
    bucket: pd.Series,
    mode: str,
    reduce_exposure: float = 0.7,
    vol_rank: pd.Series | None = None,
    vol_scalar: float = 1.0,
) -> pd.Series:
    """
    mode options:
      - "BH"             : always 1.0
      - "CASH_ON_HIGH"   : 0.0 when HIGH else 1.0
      - "REDUCE_ON_HIGH" : dynamic exposure when HIGH (from vol_rank + vol_scalar) else 1.0
    """
    bucket = bucket.astype(str)

    if mode == "BH":
        return pd.Series(1.0, index=bucket.index)

    if mode == "CASH_ON_HIGH":
        return bucket.map(lambda b: 0.0 if b == "HIGH" else 1.0).astype(float)

    if mode == "REDUCE_ON_HIGH":
        exp = []
        for i in bucket.index:
            b = bucket.loc[i]
            if b == "HIGH":
                vr = vol_rank.loc[i] if vol_rank is not None and i in vol_rank.index else np.nan
                if np.isfinite(vr):
                    base_expo = 0.4 + 0.6 * (1.0 - float(vr))
                    base_expo = float(np.clip(base_expo, 0.4, 1.0))
                    e = float(np.clip(base_expo * vol_scalar, 0.3, 1.0))
                else:
                    e = reduce_exposure
            else:
                e = 1.0
            exp.append(e)
        return pd.Series(exp, index=bucket.index).astype(float)

    raise ValueError(f"Unknown mode: {mode}")


# =========================
# Main runner
# =========================

def run_capital_allocation_test(
    base_hys: pd.DataFrame,
    periods_per_year: int = 252,
    trading_days: int = 252,
    ref_vol: float | None = None,
):
    needed = ["close", "bucket"]
    if "rv20" in base_hys.columns and "vol_rank" in base_hys.columns:
        needed = ["close", "bucket", "rv20", "vol_rank"]
    df = base_hys[needed].copy()
    if "rv20" not in df.columns:
        df["rv20"] = realized_vol_annualized(df["close"], window=20, trading_days=trading_days)
        df["vol_rank"] = rolling_percentile_rank(df["rv20"], lookback=756)
    df = df.dropna().sort_index()

    # Basic sanity
    if df["close"].isna().any():
        raise ValueError("close contains NaNs after dropna().")
    if df["bucket"].isna().any():
        raise ValueError("bucket contains NaNs after dropna().")

    # --- Baseline vol scaling (universal, deterministic) ---
    base_vol = base_hys.attrs.get("base_vol", None)

    if (
        (ref_vol is None)
        or (base_vol is None)
        or (not np.isfinite(ref_vol))
        or (not np.isfinite(base_vol))
        or (base_vol <= 0)
    ):
        vol_scalar = 1.0
    else:
        # More volatile assets than SPY -> smaller scalar -> more de-risking in HIGH
        vol_scalar = float(np.clip(ref_vol / base_vol, 0.6, 1.0))

    # Strategies
    modes = ["BH", "CASH_ON_HIGH", "REDUCE_ON_HIGH"]

    cost_scenarios = [0.0, 0.0005, 0.001, 0.002]  # 0, 5bps, 10bps, 20bps

    rows = []
    for mode in modes:
        exp = exposure_policy_from_bucket(
            df["bucket"],
            mode=mode,
            vol_rank=df["vol_rank"] if mode == "REDUCE_ON_HIGH" else None,
            vol_scalar=vol_scalar,
        )
        for cost in cost_scenarios:
            eq, turnover, cost_series = equity_curve_from_exposure(
                df["close"],
                exp,
                transaction_cost_bps=cost
            )
            avg_turnover = float(np.mean(turnover.values))

            c = cagr(eq, periods_per_year=periods_per_year)
            mdd = max_drawdown(eq)
            ui = ulcer_index(eq)
            cal = calmar_ratio(c, mdd)

            fwd20 = strategy_forward_return_20d(eq, horizon=20).dropna()
            p_tail_strat = float(np.mean(fwd20.values <= -0.10)) if len(fwd20) else np.nan
            p5_fwd20 = float(np.nanpercentile(fwd20.values, 5)) if len(fwd20) else np.nan

            rows.append({
                "strategy": STRATEGY_LABELS.get(mode, mode),
                "cost_bps": cost * 10000,
                "CAGR": c,
                "MaxDD": mdd,
                "UlcerIndex": ui,
                "Calmar": cal,
                "Strat_P(20d<=-10%)": p_tail_strat,
                "Strat_p5_20d": p5_fwd20,
                "AvgTurnover": avg_turnover,
            })

    out = pd.DataFrame(rows)

    # Tail context (market, not strategy)
    p_tail = prob_tail_20d(df["close"], threshold=-0.10, horizon=20)

    print("\n=== CAPITAL ALLOCATION TEST ===")
    print("Sample start:", df.index.min().date().isoformat(), "end:", df.index.max().date().isoformat())
    print("Unconditional market P(20d <= -10%):", round(p_tail, 6))
    print("\nResults (higher Calmar, lower MaxDD/Ulcer is better):")
    with pd.option_context("display.float_format", "{:,.6f}".format):
        print(out.sort_values("Calmar", ascending=False).to_string(index=False))

    print("\nBucket distribution:")
    print(df["bucket"].value_counts().to_string())

    # Diagnostics
    high_mask = (base_hys["bucket"] == "HIGH")
    mean_vr_high = float(np.nanmean(base_hys.loc[high_mask, "vol_rank"])) if high_mask.any() else np.nan
    exp_red = exposure_policy_from_bucket(
        df["bucket"], mode="REDUCE_ON_HIGH", vol_rank=df["vol_rank"], vol_scalar=vol_scalar
    )
    df_high = (df["bucket"] == "HIGH")
    mean_exp_high = float(exp_red.loc[df_high].mean()) if df_high.any() else np.nan

    print(f"base_vol: {base_vol:.6f}" if (base_vol is not None and np.isfinite(base_vol)) else f"base_vol: {base_vol}")
    print(f"ref_vol (SPY): {ref_vol:.6f}" if (ref_vol is not None and np.isfinite(ref_vol)) else f"ref_vol (SPY): {ref_vol}")
    print(f"vol_scalar: {vol_scalar:.6f}")
    print(f"mean vol_rank in HIGH: {mean_vr_high:.6f}" if np.isfinite(mean_vr_high) else f"mean vol_rank in HIGH: {mean_vr_high}")
    print(f"mean exposure in HIGH: {mean_exp_high:.6f}" if np.isfinite(mean_exp_high) else f"mean exposure in HIGH: {mean_exp_high}")

    return out


def run_filtered_test(base_hys: pd.DataFrame, name: str):
    """
    base_hys must have columns: close, bucket and a DatetimeIndex.
    If rv20/vol_rank missing, they will be computed (trading_days=252).
    """
    print("\n\n==============================")
    print("FILTER:", name)
    print("==============================")
    return run_capital_allocation_test(base_hys, periods_per_year=252)


# =========================
# Main: wire real series from regime engine
# =========================

ASSETS = {
    "SPY":  {"path": "data/spy_clean.csv",    "symbol": "SPY",    "trading_days": 252},
    "QQQ":  {"path": "data/qqq_clean.csv",    "symbol": "QQQ",    "trading_days": 252},
    "NVDA": {"path": "data/nvda_clean.csv",   "symbol": "NVDA",   "trading_days": 252},
    "BTC":  {"path": "data/btcusd_clean.csv", "symbol": "BTCUSD", "trading_days": 365},
    "XAU":  {"path": "data/xauusd_clean.csv", "symbol": "XAUUSD", "trading_days": 252},
}

# Run subset (SPY + BTC for baseline + extreme; add XAU for gold)
RUN_ASSETS = ["SPY", "BTC", "XAU"]


def _build_base_from_engine(engine_df: pd.DataFrame, trading_days: int = 252) -> pd.DataFrame:
    """Build base DataFrame with close, bucket (hysteresis), esc_pct from engine output."""
    valid = engine_df["escalation_v2"].notna()
    sub = engine_df.loc[valid].copy()

    esc_v2_pct = rolling_percentile_transform(
        pd.Series(sub["escalation_v2"].values, index=sub.index),
        window=504,
    )
    sub["escalation_v2_pct"] = esc_v2_pct

    valid_pct = sub["escalation_v2_pct"].notna()
    sub = sub.loc[valid_pct].copy()

    buckets = [compute_bucket_from_percentile(float(e))[0] for e in sub["escalation_v2_pct"].values]
    sub["bucket"] = buckets

    dates_series = sub.index
    if dates_series.tz is not None:
        dates_series = dates_series.tz_localize(None)
    base = pd.DataFrame({
        "date": pd.to_datetime(dates_series),
        "close": sub["adj_close"].astype(float).values,
        "bucket": sub["bucket"].astype(str).values,
        "esc_pct": sub["escalation_v2_pct"].astype(float).values,
    }).dropna().sort_values("date").set_index("date")

    is_high_hys = hysteresis_high_state(base["esc_pct"], enter=0.90, exit=0.75)
    bucket_hys = bucket_from_high_state(is_high_hys, default_bucket="LOW")

    base_hys = pd.DataFrame({"close": base["close"], "bucket": bucket_hys}, index=base.index)
    base_hys["rv20"] = realized_vol_annualized(base_hys["close"], window=20, trading_days=trading_days)
    base_hys["vol_rank"] = rolling_percentile_rank(base_hys["rv20"], lookback=756)

    rv = base_hys["rv20"].dropna()
    base_vol = float(rv.median()) if len(rv) else np.nan
    base_hys.attrs["base_vol"] = base_vol

    return base_hys


if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parents[1]
    ref_vol = None
    for label in RUN_ASSETS:
        asset = ASSETS[label]
        path = ROOT / asset["path"]
        symbol = asset["symbol"]
        trading_days = asset["trading_days"]
        if not path.exists():
            print(f"\n\n===== {label} ({symbol}): SKIP (file not found: {path}) =====")
            continue

        print("\n\n" + "=" * 60)
        print(f"ASSET: {label} ({symbol})")
        print("=" * 60)
        print("Loading data and running engine over history...")
        engine_df = load_csv(path)
        engine_df = add_forward_returns(engine_df)
        engine_df = run_engine_over_history(engine_df, symbol=symbol)

        base_hys = _build_base_from_engine(engine_df, trading_days=asset["trading_days"])
        if label == "SPY":
            ref_vol = base_hys.attrs.get("base_vol", None)

        run_capital_allocation_test(
            base_hys,
            periods_per_year=252,
            trading_days=trading_days,
            ref_vol=ref_vol,
        )
