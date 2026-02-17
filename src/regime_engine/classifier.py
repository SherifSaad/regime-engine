# src/regime_engine/classifier.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


# =========================
# Public output structure
# =========================

@dataclass(frozen=True)
class ClassificationResult:
    regime_label: str                 # e.g., TRENDING_BULL, CHOP_RISK, SHOCK, TRANSITION...
    confidence: float                 # [0, 1]
    regime_bias: str                  # BULLISH / BEARISH / NEUTRAL
    risk_posture: str                 # RISK_ON / NEUTRAL / RISK_OFF / DEFENSIVE
    strategy_tags: Tuple[str, ...]    # e.g., ("TREND_FOLLOWING", "BUY_DIPS")
    diagnostics: Dict[str, Any] | None = None


# =========================
# Helpers
# =========================

def _clip01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _clip11(x: float) -> float:
    if x < -1.0:
        return -1.0
    if x > 1.0:
        return 1.0
    return x


def _safe_get(d: Dict[str, Any], key: str, default: Any = 0.0) -> Any:
    return d.get(key, default)


def _sign(x: float, eps: float = 1e-9) -> int:
    if x > eps:
        return 1
    if x < -eps:
        return -1
    return 0


def _momentum_direction(momentum_state: str) -> int:
    s = (momentum_state or "").upper()
    if "UP" in s:
        return 1
    if "DOWN" in s:
        return -1
    return 0


def _momentum_intensity(momentum_state: str, momentum_index: float) -> float:
    s = (momentum_state or "").upper()

    if "STRONG" in s:
        kw = 0.85
    elif "WEAK" in s:
        kw = 0.55
    elif "DRIFT" in s:
        kw = 0.45
    elif "CHOP" in s or "RANGE" in s or "MEAN" in s:
        kw = 0.30
    else:
        kw = 0.40

    mi = _clip01(float(momentum_index))
    return _clip01(0.55 * kw + 0.45 * mi)


def _alignment_score(mb: float, ss: float, mom_dir: int) -> float:
    mb_s = _sign(mb)
    ss_s = _sign(ss)

    votes = [mb_s, ss_s, mom_dir]
    nonzero = [v for v in votes if v != 0]

    if not nonzero:
        return 0.35

    if all(v == nonzero[0] for v in nonzero):
        return 1.0

    if len(nonzero) == 3:
        if nonzero.count(1) == 2 or nonzero.count(-1) == 2:
            return 0.60
        return 0.35

    return 0.85 if nonzero[0] == nonzero[1] else 0.40


def _liquidity_quality(lq_value: float, lq_trend: float, lq_label: str) -> float:
    v = _clip01(float(lq_value))
    t = _clip11(float(lq_trend))

    label = (lq_label or "").upper()
    if "THIN" in label or "POOR" in label:
        lab = 0.25
    elif "NORMAL" in label:
        lab = 0.60
    elif "DEEP" in label or "STRONG" in label:
        lab = 0.80
    else:
        lab = 0.55

    trend_boost = 0.15 * t
    return _clip01(0.55 * v + 0.35 * lab + trend_boost)


def _vol_stability(vrs_value: float, vrs_label: str, vrs_trend: float) -> float:
    v = _clip01(float(vrs_value))
    t = _clip11(float(vrs_trend))
    lab = (vrs_label or "").upper()

    base = 1.0 - v

    if "EXTREME" in lab or "PANIC" in lab:
        base *= 0.65
    elif "ELEVATED" in lab:
        base *= 0.85
    elif "NORMAL" in lab or "CALM" in lab:
        base *= 1.00
    else:
        base *= 0.90

    base += (-0.10 * t)  # rising vol penalizes stability
    return _clip01(base)


def _asymmetry_penalty(asm: float) -> float:
    a = abs(_clip11(float(asm)))
    return _clip01(1.0 - 0.25 * a)


def _instability_quality(iix: float) -> float:
    return _clip01(1.0 - _clip01(float(iix)))


def _shock_quality(dsr: float) -> float:
    x = _clip01(float(dsr))
    return _clip01(1.0 - (x ** 1.35))


def _trend_strength(mb: float, ss: float) -> float:
    return _clip01(0.55 * abs(_clip11(mb)) + 0.45 * abs(_clip11(ss)))


