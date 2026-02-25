import os
import glob

import numpy as np
import pandas as pd
import streamlit as st

from core.assets_registry import core_assets, LegacyAsset, assets_by_class, get_asset
from core.engine import get_snapshot
from core.timeframes import TIMEFRAME_OPTIONS


# -----------------------------
# Helpers
# -----------------------------
def _find_latest_release_summary() -> str | None:
    candidates = []
    candidates += glob.glob("release_summary_*.csv")
    candidates += glob.glob(os.path.join("data", "release_summary_*.csv"))
    candidates += glob.glob(os.path.join("validation_outputs", "release_summary_*.csv"))
    candidates = sorted(candidates)
    return candidates[-1] if candidates else None


def _safe_read_csv(path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _status_from_escalation(x: float) -> tuple[str, str]:
    if x >= 0.75:
        return "HIGH RISK", "risk"
    if x >= 0.50:
        return "ELEVATED", "warn"
    return "NORMAL", "ok"


def _render_pill(text: str, semantic: str):
    bg = {"ok": "#1f3b2d", "warn": "#3b2f1f", "risk": "#3b1f1f"}.get(semantic, "#222")
    fg = "#e8e8e8"
    st.markdown(
        f"""
        <span style="
            display:inline-block;
            padding:0.25rem 0.55rem;
            border-radius:999px;
            background:{bg};
            color:{fg};
            font-size:0.85rem;
            border:1px solid rgba(255,255,255,0.08);
            ">
            {text}
        </span>
        """,
        unsafe_allow_html=True,
    )


def _format_label(text: str) -> str:
    """Display enum-like labels: 'TRENDING_BULL' → 'Trending Bull', 'MEDIUM_CONVICTION' → 'Medium Conviction'."""
    return str(text or "").replace("_", " ").title() or "—"


def _render_state_banner(symbol: str, asof: str, regime: str, confidence: float, conviction: str, escalation: float, risk_posture: str):
    status_label, status_sem = _status_from_escalation(escalation)

    st.markdown(
        """
        <div style="
            padding:1.25rem 1.25rem;
            margin-bottom:1.25rem;
            border-radius:18px;
            border:1px solid rgba(255,255,255,0.08);
            background:rgba(255,255,255,0.03);
        ">
        """,
        unsafe_allow_html=True,
    )

    top = st.columns([1.2, 1.0, 1.0, 1.0, 1.2])
    with top[0]:
        st.caption("Asset")
        st.subheader(symbol)
        st.caption(f"As-of: {asof}")

    with top[1]:
        st.caption("Regime")
        st.markdown(f"### {_format_label(regime)}")

    with top[2]:
        st.caption("Confidence")
        st.markdown(f'<span style="font-size:1.5rem; font-weight:700;">{confidence:.2f}</span>', unsafe_allow_html=True)
        st.caption(_format_label(conviction))

    with top[3]:
        st.caption("Escalation v2")
        st.markdown(f"### {escalation:.3f}")
        _render_pill(status_label, status_sem)

    with top[4]:
        st.caption("Capital Posture")
        st.markdown(f"### {_format_label(risk_posture)}")

    st.markdown("</div>", unsafe_allow_html=True)


def _dummy_metrics_11() -> pd.DataFrame:
    names = [
        "Trend Strength",
        "Vol Regime",
        "Drawdown Pressure",
        "Downside Shock",
        "Asymmetry / Skew",
        "Momentum State",
        "Structural Score",
        "Liquidity / Volume",
        "Gap Risk",
        "Key-Level Pressure",
        "Breadth Proxy",
    ]
    vals = np.clip(np.random.normal(0.55, 0.18, size=len(names)), 0.0, 1.0)
    return pd.DataFrame({"metric": names, "pct": vals})


def _color_tag_from_pct(p: float) -> str:
    if p >= 0.80:
        return "risk"
    if p >= 0.60:
        return "warn"
    return "ok"


def _render_metric_tiles(df: pd.DataFrame):
    # Subtle tints by semantic status
    tints = {
        "ok": "rgba(34, 197, 94, 0.06)",
        "warn": "rgba(234, 179, 8, 0.06)",
        "risk": "rgba(239, 68, 68, 0.08)",
    }
    cols = st.columns(4)
    for i, row in df.reset_index(drop=True).iterrows():
        col = cols[i % 4]
        with col:
            semantic = _color_tag_from_pct(float(row["pct"]))
            tag = {"ok": "Supportive", "warn": "Caution", "risk": "Stress"}.get(semantic, "—")
            tint = tints.get(semantic, "rgba(255,255,255,0.02)")
            st.markdown(
                f"""
                <div style="
                    padding:0.85rem 0.9rem;
                    border-radius:16px;
                    border:1px solid rgba(255,255,255,0.08);
                    background:{tint};
                    margin-bottom:0.8rem;
                ">
                  <div style="font-size:0.90rem; opacity:0.85;">{row["metric"]}</div>
                  <div style="font-size:1.25rem; font-weight:650; margin-top:0.2rem;">{float(row["pct"]):.2f}</div>
                  <div style="font-size:0.80rem; opacity:0.75; margin-top:0.15rem;">{tag}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_explanation(regime: str, escalation: float, metrics: pd.DataFrame, explanation_lines: tuple[str, ...], reasons_top: list[str], snap=None):
    st.markdown(
        """
        <div style="
            padding:1rem 1.1rem;
            border-radius:18px;
            border:1px solid rgba(255,255,255,0.08);
            background:rgba(255,255,255,0.03);
        ">
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Regime Explanation")

    status = _status_from_escalation(escalation)[0]
    st.markdown(f"- Current regime: **{_format_label(regime)}**")
    st.markdown(f"- Escalation status: **{status}** (v2={escalation:.3f})")

    # --- Proof of correct nested schema wiring ---
    if snap is not None:
        try:
            cls = snap.latest_state_raw.get("classification", {})
            rp = cls.get("risk_posture", "MISSING") if isinstance(cls, dict) else "MISSING"
            reasons = cls.get("regime_reasons", []) if isinstance(cls, dict) else []
            top = cls.get("regime_reasons_top", []) if isinstance(cls, dict) else []
            st.caption(f"Engine proof → risk_posture={rp} | reasons={len(reasons)} | top={list(top)[:3]}")
        except Exception:
            st.caption("Engine proof → (error reading classification)")

    # Prefer engine-provided explanation
    if explanation_lines:
        st.markdown("**Deterministic engine explanation:**")
        for line in explanation_lines[:5]:
            st.markdown(f"- {line}")
    elif reasons_top:
        st.markdown("**Top deterministic reason codes:**")
        for r in reasons_top[:3]:
            st.markdown(f"- `{r}`")
    else:
        # Fallback: placeholder from metric extremes
        m = metrics.sort_values("pct", ascending=False).reset_index(drop=True)
        hi = m.head(2)
        lo = m.tail(2)
        st.markdown("**Rule-derived placeholder (until engine exposes drivers explicitly):**")
        st.markdown(
            f"""
            - Primary stress drivers: **{hi.iloc[0]['metric']}** ({hi.iloc[0]['pct']:.2f}), **{hi.iloc[1]['metric']}** ({hi.iloc[1]['pct']:.2f})
            - Primary supportive drivers: **{lo.iloc[0]['metric']}** ({lo.iloc[0]['pct']:.2f}), **{lo.iloc[1]['metric']}** ({lo.iloc[1]['pct']:.2f})
            """
        )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_timeline_from_history(hist: pd.DataFrame):
    st.subheader("Timeline")

    if hist.empty:
        st.info("No full_history.csv found for this asset yet.")
        return

    # Normalize column names
    cols = {c.lower().strip(): c for c in hist.columns}

    # Prefer explicit date-like columns
    date_col = None
    for cand in ["date", "dt", "datetime", "timestamp", "time"]:
        if cand in cols:
            date_col = cols[cand]
            break

    esc_col = None
    for cand in ["escalation_v2", "escalation", "escalat", "hazard", "hazard_v2"]:
        if cand in cols:
            esc_col = cols[cand]
            break

    if esc_col is None:
        st.info("full_history.csv found, but escalation column not detected.")
        st.dataframe(hist.tail(50), width="stretch")
        return

    # Coerce escalation numeric
    hist = hist.copy()
    hist[esc_col] = pd.to_numeric(hist[esc_col], errors="coerce")

    # Coerce date index if possible
    if date_col is not None:
        hist[date_col] = pd.to_datetime(hist[date_col], errors="coerce")
        hist = hist.dropna(subset=[date_col]).sort_values(date_col)
        hist = hist.set_index(date_col)

    series = hist[esc_col].dropna()
    if series.empty:
        st.info("Escalation series exists but is empty after numeric coercion.")
        return

    # Show last N points for responsiveness
    series = series.tail(900)

    st.line_chart(pd.DataFrame({"escalation_v2": series}))


# -----------------------------
# PAGE: Dashboard
# -----------------------------
st.set_page_config(page_title="Regime Intelligence — Dashboard", layout="wide")

st.title("Regime Intelligence")
st.caption("Institutional-grade deterministic regime engine. (UI blueprint committed)")

# Sidebar controls
with st.sidebar:
    st.header("Controls")
    bars = st.number_input("Bars", min_value=250, max_value=3000, value=1500, step=250)
    version = st.text_input("Version", value="v1")
    st.divider()

    release_path = _find_latest_release_summary()
    st.caption("Release summary")
    st.write(os.path.basename(release_path) if release_path else "Not found")

# Load snapshot table
summary = _safe_read_csv(release_path) if release_path else pd.DataFrame()

if summary.empty:
    st.error("No release_summary_*.csv found. Put it in project root, data/, or validation_outputs/.")
    st.stop()

# Column detection
summary_cols = {c.lower().strip(): c for c in summary.columns}
def _col(name: str) -> str | None:
    return summary_cols.get(name.lower().strip())

sym_col = _col("symbol") or _col("ticker") or _col("asset")
reg_col = _col("regime")
conf_col = _col("confidence")
conv_col = _col("conviction")
esc_col = _col("escalation_v2") or _col("escalation") or _col("escalat")

if sym_col is None:
    st.error("release summary must contain a symbol/ticker/asset column.")
    st.stop()

core_list = core_assets()
symbols = [a["symbol"] for a in core_list]
print(f"Dashboard loading {len(symbols)} real-time core symbols: {symbols}")
assets = [LegacyAsset.from_dict(a) for a in core_list]
by_class = assets_by_class(assets)

with st.sidebar:
    asset_class = st.selectbox("Asset Class", sorted(by_class.keys()))
    asset_list = by_class[asset_class]
    symbol = st.selectbox(
        "Asset",
        [a.symbol for a in asset_list],
    )
    asset_obj = get_asset(symbol, assets)
    timeframe = st.selectbox("Timeframe", TIMEFRAME_OPTIONS, index=0)

# Cross-Asset Snapshot section
st.subheader("Deterministic Cross-Asset Regime Engine")
colA, colB = st.columns([1.15, 1.0], vertical_alignment="top")

with colA:
    st.markdown(
        """
        <div style="
            padding:1rem 1.1rem;
            border-radius:18px;
            border:1px solid rgba(255,255,255,0.08);
            background:rgba(255,255,255,0.03);
        ">
        """,
        unsafe_allow_html=True,
    )
    st.subheader("Cross-Asset Snapshot")
    keep = [c for c in [sym_col, reg_col, conf_col, conv_col, esc_col] if c and c in summary.columns]
    show = summary[keep].copy() if keep else summary.copy()
    if reg_col and reg_col in show.columns:
        show[reg_col] = show[reg_col].astype(str).apply(_format_label)
    if conv_col and conv_col in show.columns:
        show[conv_col] = show[conv_col].astype(str).apply(_format_label)
    st.dataframe(show, width="stretch", hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

with colB:
    st.markdown(
        """
        <div style="
            padding:1rem 1.1rem;
            border-radius:18px;
            border:1px solid rgba(255,255,255,0.08);
            background:rgba(255,255,255,0.03);
        ">
        """,
        unsafe_allow_html=True,
    )
    st.subheader("Audit Bundle")
    st.button("Download Release Bundle (.zip)", type="secondary", width="stretch", disabled=True)
    st.caption("Wiring happens once auth + permissions exist.")

    st.subheader("Operations")
    op = st.columns([1, 1])
    with op[0]:
        st.caption("Bars")
        st.write(int(bars))
    with op[1]:
        st.caption("Version")
        st.write(version)
    st.button("Run Release Build (this asset)", width="stretch", disabled=True)
    st.markdown("</div>", unsafe_allow_html=True)

# Resolve selected asset state via engine gateway (UI never touches validation_outputs directly)
snap = get_snapshot(symbol, timeframe=timeframe, root="validation_outputs")
hist = snap.history

regime = snap.regime_label
confidence = snap.confidence if pd.notna(snap.confidence) else 0.60
conviction = snap.conviction
escalation = snap.escalation_v2 if pd.notna(snap.escalation_v2) else 0.40
asof = snap.asof
risk_posture = snap.risk_posture

st.subheader(f"{symbol} — Current State")
_render_state_banner(f"{str(symbol)} • {timeframe}", str(asof), str(regime), float(confidence), str(conviction), float(escalation), str(risk_posture))

# Explain + Drivers (use engine metrics_11 if available, else placeholder)
left, right = st.columns([1.05, 1.2], vertical_alignment="top")
metrics11 = snap.metrics_11 if not snap.metrics_11.empty else _dummy_metrics_11()

with left:
    reasons_top = []
    try:
        cls = snap.latest_state_raw.get("classification", {})
        reasons_top = list(cls.get("regime_reasons_top", [])) if isinstance(cls, dict) else []
    except Exception:
        reasons_top = []

    _render_explanation(
        str(regime),
        float(escalation),
        metrics11,
        tuple(getattr(snap, "explanation_lines", ())),
        reasons_top,
        snap=snap,
    )

with right:
    st.subheader("Drivers (11 Metrics)")
    _render_metric_tiles(metrics11)

# Timeline + Controls (history from engine)
left2, right2 = st.columns([1.55, 1.0], vertical_alignment="top")
with left2:
    st.markdown(
        """
        <div style="
            padding:1rem 1.1rem;
            border-radius:18px;
            border:1px solid rgba(255,255,255,0.08);
            background:rgba(255,255,255,0.03);
        ">
        """,
        unsafe_allow_html=True,
    )
    _render_timeline_from_history(hist)
    st.markdown("</div>", unsafe_allow_html=True)

with right2:
    st.markdown(
        """
        <div style="
            padding:1rem 1.1rem;
            border-radius:18px;
            border:1px solid rgba(255,255,255,0.08);
            background:rgba(255,255,255,0.03);
        ">
        """,
        unsafe_allow_html=True,
    )
    st.subheader("Controls")
    st.caption("Data via core/engine gateway.")
    st.button("Download audit bundle (this asset)", width="stretch", disabled=True)
    st.markdown("</div>", unsafe_allow_html=True)
