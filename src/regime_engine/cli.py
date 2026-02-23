from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from regime_engine.classifier import classify_to_dict
from regime_engine.loader import load_sample_data


def _trend_to_float(trend: str | float, rising: str, falling: str) -> float:
    """Convert string trend to numeric [-1, 1]. rising=+0.5, falling=-0.5, else 0."""
    if isinstance(trend, (int, float)):
        return float(trend)
    s = (trend or "").upper()
    if rising.upper() in s:
        return 0.5
    if falling.upper() in s:
        return -0.5
    return 0.0
from regime_engine.escalation_buckets import compute_bucket_from_percentile
from regime_engine.escalation_v2 import rolling_percentile_transform
from regime_engine.escalation_v2 import compute_escalation_v2
from regime_engine.escalation_v2 import compute_escalation_v2_series
from regime_engine.escalation_fast import compute_dsr_iix_ss_arrays_fast
from regime_engine.features import (
    compute_ema,
    compute_returns,
    compute_realized_vol,
)
from regime_engine.metrics import (
    compute_market_bias,
    compute_risk_level,
    compute_breakout_probability,
    compute_downside_shock_risk,
    compute_key_levels,
    compute_structural_score,
    compute_volatility_regime,
    compute_momentum_state,
    compute_liquidity_context,
    compute_instability_index,
    compute_asymmetry_metric,
)