def _get_lq_trend_num(x: Any) -> float:
    """
    Accepts numeric trend or strings like IMPROVING/DETERIORATING/FLAT.
    Returns [-1,1].
    """
    if isinstance(x, (int, float)):
        return _clip11(float(x))
    s = (str(x or "")).upper()
    if "IMPROV" in s or "UP" in s:
        return 0.7
    if "DETER" in s or "DOWN" in s:
        return -0.7
    return 0.0


def _get_vol_trend_num(x: Any) -> float:
    if isinstance(x, (int, float)):
        return _clip11(float(x))
    s = (str(x or "")).upper()
    if "RISING" in s or "UP" in s:
        return 0.7
    if "FALL" in s or "DOWN" in s:
        return -0.7
    return 0.0


# =========================
# Confidence
# =========================

def compute_confidence(
    metrics: Dict[str, Any],
    *,
    return_components: bool = False
) -> float | Tuple[float, Dict[str, float]]:
    """
    Confidence = coherence / alignment of the full metric stack.
    Deterministic, no ML.
    Returns:
      - confidence in [0,1]  OR
      - (confidence, components) if return_components=True
    """
    mb = float(_safe_get(metrics, "MB", 0.0))
    ss = float(_safe_get(metrics, "SS", 0.0))

    # Momentum
    momentum = _safe_get(metrics, "momentum", {}) or {}
    mom_state = str(_safe_get(momentum, "state", _safe_get(metrics, "momentum_state", "")))
    mom_index = float(_safe_get(momentum, "index", _safe_get(momentum, "intensity", _safe_get(metrics, "momentum_index", 0.0))))
    mom_dir = _momentum_direction(mom_state)
    mom_int = _momentum_intensity(mom_state, mom_index)

    # Instability / asymmetry
    iix = float(_safe_get(metrics, "IIX", 0.0))
    asm = float(_safe_get(metrics, "ASM", 0.0))

    # Liquidity
    liquidity = _safe_get(metrics, "liquidity", {}) or {}
    lq_value = float(_safe_get(liquidity, "value", _safe_get(liquidity, "lq", _safe_get(metrics, "LQ", 0.0))))
    lq_trend_raw = _safe_get(liquidity, "trend", 0.0)
    lq_trend = _get_lq_trend_num(lq_trend_raw)
    lq_label = str(_safe_get(liquidity, "label", ""))

    # Volatility regime
    vol = _safe_get(metrics, "vol_regime", {}) or {}
    vrs_value = float(_safe_get(vol, "value", _safe_get(vol, "vrs", _safe_get(metrics, "VRS", 0.0))))
    vrs_trend_raw = _safe_get(vol, "trend", 0.0)
    vrs_trend = _get_vol_trend_num(vrs_trend_raw)
    vrs_label = str(_safe_get(vol, "label", ""))

    # Downside shock risk
    dsr = float(_safe_get(metrics, "DSR", 0.0))

    # Alignment
    align = _alignment_score(mb, ss, mom_dir)  # [0,1]

    # Strength
    strength = _trend_strength(mb, ss)

    # Environment qualities
    inst_q = _instability_quality(iix)
    asm_q = _asymmetry_penalty(asm)
    lq_q = _liquidity_quality(lq_value, lq_trend, lq_label)
    vol_q = _vol_stability(vrs_value, vrs_label, vrs_trend)
    shock_q = _shock_quality(dsr)

    raw = (
        0.20 * strength +
        0.22 * align +
        0.14 * mom_int +
        0.14 * inst_q +
        0.10 * lq_q +
        0.10 * vol_q +
        0.10 * shock_q
    )

    raw *= asm_q
    conf = _clip01(raw)

    if not return_components:
        return conf

    components = {
        "strength": strength,
        "alignment": align,
        "momentum_intensity": mom_int,
        "instability_quality": inst_q,
        "liquidity_quality": lq_q,
        "vol_stability": vol_q,
        "shock_quality": shock_q,
        "asymmetry_penalty": asm_q,
    }
    return conf, components


