import numpy as np
import pandas as pd

def forward_return(close: pd.Series, horizon: int = 20) -> pd.Series:
    return close.shift(-horizon) / close - 1.0

def forward_max_drawdown(close: pd.Series, horizon: int = 20) -> pd.Series:
    """
    Forward max drawdown over next `horizon` days.
    For each t: max drawdown from close[t] to min(close[t+1..t+horizon]) relative to close[t].
    Returns negative values (e.g., -0.12).
    """
    vals = close.values
    n = len(vals)
    out = np.full(n, np.nan, dtype=float)

    for t in range(n - horizon - 1):
        start = vals[t]
        window = vals[t+1 : t + horizon + 1]
        if start <= 0 or len(window) == 0:
            continue
        min_fwd = np.min(window)
        out[t] = (min_fwd / start) - 1.0

    return pd.Series(out, index=close.index)

def summarize_bucket(df: pd.DataFrame, bucket: str, tail_level: float = -0.10) -> dict:
    sub = df[df["bucket"] == bucket].dropna(subset=["fwd_ret_20d", "fwd_mdd_20d"])
    if len(sub) == 0:
        return {
            "bucket": bucket,
            "n": 0,
            "p_tail": np.nan,
            "p5_ret": np.nan,
            "avg_mdd": np.nan,
        }

    fwd = sub["fwd_ret_20d"].values
    mdd = sub["fwd_mdd_20d"].values

    return {
        "bucket": bucket,
        "n": int(len(sub)),
        "p_tail": float(np.mean(fwd <= tail_level)),
        "p5_ret": float(np.nanpercentile(fwd, 5)),
        "avg_mdd": float(np.nanmean(mdd)),
    }

def rolling_oos_tail_report(
    dates: pd.Series,
    close: pd.Series,
    regime: pd.Series,
    escalation_v2: pd.Series,
    bucket_func,  # function(regime_label:str, escalation_v2:float) -> (bucket, action, thresholds)
    start_train_years: int = 10,
    test_years: int = 5,
    step_months: int = 6,
    horizon: int = 20,
    tail_level: float = -0.10,
) -> pd.DataFrame:
    """
    Rolling OOS report. Deterministic.
    - Uses time splits only; no fitting, no ML.
    - Measures tail outcomes by bucket in each OOS block.

    Inputs must be aligned Series indexed by date.
    """
    df = pd.DataFrame({
        "date": pd.to_datetime(dates),
        "close": close.astype(float),
        "regime": regime.astype(str),
        "esc": escalation_v2.astype(float),
    }).dropna()

    df = df.sort_values("date").reset_index(drop=True)

    df["fwd_ret_20d"] = forward_return(df["close"], horizon=horizon)
    df["fwd_mdd_20d"] = forward_max_drawdown(df["close"], horizon=horizon)

    # bucket at time t using ONLY info at t (regime + esc)
    buckets = []
    actions = []
    for r, e in zip(df["regime"].values, df["esc"].values):
        b, a, _thr = bucket_func(r, float(e))
        buckets.append(b)
        actions.append(a)
    df["bucket"] = buckets
    df["action"] = actions

    # rolling splits by calendar time
    start_date = df["date"].iloc[0]
    end_date = df["date"].iloc[-1]

    # define initial cutoffs
    train_start = start_date
    train_end = train_start + pd.DateOffset(years=start_train_years)
    test_end = train_end + pd.DateOffset(years=test_years)

    rows = []

    while test_end <= end_date:
        train_mask = (df["date"] >= train_start) & (df["date"] < train_end)
        test_mask  = (df["date"] >= train_end) & (df["date"] < test_end)

        test_df = df.loc[test_mask].copy()

        # Summaries computed ONLY on the test period
        for bucket in ["LOW", "MED", "HIGH"]:
            s = summarize_bucket(test_df, bucket=bucket, tail_level=tail_level)
            s.update({
                "train_start": train_start.date().isoformat(),
                "train_end": train_end.date().isoformat(),
                "test_start": train_end.date().isoformat(),
                "test_end": test_end.date().isoformat(),
            })
            rows.append(s)

        # roll forward
        train_start = train_start + pd.DateOffset(months=step_months)
        train_end   = train_start + pd.DateOffset(years=start_train_years)
        test_end    = train_end + pd.DateOffset(years=test_years)

    out = pd.DataFrame(rows)

    # Add a simple "separation" metric per window (HIGH vs LOW tail probability)
    # We'll compute it by grouping on window and comparing p_tail.
    sep_rows = []
    if len(out) > 0 and "train_start" in out.columns:
        for (ts, te, qs, qe), g in out.groupby(["train_start", "train_end", "test_start", "test_end"]):
            p_low = g.loc[g["bucket"] == "LOW", "p_tail"].values
            p_high = g.loc[g["bucket"] == "HIGH", "p_tail"].values
            sep = np.nan
            if len(p_low) and len(p_high):
                sep = float(p_high[0] - p_low[0])
            sep_rows.append({
                "train_start": ts, "train_end": te, "test_start": qs, "test_end": qe,
                "tail_sep_high_minus_low": sep
            })

    sep_df = pd.DataFrame(sep_rows)
    if len(out) > 0 and len(sep_df) > 0:
        out = out.merge(sep_df, on=["train_start","train_end","test_start","test_end"], how="left")

    return out