def compute_market_state_from_df(
    df, symbol: str, *, diagnostics: bool = False, include_escalation_v2: bool = False
):
    """
    Pure engine function.
    Takes a DataFrame with normalized OHLCV columns.
    Returns full market state dict (same structure as CLI output).
    """
    close = df["close"]
    close_for_returns = df["adj_close"] if "adj_close" in df.columns else df["close"]

    ema_fast = compute_ema(close, 20)
    ema_slow = compute_ema(close, 100)
    returns = compute_returns(close_for_returns)
    rv = compute_realized_vol(returns)

    market_bias = compute_market_bias(df, n_f=20, n_s=100, alpha=0.7, beta=0.3)
    risk_level = compute_risk_level(df, n_f=20, n_s=100, peak_window=252)

    vol_regime = compute_volatility_regime(
        df,
        rl=risk_level,
        n_f=20,
        n_s=100,
        n_sh=10,
        n_lg=50,
    )

    kl = compute_key_levels(df, n_f=20, W=250, k=3, eta=0.35, N=3, min_strength=0.35)

    L_up = kl["resistances"][0]["price"] if kl["resistances"] else None
    L_dn = kl["supports"][0]["price"] if kl["supports"] else None

    bp_up, bp_dn = compute_breakout_probability(
        df,
        mb=market_bias,
        rl=risk_level,
        n_f=20,
        atr_short_n=10,
        atr_long_n=50,
        level_lookback=50,
        L_up=L_up,
        L_dn=L_dn,
    )

    dsr = compute_downside_shock_risk(
        df,
        mb=market_bias,
        rl=risk_level,
        n_f=20,
        n_s=100,
        H=60,
        m=2.5,
    )

    ss = compute_structural_score(
        df,
        mb=market_bias,
        rl=risk_level,
        dsr=dsr,
        key_levels=kl,
        n_f=20,
        n_s=100,
        n_c=20,
    )

    momentum = compute_momentum_state(
        df,
        mb=market_bias,
        ss=ss,
        vrs=float(vol_regime["vrs"]),
        bp_up=bp_up,
        bp_dn=bp_dn,
        n_f=20,
        n_m=20,
        k_m=2.0,
        n_c=20,
    )

    liquidity = compute_liquidity_context(
        df,
        vrs=float(vol_regime["vrs"]),
        er=float(momentum["er"]),
        n_dv=20,
        h=5,
    )

    iix = compute_instability_index(
        df,
        rl=risk_level,
        dsr=dsr,
        vrs=float(vol_regime["vrs"]),
        lq=float(liquidity["lq"]),
        er=float(momentum["er"]),
        n_f=20,
    )

    asm = compute_asymmetry_metric(
        df,
        bp_up=bp_up,
        bp_dn=bp_dn,
        dsr=dsr,
        rl=risk_level,
        mb=market_bias,
        er=float(momentum["er"]),
        iix=iix,
        H=60,
        gamma=1.0,
    )

    asof = df.index[-1].date().isoformat()

    classification_metrics = {
        "MB": float(market_bias),
        "SS": float(ss),
        "IIX": float(iix),
        "ASM": float(asm),
        "DSR": float(dsr),
        "risk_level": float(risk_level),
        "BP_up": float(bp_up),
        "BP_dn": float(bp_dn),
        "VRS": float(vol_regime["vrs"]),
        "LQ": float(liquidity["lq"]),
        "momentum": {
            "state": momentum["state"],
            "index": float(momentum["ii"]),
        },
        "vol_regime": {
            "value": float(vol_regime["vrs"]),
            "label": vol_regime["label"],
            "trend": _trend_to_float(vol_regime["trend"], "RISING", "FALLING"),
        },
        "liquidity": {
            "value": float(liquidity["lq"]),
            "label": liquidity["label"],
            "trend": _trend_to_float(liquidity["trend"], "IMPROVING", "DETERIORATING"),
        },
    }
    classification = classify_to_dict(classification_metrics, diagnostics=diagnostics)

    output = {
        "symbol": symbol.upper(),
        "asof": asof,
        "key_levels": kl,
        "vol_regime": vol_regime,
        "momentum": momentum,
        "liquidity": liquidity,
        "metrics": {
            "price": float(close.iloc[-1]),
            "ema_fast": float(ema_fast.iloc[-1]),
            "ema_slow": float(ema_slow.iloc[-1]),
            "realized_vol": float(rv.iloc[-1]),
            "market_bias": float(market_bias),
            "risk_level": float(risk_level),
            "vrs": float(vol_regime["vrs"]),
            "breakout_up": float(bp_up),
            "breakout_down": float(bp_dn),
            "downside_shock_risk": float(dsr),
            "structural_score": float(ss),
            "cms": float(momentum["cms"]),
            "ii": float(momentum["ii"]),
            "lq": float(liquidity["lq"]),
            "instability_index": float(iix),
            "asymmetry_metric": float(asm),
        },
        "classification": classification,
    }

    # --- Escalation v2 (tail composite): fast path with precomputed series ---
    if include_escalation_v2 and len(df) >= 20:
        dsr_arr, iix_arr, ss_arr = compute_dsr_iix_ss_arrays_fast(df, symbol)
        close_arr = close.iloc[20:].astype(float).values
        ema_arr = ema_slow.iloc[20:].astype(float).values
        escalation_v2, esc_parts = compute_escalation_v2(
            dsr=dsr_arr,
            iix=iix_arr,
            ss=ss_arr,
            close=close_arr,
            ema=ema_arr,
        )
        output["escalation_v2"] = float(escalation_v2)

        # Build escalation_v2 series via vectorized compute_escalation_v2_series
        esc_full = compute_escalation_v2_series(
            dsr_arr, iix_arr, ss_arr, close_arr, ema_arr
        )
        # First valid escalation at bar 31 (w_max-1 = 11 in 0-based close_arr)
        w_max = max(10, 5, 10, 5) + 2  # 12
        n_esc = max(0, len(df) - 31)
        esc_vals = list(esc_full[w_max - 1 : w_max - 1 + n_esc]) if n_esc > 0 else []
        esc_v2_series = pd.Series(
            [float("nan")] * min(31, len(df)) + esc_vals,
            index=df.index,
        )
        esc_v2_pct_series = rolling_percentile_transform(esc_v2_series, window=504)
        escalation_v2_pct_today = esc_v2_pct_series.iloc[-1] if len(esc_v2_pct_series) else float("nan")

        escalation_bucket, escalation_action, escalation_thresholds = compute_bucket_from_percentile(
            escalation_v2_pct_today
        )
        output["escalation_bucket"] = escalation_bucket
        output["escalation_action"] = escalation_action
        output["escalation_bucket_thresholds"] = escalation_thresholds
        output["escalation_v2_parts"] = {
            "C1_DSR_level": float(esc_parts["C1_DSR_level"]),
            "C2_DSR_delta": float(esc_parts["C2_DSR_delta"]),
            "C3_IIX_delta": float(esc_parts["C3_IIX_delta"]),
            "C4_Structural_decay": float(esc_parts["C4_Structural_decay"]),
            "C5_Div_accel": float(esc_parts["C5_Div_accel"]),
        }
        raw = esc_parts.get("raw", {})
        raw["audit"] = esc_parts.get("audit", {})
        output["escalation_v2_raw"] = raw

    return output