def _drivers_from_components(components: Dict[str, float]) -> Tuple[List[str], List[str]]:
    """
    Produce short textual reasons.
    """
    pos: List[str] = []
    neg: List[str] = []

    def pos_if(k: str, thr: float, msg: str) -> None:
        if components.get(k, 0.0) >= thr:
            pos.append(msg)

    def neg_if(k: str, thr: float, msg: str) -> None:
        if components.get(k, 1.0) <= thr:
            neg.append(msg)

    pos_if("strength", 0.70, "Strong directional strength (|MB| & |SS| high).")
    pos_if("alignment", 0.70, "MB/SS/Momentum aligned (signal coherence).")
    pos_if("shock_quality", 0.80, "Downside shock risk is low (DSR supportive).")
    pos_if("liquidity_quality", 0.60, "Liquidity is supportive / improving.")
    pos_if("vol_stability", 0.55, "Volatility conditions are reasonably stable.")
    pos_if("instability_quality", 0.60, "Instability is contained (IIX not elevated).")
    pos_if("momentum_intensity", 0.60, "Momentum intensity supports the move.")

    neg_if("momentum_intensity", 0.45, "Momentum is weak / drifting (limits conviction).")
    neg_if("instability_quality", 0.50, "Instability is elevated (choppier tape).")
    neg_if("vol_stability", 0.45, "Volatility is elevated / unstable (reduces clarity).")
    neg_if("liquidity_quality", 0.45, "Liquidity is weak / deteriorating (execution risk).")
    neg_if("shock_quality", 0.60, "Downside shock risk is non-trivial (tail risk).")
    neg_if("asymmetry_penalty", 0.90, "Asymmetry/skew is meaningful (conflicting signals).")
    neg_if("alignment", 0.55, "Signals are mixed (MB/SS/Momentum disagreement).")

    return pos[:4], neg[:4]


# =========================
# Regime Label + Tags
# =========================

