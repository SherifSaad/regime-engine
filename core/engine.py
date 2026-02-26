# core/engine.py
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from core.data_loader import compute_db_path, find_asset_bundle


# -----------------------------
# Public types
# -----------------------------
@dataclass(frozen=True)
class EngineSnapshot:
    """
    Single source-of-truth object the UI consumes.
    This is intentionally "bundle-first" today, and "live-engine" later.
    """
    symbol: str
    timeframe: str
    asof: str
    regime_label: str
    confidence: float
    conviction: str
    escalation_v2: float
    risk_posture: str  # engine output if present; else best-effort

    # Optional structured payloads for richer UI later
    latest_state_raw: Dict[str, Any]
    history: pd.DataFrame

    # Optional: 11 metric tiles / drivers (if available from engine payload)
    # Format: DataFrame with columns: metric, pct, label(optional)
    metrics_11: pd.DataFrame

    # Optional: deterministic explanation strings (if present)
    explanation_lines: Tuple[str, ...]


# -----------------------------
# Internal helpers
# -----------------------------
def _safe_read_json(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _safe_read_csv(path: Optional[str]) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _unwrap_latest_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Your bundles store the real state under payload["latest_state"].
    If it's already flat, return as-is.
    """
    ls = payload.get("latest_state")
    return ls if isinstance(ls, dict) and ls else payload


def _pick_first(d: Dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _as_float(x: Any, default: float = float("nan")) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _as_str(x: Any, default: str = "") -> str:
    try:
        s = str(x)
        return s if s else default
    except Exception:
        return default


def _title_case_enum(s: str) -> str:
    # MEDIUM_CONVICTION -> Medium Conviction
    s = s.replace("_", " ").strip().lower()
    return " ".join(w.capitalize() for w in s.split())


def _derive_risk_posture(regime_label: str, escalation_v2: float) -> str:
    # Only used if engine didn't provide it. Deterministic UI-safe fallback.
    rl = regime_label.upper().strip()

    if escalation_v2 >= 0.75:
        return "RISK_OFF / HEDGE"
    if escalation_v2 >= 0.50:
        return "NEUTRAL / DEFENSIVE"
    if "BEAR" in rl or rl in ("PANIC_RISK", "SHOCK"):
        return "DEFENSIVE"
    if "BULL" in rl:
        return "RISK_ON"
    return "NEUTRAL"


def _extract_metrics_11(state: Dict[str, Any]) -> pd.DataFrame:
    """
    Best-effort extraction of the 11-metric tiles from latest_state.json.
    If not available, return empty DF and the UI can keep placeholders.

    Supported patterns (we tolerate multiple schemas):
      - state["metrics_11"] = [{"metric": "...", "pct": 0.72}, ...]
      - state["metrics"] = { "vol_regime": {"pct": 0.61, ...}, ... }
      - state["metric_percentiles"] = {"Trend Strength": 0.7, ...}
    """
    # 1) explicit list
    m11 = state.get("metrics_11")
    if isinstance(m11, list) and m11:
        rows = []
        for r in m11:
            if isinstance(r, dict) and "metric" in r and ("pct" in r or "percentile" in r):
                rows.append(
                    {
                        "metric": _as_str(r.get("metric")),
                        "pct": _as_float(r.get("pct", r.get("percentile"))),
                        "label": _as_str(r.get("label", "")),
                    }
                )
        if rows:
            return pd.DataFrame(rows)

    # 2) dict-of-dicts with pct
    metrics = state.get("metrics")
    if isinstance(metrics, dict) and metrics:
        rows = []
        for k, v in metrics.items():
            if isinstance(v, dict):
                pct = v.get("pct", v.get("percentile"))
                if pct is not None:
                    rows.append({"metric": str(k), "pct": _as_float(pct), "label": _as_str(v.get("label", ""))})
        if rows:
            df = pd.DataFrame(rows)
            return df.sort_values("pct", ascending=False).head(11).reset_index(drop=True)

    # 3) plain mapping
    mp = state.get("metric_percentiles")
    if isinstance(mp, dict) and mp:
        rows = [{"metric": str(k), "pct": _as_float(v), "label": ""} for k, v in mp.items()]
        df = pd.DataFrame(rows)
        return df.sort_values("pct", ascending=False).head(11).reset_index(drop=True)

    return pd.DataFrame(columns=["metric", "pct", "label"])


def _extract_explanation_lines(state: Dict[str, Any]) -> Tuple[str, ...]:
    lines = []
    cls = state.get("classification") if isinstance(state.get("classification"), dict) else {}

    # Prefer classifier summary
    summ = cls.get("summary")
    if isinstance(summ, str) and summ.strip():
        lines.append(summ.strip())

    # Optional additional lines (if you later add them)
    xl = state.get("explanation_lines")
    if isinstance(xl, list):
        lines += [str(x) for x in xl if str(x).strip()]

    why = state.get("why")
    if isinstance(why, str) and why.strip():
        lines.append(why.strip())

    # de-dupe preserving order
    seen = set()
    out = []
    for l in lines:
        if l not in seen:
            seen.add(l)
            out.append(l)

    return tuple(out)


def _normalize_history(df: pd.DataFrame) -> pd.DataFrame:
    """
    Make history consistent for UI charts without assuming a rigid schema.
    - Ensures a datetime index if possible
    - Ensures escalation_v2 numeric column if exists under aliases
    """
    if df.empty:
        return df

    df = df.copy()
    cols = {c.lower().strip(): c for c in df.columns}

    # Date column preference
    date_col = None
    for cand in ["date", "dt", "datetime", "timestamp", "time"]:
        if cand in cols:
            date_col = cols[cand]
            break

    # Escalation column preference
    esc_col = None
    for cand in ["escalation_v2", "escalation", "escalat", "hazard", "hazard_v2"]:
        if cand in cols:
            esc_col = cols[cand]
            break

    if esc_col is not None:
        df[esc_col] = pd.to_numeric(df[esc_col], errors="coerce")

    if date_col is not None:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col]).sort_values(date_col)
        df = df.set_index(date_col)

    # Standardize name for charts (optional convenience)
    if esc_col is not None and esc_col != "escalation_v2":
        df = df.rename(columns={esc_col: "escalation_v2"})

    return df


def _get_snapshot_from_compute_db(symbol: str, timeframe: str) -> Optional[EngineSnapshot]:
    """
    Load state/history from compute.db (scheduler output). Returns None if no data.
    """
    db_path = compute_db_path(symbol)
    if not db_path:
        return None

    try:
        conn = sqlite3.connect(str(db_path))
        # latest_state: state_json is the full regime state (same format as bundle)
        row = conn.execute(
            "SELECT asof, state_json FROM latest_state WHERE symbol=? AND timeframe=?",
            (symbol.upper().strip(), timeframe),
        ).fetchone()
        conn.close()

        if not row or not row[1]:
            return None

        asof_val, state_json_str = row[0], row[1]
        state = json.loads(state_json_str) if isinstance(state_json_str, str) else state_json_str
        if not isinstance(state, dict):
            return None

        # Build history from state_history
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT asof, state_json FROM state_history WHERE symbol=? AND timeframe=? ORDER BY asof ASC",
            (symbol.upper().strip(), timeframe),
        ).fetchall()
        conn.close()

        hist_rows = []
        for asof, sj in rows:
            try:
                st = json.loads(sj) if isinstance(sj, str) else sj
                esc = st.get("escalation_v2")
                if esc is None:
                    esc = st.get("escalation")
                hist_rows.append({"date": asof, "escalation_v2": float(esc) if esc is not None else float("nan")})
            except Exception:
                pass
        hist = pd.DataFrame(hist_rows) if hist_rows else pd.DataFrame(columns=["date", "escalation_v2"])
        hist = _normalize_history(hist)

        cls = state.get("classification") if isinstance(state.get("classification"), dict) else {}
        regime_label = _as_str(_pick_first(cls, ["regime_label"], default="TRANSITION"))
        confidence = _as_float(_pick_first(cls, ["confidence"], default=float("nan")), default=float("nan"))
        tags = cls.get("strategy_tags", [])
        conviction = "Unknown Conviction"
        if isinstance(tags, list):
            conv = next((t for t in tags if str(t).endswith("_CONVICTION")), None)
            if conv:
                conviction = _title_case_enum(str(conv))
        escalation_v2 = _as_float(_pick_first(state, ["escalation_v2"], default=float("nan")), default=float("nan"))
        risk_posture = _as_str(_pick_first(cls, ["risk_posture"], default=""))
        if not risk_posture:
            risk_posture = _derive_risk_posture(regime_label, escalation_v2 if pd.notna(escalation_v2) else 0.0)
        metrics_11 = _extract_metrics_11(state)
        explanation_lines = _extract_explanation_lines(state)
        if conviction.endswith("_CONVICTION") or conviction.isupper():
            conviction = _title_case_enum(conviction)

        return EngineSnapshot(
            symbol=str(symbol).upper().strip(),
            timeframe=str(timeframe),
            asof=asof_val or "unknown",
            regime_label=regime_label,
            confidence=float(confidence) if pd.notna(confidence) else float("nan"),
            conviction=conviction,
            escalation_v2=float(escalation_v2) if pd.notna(escalation_v2) else float("nan"),
            risk_posture=risk_posture,
            latest_state_raw=state,
            history=hist,
            metrics_11=metrics_11,
            explanation_lines=explanation_lines,
        )
    except Exception:
        return None


# -----------------------------
# Public API (UI calls only these)
# -----------------------------
def get_snapshot(symbol: str, timeframe: str = "1day", *, root: str = "validation_outputs") -> EngineSnapshot:
    """
    Returns the latest state + full history for symbol.
    Prefers compute.db (scheduler output); falls back to validation_outputs (legacy audit bundle).
    """
    snap = _get_snapshot_from_compute_db(symbol, timeframe)
    if snap is not None:
        return snap

    bundle = find_asset_bundle(symbol, root=root)
    payload = _safe_read_json(bundle.latest_state_json)
    state = _unwrap_latest_state(payload)

    hist = _safe_read_csv(bundle.full_history_csv)
    hist = _normalize_history(hist)

    cls = state.get("classification") if isinstance(state.get("classification"), dict) else {}

    regime_label = _as_str(_pick_first(cls, ["regime_label"], default="TRANSITION"))
    confidence = _as_float(_pick_first(cls, ["confidence"], default=float("nan")), default=float("nan"))

    # conviction comes from strategy_tags like HIGH_CONVICTION / MEDIUM_CONVICTION / LOW_CONVICTION
    tags = cls.get("strategy_tags", [])
    conviction = "Unknown Conviction"
    if isinstance(tags, list):
        conv = next((t for t in tags if str(t).endswith("_CONVICTION")), None)
        if conv:
            conviction = _title_case_enum(str(conv))

    escalation_v2 = _as_float(_pick_first(state, ["escalation_v2"], default=float("nan")), default=float("nan"))
    asof = _as_str(_pick_first(state, ["asof"], default=""))

    # If asof not present, try payload or derive from history index max
    if not asof:
        asof = _as_str(payload.get("asof", ""))
    if not asof:
        if not hist.empty and hasattr(hist.index, "max"):
            try:
                asof = str(hist.index.max().date())
            except Exception:
                asof = ""
    if not asof:
        asof = "unknown"

    # risk posture: from classification
    risk_posture = _as_str(_pick_first(cls, ["risk_posture"], default=""))
    if not risk_posture:
        risk_posture = _derive_risk_posture(regime_label, escalation_v2 if pd.notna(escalation_v2) else 0.0)

    metrics_11 = _extract_metrics_11(state)
    explanation_lines = _extract_explanation_lines(state)

    # Prettify conviction if it looks like enum
    if conviction.endswith("_CONVICTION") or conviction.isupper():
        conviction = _title_case_enum(conviction)

    return EngineSnapshot(
        symbol=str(symbol).upper().strip(),
        timeframe=str(timeframe),
        asof=asof,
        regime_label=regime_label,
        confidence=float(confidence) if pd.notna(confidence) else float("nan"),
        conviction=conviction,
        escalation_v2=float(escalation_v2) if pd.notna(escalation_v2) else float("nan"),
        risk_posture=risk_posture,
        latest_state_raw=state,
        history=hist,
        metrics_11=metrics_11,
        explanation_lines=explanation_lines,
    )
