from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd

from regime_engine.cli import compute_market_state_from_df
from regime_engine.escalation_v2 import compute_escalation_v2
from regime_engine.features import compute_ema


# -----------------
# CONFIG
# -----------------
CSV_PATH = Path("data/btcusd_clean.csv")  # use cleaned BTCUSD data
FORWARD_WINDOWS = [5, 10, 20]
STRESS_DAY_THRESHOLD = -0.02  # -2% daily return defines a "stress day"
PRE_STRESS_LOOKBACKS = [5, 10, 20]  # days before stress day to evaluate warnings


def load_csv(path: Path | None = None) -> pd.DataFrame:
    """
    Loads Yahoo-style CSV or _clean.csv:
    Date, Open, High, Low, Close, [Adj Close], Volume
    Normalizes to: timestamp, open, high, low, close, volume
    """
    p = path if path is not None else CSV_PATH
    df = pd.read_csv(p)

    # Normalize column names (handle both Date and date)
    df.columns = [c.strip() for c in df.columns]
    col_map = {"Date": "timestamp", "date": "timestamp", "Open": "open", "High": "high",
               "Low": "low", "Close": "close", "Volume": "volume", "Adj Close": "adj_close"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Ensure timestamp exists
    if "timestamp" not in df.columns:
        raise ValueError(f"CSV must have Date column. Found: {list(df.columns)}")

    # Drop non-price rows (e.g., dividend rows)
    for c in ["open", "high", "low", "close"]:
        if c in df.columns:
            df = df[pd.to_numeric(df[c], errors="coerce").notna()]

    # adj_close: use Adj Close if present, else Close (for _clean.csv)
    if "adj_close" in df.columns:
        df["adj_close"] = df["adj_close"].astype(float)
    elif "close" in df.columns:
        df["adj_close"] = df["close"].astype(float)
    else:
        raise ValueError("CSV must have Close or Adj Close")

    # Ensure types
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    for c in ["open", "high", "low", "close", "adj_close"]:
        if c in df.columns:
            df[c] = df[c].astype(float)
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

    # Sort and drop rows missing required OHLC
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

    # Set timestamp as index (engine expects datetime index for asof)
    df = df.set_index("timestamp")

    return df


def add_forward_returns(df: pd.DataFrame) -> pd.DataFrame:
    for w in FORWARD_WINDOWS:
        df[f"fwd_{w}"] = df["adj_close"].shift(-w) / df["adj_close"] - 1.0
    return df


def run_engine_over_history(df: pd.DataFrame, symbol: str = "SPY") -> pd.DataFrame:
    """
    Runs your deterministic engine bar-by-bar by feeding an expanding window df[:i+1].
    Stores regime + confidence + key risk metrics for later validation.
    """
    regimes: List[str] = []
    confidences: List[float] = []
    convictions: List[str] = []

    # store a few core risk/context series so we can test "warning" behavior
    iix_list: List[float] = []
    dsr_list: List[float] = []
    vrs_list: List[float] = []
    lq_list: List[float] = []
    rl_list: List[float] = []
    ss_list: List[float] = []
    mb_list: List[float] = []

    for i in range(len(df)):
        sub = df.iloc[: i + 1].copy()
        out = compute_market_state_from_df(sub, symbol)

        cls = out["classification"]
        regimes.append(cls["regime_label"])
        confidences.append(float(cls["confidence"]))

        # conviction tag is embedded in strategy_tags (HIGH/MEDIUM/LOW_CONVICTION)
        tags = cls.get("strategy_tags", [])
        conv = next((t for t in tags if t.endswith("_CONVICTION")), "UNKNOWN_CONVICTION")
        convictions.append(conv)

        # pull from out["metrics"] (your canonical numeric dict)
        m = out.get("metrics", {})
        iix_list.append(float(m.get("instability_index", np.nan)))
        dsr_list.append(float(m.get("downside_shock_risk", np.nan)))
        vrs_list.append(float(m.get("vrs", np.nan)))
        lq_list.append(float(m.get("lq", np.nan)))
        rl_list.append(float(m.get("risk_level", np.nan)))
        ss_list.append(float(m.get("structural_score", np.nan)))
        mb_list.append(float(m.get("market_bias", np.nan)))

    # Add escalation_v2 (requires arrays; compute from bar 20 onward, min 12 bars for windows)
    ema_100 = compute_ema(df["adj_close"], 100)
    min_bars = 12  # max(windows) + 2
    escalation_v2_list: List[float] = [float("nan")] * (20 + min_bars - 1)
    for i in range(20 + min_bars - 1, len(df)):
        dsr_arr = np.array(dsr_list[20 : i + 1], dtype=float)
        iix_arr = np.array(iix_list[20 : i + 1], dtype=float)
        ss_arr = np.array(ss_list[20 : i + 1], dtype=float)
        close_arr = df["adj_close"].iloc[20 : i + 1].astype(float).values
        ema_arr = ema_100.iloc[20 : i + 1].astype(float).values
        esc, _ = compute_escalation_v2(dsr_arr, iix_arr, ss_arr, close_arr, ema_arr)
        escalation_v2_list.append(float(esc))

    df = df.copy()
    df["regime"] = regimes
    df["confidence"] = confidences
    df["conviction"] = convictions
    df["iix"] = iix_list
    df["dsr"] = dsr_list
    df["vrs"] = vrs_list
    df["lq"] = lq_list
    df["risk_level"] = rl_list
    df["structural_score"] = ss_list
    df["market_bias"] = mb_list
    df["escalation_v2"] = escalation_v2_list
    return df


def regime_forward_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Forward-return stats grouped by regime and also by regime+conviction.
    """
    rows = []

    def summarize(group: pd.DataFrame, key: str) -> Dict[str, Any]:
        row: Dict[str, Any] = {"group": key, "count": int(len(group))}
        for w in FORWARD_WINDOWS:
            s = group[f"fwd_{w}"].dropna()
            row[f"mean_fwd_{w}"] = float(s.mean()) if len(s) else np.nan
            row[f"median_fwd_{w}"] = float(s.median()) if len(s) else np.nan
            row[f"winrate_fwd_{w}"] = float((s > 0).mean()) if len(s) else np.nan
        return row

    # by regime
    for reg, g in df.groupby("regime"):
        rows.append(summarize(g, f"regime={reg}"))

    # by regime + conviction
    for (reg, conv), g in df.groupby(["regime", "conviction"]):
        rows.append(summarize(g, f"regime={reg} | {conv}"))

    return pd.DataFrame(rows).sort_values("mean_fwd_10", ascending=False)


def stress_day_warning_test(df: pd.DataFrame) -> pd.DataFrame:
    """
    Stress day = daily return <= threshold.
    For each stress day, look back 5/10/20 days and check:
      - fraction of days flagged PANIC_RISK or SHOCK
      - average iix/dsr in the lookback window
      - average confidence in the lookback window
    Compare vs baseline random windows (same number of windows).
    """
    d = df.copy()
    d["ret_1"] = d["adj_close"].pct_change()
    # Use integer positions (not index values) for slicing
    stress_positions = np.where(d["ret_1"].values <= STRESS_DAY_THRESHOLD)[0].tolist()

    if not stress_positions:
        return pd.DataFrame([{"note": "No stress days found for threshold."}])

    def window_slice(end_pos: int, lookback: int) -> pd.DataFrame:
        start = max(0, end_pos - lookback)
        return d.iloc[start:end_pos]

    def compute_window_features(win: pd.DataFrame) -> Dict[str, Any]:
        if len(win) == 0:
            return {
                "risk_flag_rate": np.nan,
                "mean_iix": np.nan,
                "mean_dsr": np.nan,
                "mean_conf": np.nan,
            }
        risk_flags = win["regime"].isin(["PANIC_RISK", "SHOCK"]).mean()
        return {
            "risk_flag_rate": float(risk_flags),
            "mean_iix": float(win["iix"].mean()),
            "mean_dsr": float(win["dsr"].mean()),
            "mean_conf": float(win["confidence"].mean()),
        }

    out_rows = []
    n_windows = len(stress_positions)

    rng = np.random.default_rng(7)
    # baseline endpoints: integer positions with enough lookback
    baseline_candidates = [
        i for i in range(len(d)) if i >= max(PRE_STRESS_LOOKBACKS)
    ]
    baseline_endpoints = rng.choice(
        baseline_candidates,
        size=n_windows,
        replace=(n_windows > len(baseline_candidates)),
    ).tolist()

    for lb in PRE_STRESS_LOOKBACKS:
        # stress windows
        stress_feats = [compute_window_features(window_slice(i, lb)) for i in stress_positions]
        stress_avg = pd.DataFrame(stress_feats).mean(numeric_only=True)

        # baseline windows
        base_feats = [compute_window_features(window_slice(i, lb)) for i in baseline_endpoints]
        base_avg = pd.DataFrame(base_feats).mean(numeric_only=True)

        out_rows.append(
            {
                "lookback_days": lb,
                "stress_risk_flag_rate": float(stress_avg["risk_flag_rate"]),
                "baseline_risk_flag_rate": float(base_avg["risk_flag_rate"]),
                "stress_mean_iix": float(stress_avg["mean_iix"]),
                "baseline_mean_iix": float(base_avg["mean_iix"]),
                "stress_mean_dsr": float(stress_avg["mean_dsr"]),
                "baseline_mean_dsr": float(base_avg["mean_dsr"]),
                "stress_mean_conf": float(stress_avg["mean_conf"]),
                "baseline_mean_conf": float(base_avg["mean_conf"]),
            }
        )

    return pd.DataFrame(out_rows)


def regime_risk_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Risk-focused validation:
    - forward max drawdown over next N days
    - tail returns (5th percentile) over next N days
    - probability of a -3% day within next N days
    """
    d = df.copy()
    d["ret_1"] = d["adj_close"].pct_change()

    def fwd_max_drawdown(closes: np.ndarray) -> float:
        # max drawdown within the window relative to start
        start = closes[0]
        if start <= 0:
            return np.nan
        dd = (closes / start) - 1.0
        return float(dd.min())

    rows = []
    horizons = [10, 20]

    for reg, g in d.groupby("regime"):
        row = {"regime": reg, "count": int(len(g))}
        # Use integer positions (df has DatetimeIndex)
        idxs = d.index.get_indexer(g.index)

        for h in horizons:
            mdds = []
            tails = []
            p_neg3 = []

            for i in idxs:
                if i + h >= len(d):
                    continue

                window_closes = d["adj_close"].iloc[i : i + h + 1].to_numpy()
                mdds.append(fwd_max_drawdown(window_closes))

                fwd_ret = (d["adj_close"].iloc[i + h] / d["adj_close"].iloc[i]) - 1.0
                tails.append(fwd_ret)

                # probability of at least one -3% day in the next h days
                window_rets = d["ret_1"].iloc[i + 1 : i + h + 1]
                p_neg3.append(float((window_rets <= -0.03).any()))

            row[f"mdd_{h}d_mean"] = float(np.nanmean(mdds)) if mdds else np.nan
            row[f"fwd_{h}d_p5"] = float(np.nanpercentile(tails, 5)) if tails else np.nan
            row[f"prob_-3pct_day_{h}d"] = float(np.nanmean(p_neg3)) if p_neg3 else np.nan

        rows.append(row)

    return pd.DataFrame(rows).sort_values("mdd_20d_mean")


def main():
    df = load_csv()
    df = add_forward_returns(df)

    print("Running engine over full history (this may take a bit on first run)...")
    df = run_engine_over_history(df, symbol="SPY")

    results_df = df.reset_index()
    results_df = results_df.rename(columns={"timestamp": "date"})
    results_df[["date", "regime", "confidence", "risk_level", "dsr", "iix", "structural_score", "market_bias"]].rename(
        columns={"dsr": "downside_shock_risk", "iix": "instability_index"}
    ).to_csv("validation_outputs/regime_timeline.csv", index=False)

    # Save the annotated dataset for later analysis
    out_dir = Path("validation_outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "spy_regime_annotated.csv", index=True)

    print("\n=== Forward Return Stats (Regime + Regime|Conviction) ===")
    stats = regime_forward_stats(df)
    stats.to_csv(out_dir / "regime_forward_stats.csv", index=False)
    print(stats.head(30).to_string(index=False))

    print("\n=== Risk Stats (Drawdown / Tails / -3% day probability) ===")
    risk = regime_risk_stats(df)
    risk.to_csv(out_dir / "regime_risk_stats.csv", index=False)
    print(risk.to_string(index=False))

    print("\n=== Stress-Day Warning Test (pre-stress lookback windows) ===")
    warn = stress_day_warning_test(df)
    warn.to_csv(out_dir / "stress_warning_test.csv", index=False)
    print(warn.to_string(index=False))

    print(f"\nSaved outputs to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
