import pandas as pd
import numpy as np
from pathlib import Path

DATA_PRICE = Path("data/spy_sample.csv")
DATA_REGIME = Path("validation_outputs/regime_timeline.csv")
OUT_DIR = Path("validation_outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Load price (expect at least: Date + Close OR Adj Close) ---
px = pd.read_csv(DATA_PRICE)
if "Date" not in px.columns:
    raise SystemExit("spy_sample.csv must have a 'Date' column.")
px["Date"] = pd.to_datetime(px["Date"]).dt.tz_localize(None)
px = px.sort_values("Date")

price_col = None
for c in ["Adj Close", "AdjClose", "Close", "close"]:
    if c in px.columns:
        price_col = c
        break
if price_col is None:
    raise SystemExit("spy_sample.csv must have 'Close' or 'Adj Close' column.")
px = px[["Date", price_col]].rename(columns={price_col: "Close"}).dropna()

# --- Load regime timeline ---
rg = pd.read_csv(DATA_REGIME)

# Normalize date column name
date_col = None
for c in ["date", "Date", "datetime", "timestamp"]:
    if c in rg.columns:
        date_col = c
        break
if date_col is None:
    raise SystemExit("regime_timeline.csv must have a date-like column (date/Date/datetime/timestamp).")

rg[date_col] = pd.to_datetime(rg[date_col], utc=True, errors="coerce").dt.tz_convert(None)
rg = rg.rename(columns={date_col: "Date"})
if "regime" in rg.columns and "regime_label" not in rg.columns:
    rg = rg.rename(columns={"regime": "regime_label"})

# Required columns
needed = ["regime_label", "instability_index", "downside_shock_risk", "risk_level"]
missing = [c for c in needed if c not in rg.columns]
if missing:
    raise SystemExit(f"regime_timeline.csv missing columns: {missing}")

rg = rg[["Date", "regime_label", "instability_index", "downside_shock_risk", "risk_level"]].dropna()
rg = rg.sort_values("Date")

# Join on Date (inner keeps only common trading days)
df = pd.merge(px, rg, on="Date", how="inner").sort_values("Date").reset_index(drop=True)

# --- Define crash events from price (objective, no hand-picking) ---
# We identify major peak-to-trough drawdowns >= 15% and treat each as an event.
close = df["Close"].values
dates = df["Date"].values

running_max = np.maximum.accumulate(close)
dd = close / running_max - 1.0

# Find local minima (troughs) for drawdowns
is_trough = np.r_[False, (dd[1:-1] < dd[:-2]) & (dd[1:-1] < dd[2:]), False]
trough_idx = np.where(is_trough)[0]

events = []
min_dd_threshold = -0.15  # 15% drawdown

for t in trough_idx:
    if dd[t] > min_dd_threshold:
        continue

    # Peak index is the last time running_max was achieved before trough
    peak_price = running_max[t]
    # Find the last index <= t where close == peak_price (within tiny tolerance)
    tol = peak_price * 1e-12 + 1e-9
    peak_candidates = np.where(np.abs(close[: t + 1] - peak_price) <= tol)[0]
    if len(peak_candidates) == 0:
        continue
    p = peak_candidates[-1]

    # Event window: from peak to trough
    peak_date = pd.Timestamp(dates[p]).to_pydatetime()
    trough_date = pd.Timestamp(dates[t]).to_pydatetime()
    event_dd = float(dd[t])

    events.append((p, t, peak_date, trough_date, event_dd))

# De-duplicate overlapping events by keeping the worst trough for overlapping peak→trough windows
events = sorted(events, key=lambda x: (x[2], x[3]))
pruned = []
for e in events:
    if not pruned:
        pruned.append(e)
        continue
    last = pruned[-1]
    # overlap if this peak date is before last trough date
    if e[2] <= last[3]:
        # keep the one with deeper drawdown
        if e[4] < last[4]:
            pruned[-1] = e
    else:
        pruned.append(e)

events = pruned

# --- Warning definitions (deterministic) ---
# Early warning trigger: TRANSITION with elevated risk OR any PANIC/SHOCK (counts as warning too)
EARLY_RISKLEVEL = 0.35
EARLY_INSTABILITY = 0.55
EARLY_DSR = 0.30

def first_warning_idx(window_df: pd.DataFrame):
    # earliest date in window where conditions indicate elevated risk
    cond_transition = (
        (window_df["regime_label"] == "TRANSITION")
        & (
            (window_df["risk_level"] >= EARLY_RISKLEVEL)
            | (window_df["instability_index"] >= EARLY_INSTABILITY)
            | (window_df["downside_shock_risk"] >= EARLY_DSR)
        )
    )
    cond_panic = (window_df["regime_label"] == "PANIC_RISK")
    cond_shock = (window_df["regime_label"] == "SHOCK")

    cond_any = cond_transition | cond_panic | cond_shock
    idx = np.where(cond_any.values)[0]
    return int(idx[0]) if len(idx) else None

def first_label_idx(window_df: pd.DataFrame, label: str):
    idx = np.where((window_df["regime_label"] == label).values)[0]
    return int(idx[0]) if len(idx) else None

def first_drawdown_hit_idx(window_df: pd.DataFrame, peak_close: float, threshold: float):
    # first date where Close <= peak_close*(1-threshold)
    target = peak_close * (1.0 - threshold)
    idx = np.where((window_df["Close"].values <= target))[0]
    return int(idx[0]) if len(idx) else None

# --- Build lead-time table ---
rows = []
for (p, t, peak_date, trough_date, event_dd) in events:
    # window from peak to trough (inclusive)
    w = df.iloc[p : t + 1].copy().reset_index(drop=True)
    peak_close = float(w.loc[0, "Close"])

    # milestone indices
    warn0 = first_warning_idx(w)
    panic0 = first_label_idx(w, "PANIC_RISK")
    shock0 = first_label_idx(w, "SHOCK")

    dd10 = first_drawdown_hit_idx(w, peak_close, 0.10)  # -10%
    dd20 = first_drawdown_hit_idx(w, peak_close, 0.20)  # -20%

    def idx_to_date(i):
        return pd.Timestamp(w.loc[i, "Date"]).date().isoformat() if i is not None else ""

    def lead_days(i):
        return int(i) if i is not None else ""

    rows.append({
        "event_peak_date": pd.Timestamp(peak_date).date().isoformat(),
        "event_trough_date": pd.Timestamp(trough_date).date().isoformat(),
        "event_max_drawdown": event_dd,

        "first_warning_date": idx_to_date(warn0),
        "lead_trading_days_warning_to_peak": 0 if warn0 is not None else "",
        "lead_trading_days_warning_to_-10%": lead_days(dd10 - warn0) if (warn0 is not None and dd10 is not None) else "",
        "lead_trading_days_warning_to_-20%": lead_days(dd20 - warn0) if (warn0 is not None and dd20 is not None) else "",

        "first_panic_date": idx_to_date(panic0),
        "lead_trading_days_panic_to_-10%": lead_days(dd10 - panic0) if (panic0 is not None and dd10 is not None) else "",
        "lead_trading_days_panic_to_-20%": lead_days(dd20 - panic0) if (panic0 is not None and dd20 is not None) else "",

        "first_shock_date": idx_to_date(shock0),
        "lead_trading_days_shock_to_-10%": lead_days(dd10 - shock0) if (shock0 is not None and dd10 is not None) else "",
        "lead_trading_days_shock_to_-20%": lead_days(dd20 - shock0) if (shock0 is not None and dd20 is not None) else "",

        "date_reaches_-10%": idx_to_date(dd10),
        "date_reaches_-20%": idx_to_date(dd20),

        "n_days_peak_to_trough": int(len(w)-1),
    })

events_df = pd.DataFrame(rows).sort_values("event_peak_date")

# Summary stats (only numeric columns)
num_cols = [c for c in events_df.columns if c.startswith("lead_trading_days_")]
summary = {}
for c in num_cols:
    s = pd.to_numeric(events_df[c], errors="coerce").dropna()
    if len(s) == 0:
        continue
    summary[c] = {
        "n": int(s.shape[0]),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "p25": float(s.quantile(0.25)),
        "p75": float(s.quantile(0.75)),
        "min": float(s.min()),
        "max": float(s.max()),
    }
summary_df = pd.DataFrame(summary).T.reset_index().rename(columns={"index": "metric"}).sort_values("metric")

out_events = OUT_DIR / "lead_time_events.csv"
out_summary = OUT_DIR / "lead_time_summary.csv"
events_df.to_csv(out_events, index=False)
summary_df.to_csv(out_summary, index=False)

print("DONE")
print(f"Events:  {out_events}")
print(f"Summary: {out_summary}")
print("")
print("Top events by drawdown:")
print(events_df.sort_values('event_max_drawdown').head(10)[
    ["event_peak_date","event_trough_date","event_max_drawdown","first_warning_date","first_panic_date","first_shock_date","date_reaches_-10%","date_reaches_-20%","n_days_peak_to_trough"]
].to_string(index=False))