def classify(metrics: Dict[str, Any], *, diagnostics: bool = False) -> ClassificationResult:
    mb = float(_safe_get(metrics, "MB", 0.0))
    ss = float(_safe_get(metrics, "SS", 0.0))
    iix = float(_safe_get(metrics, "IIX", 0.0))
    asm = float(_safe_get(metrics, "ASM", 0.0))
    dsr = float(_safe_get(metrics, "DSR", 0.0))
    rl = float(_safe_get(metrics, "risk_level", 0.0))

    # Breakout probabilities if present
    bp_up = float(_safe_get(metrics, "BP_up", _safe_get(metrics, "BP_UP", 0.0)))
    bp_dn = float(_safe_get(metrics, "BP_dn", _safe_get(metrics, "BP_DN", 0.0)))

    # Momentum
    momentum = _safe_get(metrics, "momentum", {}) or {}
    mom_state = str(_safe_get(momentum, "state", _safe_get(metrics, "momentum_state", "")))
    mom_index = float(_safe_get(momentum, "index", _safe_get(momentum, "intensity", _safe_get(metrics, "momentum_index", 0.0))))
    mom_dir = _momentum_direction(mom_state)
    mom_int = _momentum_intensity(mom_state, mom_index)

    # Volatility
    vol = _safe_get(metrics, "vol_regime", {}) or {}
    vrs_value = float(_safe_get(vol, "value", _safe_get(vol, "vrs", _safe_get(metrics, "VRS", 0.0))))
    vrs_label = str(_safe_get(vol, "label", ""))
    vrs_trend = _get_vol_trend_num(_safe_get(vol, "trend", 0.0))

    # Liquidity
    liquidity = _safe_get(metrics, "liquidity", {}) or {}
    lq_value = float(_safe_get(liquidity, "value", _safe_get(liquidity, "lq", _safe_get(metrics, "LQ", 0.0))))
    lq_trend = _get_lq_trend_num(_safe_get(liquidity, "trend", 0.0))
    lq_label = str(_safe_get(liquidity, "label", ""))

    # Derived helper scores
    align = _alignment_score(mb, ss, mom_dir)
    lq_q = _liquidity_quality(lq_value, lq_trend, lq_label)
    vol_q = _vol_stability(vrs_value, vrs_label, vrs_trend)
    inst_q = _instability_quality(iix)

    # Confidence (+ optional components)
    diag_obj: Dict[str, Any] | None = None
    if diagnostics:
        conf, comps = compute_confidence(metrics, return_components=True)  # type: ignore[assignment]
        pos, neg = _drivers_from_components(comps)
        why = ""
        if neg:
            why = "Confidence limited mainly by: " + " ".join(neg[:1])
        elif pos:
            why = "Confidence supported by: " + " ".join(pos[:1])
        diag_obj = {
            "components": comps,
            "drivers_positive": pos,
            "drivers_negative": neg,
            "why": why,
        }
    else:
        conf = float(compute_confidence(metrics))  # type: ignore[arg-type]

    # Bias
    if mb > 0.20 and ss > 0.15:
        bias = "BULLISH"
    elif mb < -0.20 and ss < -0.15:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    # Risk posture
    if dsr >= 0.70 or iix >= 0.70 or vol_q <= 0.35:
        risk_posture = "RISK_OFF"
    elif dsr >= 0.55 or iix >= 0.55 or lq_q <= 0.40:
        risk_posture = "DEFENSIVE"
    elif lq_q >= 0.65 and inst_q >= 0.60 and vol_q >= 0.55:
        risk_posture = "RISK_ON"
    else:
        risk_posture = "NEUTRAL"

    # Regime rules (priority: SHOCK > PANIC_RISK > TRENDING > CHOP_RISK > TRANSITION)
    # --- Crash / Shock regime: high downside tail risk + stressed conditions ---
    # Goal: capture crash-like environments (or imminent crash conditions) deterministically.
    # Single SHOCK block: crash-specific (dsr+instability+vol+bearish) OR extreme DSR OR extreme vol+instability
    if (
        (dsr >= 0.70 and (iix >= 0.70 or rl >= 0.75) and vrs_value >= 0.60 and mb <= -0.25 and ss <= -0.25)
        or (dsr >= 0.80)
        or (vrs_value >= 0.75 and iix >= 0.65)
    ):
        regime = "SHOCK"
        bias = "BEARISH"
        risk_posture = "DEFENSIVE"
    elif dsr >= 0.65 or iix >= 0.65 or (vrs_value >= 0.60 and lq_q <= 0.45):
        regime = "PANIC_RISK"
    elif (mb >= 0.55 and ss >= 0.40 and mom_dir >= 0 and align >= 0.70 and iix <= 0.55):
        regime = "TRENDING_BULL"
    elif (mb <= -0.55 and ss <= -0.40 and mom_dir <= 0 and align >= 0.70 and iix <= 0.55):
        regime = "TRENDING_BEAR"
    # --- Force a real bearish trend regime when direction + structure agree ---
    elif (mb <= -0.35) and (ss <= -0.25) and (conf >= 0.45):
        regime = "TRENDING_BEAR"
        bias = "BEARISH"
        risk_posture = "CAUTIOUS"
    elif (abs(mb) <= 0.25 and abs(ss) <= 0.25 and mom_int <= 0.45) or (
        align <= 0.45 and mom_int <= 0.45 and max(bp_up, bp_dn) <= 0.55
    ):
        regime = "CHOP_RISK"
    else:
        regime = "TRANSITION_BREAKOUT_SETUP" if max(bp_up, bp_dn) >= 0.62 else "TRANSITION"

    # Guardrail: don't call it TRENDING when confidence is not strong
    # Exception: softer TRENDING_BEAR (mb<=-0.35, ss<=-0.25) is allowed with conf>=0.45
    if regime in ("TRENDING_BULL", "TRENDING_BEAR") and conf < 0.65:
        if not (regime == "TRENDING_BEAR" and mb <= -0.35 and ss <= -0.25 and conf >= 0.45):
            regime = "TRANSITION"

    # Strategy tags
    tags: List[str] = []

    if regime in ("TRENDING_BULL", "TRENDING_BEAR"):
        if conf >= 0.65:
            tags.append("TREND_FOLLOWING")
        else:
            tags.append("WAIT_FOR_CONFIRMATION")
        if lq_q >= 0.55 and vol_q >= 0.45:
            tags.append("ADD_ON_BREAKS")
        else:
            tags.append("SIZE_DOWN")
        tags.append("BUY_DIPS" if regime == "TRENDING_BULL" else "SELL_RALLIES")

    elif regime.startswith("CHOP_RISK"):
        tags.append("MEAN_REVERSION")
        if lq_q >= 0.55:
            tags.append("FADE_EXTREMES")
        if max(bp_up, bp_dn) >= 0.60:
            tags.append("BE_READY_FOR_BREAKOUT")

    elif regime in ("PANIC_RISK", "SHOCK"):
        tags.append("CAPITAL_PRESERVATION")
        tags.append("REDUCE_LEVERAGE")
        if lq_q <= 0.45:
            tags.append("AVOID_ILLQUID_NAMES")
        if asm <= -0.35:
            tags.append("DOWNSIDE_SKEW")
        if asm >= 0.35:
            tags.append("UPSIDE_SKEW")

    else:  # TRANSITION
        tags.append("WAIT_FOR_CONFIRMATION")
        if max(bp_up, bp_dn) >= 0.62:
            tags.append("BREAKOUT_WATCH")
            tags.append("SET_ALERTS")
        if abs(_clip11(asm)) >= 0.50:
            tags.append("SKEW_CAUTION")

    # Confidence-aware tag
    if conf >= 0.75:
        tags.append("HIGH_CONVICTION")
    elif conf <= 0.45:
        tags.append("LOW_CONVICTION")
    else:
        tags.append("MEDIUM_CONVICTION")

    return ClassificationResult(
        regime_label=regime,
        confidence=_clip01(float(conf)),
        regime_bias=bias,
        risk_posture=risk_posture,
        strategy_tags=tuple(tags),
        diagnostics=diag_obj,
    )