def get_regime_history(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    diagnostics: bool = False,
) -> pd.DataFrame:
    """
    Load data, filter by date range, run engine with expanding window per date.
    Returns DataFrame with: date, regime_label, confidence, instability_index,
    downside_shock_risk, risk_level, vrs, market_bias, structural_score.
    """
    df = load_sample_data(symbol, n_bars=10000)
    df.index = pd.to_datetime(df.index)
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    if df.index.tz is not None:
        start = start.tz_localize(df.index.tz) if start.tz is None else start
        end = end.tz_localize(df.index.tz) if end.tz is None else end
    mask = (df.index >= start) & (df.index <= end)
    df_range = df.loc[mask]

    rows = []
    for date in df_range.index:
        sub = df.loc[:date]
        if len(sub) < 20:
            continue
        out = compute_market_state_from_df(sub, symbol, diagnostics=diagnostics)
        cls = out["classification"]
        m = out.get("metrics", {})
        rows.append({
            "date": date.date().isoformat() if hasattr(date, "date") else str(date)[:10],
            "regime_label": cls["regime_label"],
            "confidence": float(cls["confidence"]),
            "instability_index": float(m.get("instability_index", float("nan"))),
            "downside_shock_risk": float(m.get("downside_shock_risk", float("nan"))),
            "risk_level": float(m.get("risk_level", float("nan"))),
            "vrs": float(m.get("vrs", float("nan"))),
            "market_bias": float(m.get("market_bias", float("nan"))),
            "structural_score": float(m.get("structural_score", float("nan"))),
        })

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the regime engine (offline).")
    parser.add_argument(
        "--inspect-crashes",
        action="store_true",
        help="Inspect 2020/2008/2022 crash windows (timing question). Runs scripts/inspect_crash_windows.py.",
    )
    parser.add_argument("--symbol", help="Asset symbol, e.g., SPY (default: SPY)")
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Include confidence diagnostics breakdown (components + drivers).",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON (indent=2).")
    parser.add_argument("--jsonl", action="store_true", help="Output JSON Lines (one line).")
    parser.add_argument(
        "--history",
        nargs=2,
        metavar=("START", "END"),
        help="Output regime history as CSV for date range, e.g. --history 2020-02-01 2020-04-01",
    )
    args = parser.parse_args()

    if args.inspect_crashes:
        root = Path(__file__).resolve().parents[2]
        script = root / "scripts" / "inspect_crash_windows.py"
        subprocess.run(
            [sys.executable, str(script), "--csv"],
            cwd=root,
            check=True,
        )
        return

    if not args.symbol:
        parser.error("--symbol is required (or use --inspect-crashes)")

    if args.history:
        start_date, end_date = args.history
        hist_df = get_regime_history(args.symbol, start_date, end_date, diagnostics=args.diagnostics)
        print(hist_df.to_csv(index=False))
        return

    df = load_sample_data(args.symbol)
    output = compute_market_state_from_df(
        df, args.symbol, diagnostics=args.diagnostics, include_escalation_v2=True
    )

    if args.jsonl:
        print(json.dumps(output, separators=(",", ":"), sort_keys=True))
    elif args.pretty:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(json.dumps(output, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