def classify_to_dict(metrics: Dict[str, Any], *, diagnostics: bool = False) -> Dict[str, Any]:
    """
    Returns a plain dict for easy JSON/CLI printing.
    If diagnostics=True, adds a 'diagnostics' key with component breakdown and drivers.
    Also adds stable 'regime_reasons' codes (deterministic).
    """
    res = classify(metrics, diagnostics=diagnostics)

    out: Dict[str, Any] = {
        "regime_label": res.regime_label,
        "confidence": res.confidence,
        "regime_bias": res.regime_bias,
        "risk_posture": res.risk_posture,
        "strategy_tags": list(res.strategy_tags),
        "regime_reasons": [],
    }

    # --- UI-friendly summary (stable format) ---
    conviction = "HIGH" if out["confidence"] >= 0.75 else "LOW" if out["confidence"] <= 0.45 else "MEDIUM"
    out["summary"] = f"{out['regime_label']} | {out['regime_bias']} | {out['risk_posture']} | {conviction}_CONVICTION"

    # --- Reason codes (stable, no prose) ---
    # Pull raw values defensively (supports both your top-level keys and nested dicts)
    mb = float(_safe_get(metrics, "MB", 0.0))
    ss = float(_safe_get(metrics, "SS", 0.0))
    iix = float(_safe_get(metrics, "IIX", 0.0))
    dsr = float(_safe_get(metrics, "DSR", 0.0))
    asm = float(_safe_get(metrics, "ASM", 0.0))

    bp_up = float(_safe_get(metrics, "BP_up", _safe_get(metrics, "BP_UP", 0.0)))
    bp_dn = float(_safe_get(metrics, "BP_dn", _safe_get(metrics, "BP_DN", 0.0)))

    momentum = _safe_get(metrics, "momentum", {}) or {}
    mom_state = str(_safe_get(momentum, "state", _safe_get(metrics, "momentum_state", "")))
    mom_dir = _momentum_direction(mom_state)

    vol = _safe_get(metrics, "vol_regime", {}) or {}
    vrs_value = float(_safe_get(vol, "value", _safe_get(vol, "vrs", _safe_get(metrics, "VRS", 0.0))))

    liquidity = _safe_get(metrics, "liquidity", {}) or {}
    lq_value = float(_safe_get(liquidity, "value", _safe_get(liquidity, "lq", _safe_get(metrics, "LQ", 0.0))))
    lq_trend = _get_lq_trend_num(_safe_get(liquidity, "trend", 0.0))
    lq_label = str(_safe_get(liquidity, "label", ""))

    # Derived helpers (same ones used by classifier)
    strength = _trend_strength(mb, ss)
    align = _alignment_score(mb, ss, mom_dir)
    inst_q = _instability_quality(iix)
    asm_q = _asymmetry_penalty(asm)
    lq_q = _liquidity_quality(lq_value, lq_trend, lq_label)
    vol_q = _vol_stability(vrs_value, str(_safe_get(vol, "label", "")), _get_vol_trend_num(_safe_get(vol, "trend", 0.0)))
    shock_q = _shock_quality(dsr)

    reasons: List[str] = []

    # Direction
    if mb >= 0.25:
        reasons.append("MB_BULLISH")
    elif mb <= -0.25:
        reasons.append("MB_BEARISH")
    else:
        reasons.append("MB_NEUTRAL")

    if ss >= 0.25:
        reasons.append("SS_BULLISH")
    elif ss <= -0.25:
        reasons.append("SS_BEARISH")
    else:
        reasons.append("SS_NEUTRAL")

    # Coherence / alignment
    if align >= 0.70:
        reasons.append("ALIGNMENT_STRONG")
    elif align <= 0.45:
        reasons.append("ALIGNMENT_WEAK")
    else:
        reasons.append("ALIGNMENT_MIXED")

    # Trend strength
    if strength >= 0.70:
        reasons.append("TREND_STRENGTH_HIGH")
    elif strength <= 0.35:
        reasons.append("TREND_STRENGTH_LOW")
    else:
        reasons.append("TREND_STRENGTH_MEDIUM")

    # Instability / volatility / liquidity context
    if inst_q >= 0.60:
        reasons.append("INSTABILITY_CONTAINED")
    elif inst_q <= 0.45:
        reasons.append("INSTABILITY_ELEVATED")
    else:
        reasons.append("INSTABILITY_MODERATE")

    if vol_q >= 0.55:
        reasons.append("VOL_STABLE")
    elif vol_q <= 0.45:
        reasons.append("VOL_UNSTABLE")
    else:
        reasons.append("VOL_ELEVATED")

    if lq_q >= 0.60:
        reasons.append("LIQUIDITY_SUPPORTIVE")
    elif lq_q <= 0.45:
        reasons.append("LIQUIDITY_WEAK")
    else:
        reasons.append("LIQUIDITY_NORMAL")

    # Shock / tail risk
    if shock_q >= 0.80:
        reasons.append("SHOCK_RISK_LOW")
    elif shock_q <= 0.60:
        reasons.append("SHOCK_RISK_HIGH")
    else:
        reasons.append("SHOCK_RISK_MODERATE")

    # Asymmetry (penalty)
    if asm_q >= 0.93:
        reasons.append("ASYMMETRY_LOW")
    elif asm_q <= 0.85:
        reasons.append("ASYMMETRY_HIGH")
    else:
        reasons.append("ASYMMETRY_MEDIUM")

    # Breakout setup
    if max(bp_up, bp_dn) >= 0.62:
        reasons.append("BREAKOUT_SETUP")
        reasons.append("BREAKOUT_UP_EDGE" if bp_up >= bp_dn else "BREAKOUT_DOWN_EDGE")
    else:
        reasons.append("NO_BREAKOUT_EDGE")

    # Guardrail visibility (deterministic, based on your current policy)
    # If you ever change thresholds, this remains interpretable.
    if out["regime_label"] in ("TRANSITION", "TRANSITION_BREAKOUT_SETUP") and strength >= 0.70 and align >= 0.70 and out["confidence"] < 0.65:
        reasons.append("CONFIDENCE_GUARDRAIL_TRIGGERED")

    out["regime_reasons"] = reasons

    priority = [
        "TREND_STRENGTH_HIGH",
        "ALIGNMENT_STRONG",
        "SHOCK_RISK_HIGH",
        "VOL_UNSTABLE",
        "INSTABILITY_ELEVATED",
        "LIQUIDITY_WEAK",
        "BREAKOUT_SETUP",
        "CONFIDENCE_GUARDRAIL_TRIGGERED",
        "MB_BULLISH",
        "MB_BEARISH",
    ]
    out["regime_reasons_top"] = [r for r in priority if r in reasons][:3]

    # Optional diagnostics passthrough
    if diagnostics and res.diagnostics is not None:
        out["diagnostics"] = res.diagnostics

    return out
