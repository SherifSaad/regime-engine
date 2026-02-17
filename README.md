# Regime Engine

Deterministic market regime engine (11 metrics) — offline-first.

## Cross-Asset Vol Normalization (Exposure Only)

When hazard state is HIGH, exposure is scaled by a baseline vol scalar so more volatile assets are de-risked more:

- `vol_scalar = clip(ref_vol / base_vol, 0.6, 1.0)`
- `exposure_high = clip(base_expo(vol_rank) * vol_scalar, 0.3, 1.0)`

Hazard thresholds and escalation logic are unchanged; only position sizing adapts across assets. SPY is the reference (`ref_vol`); other assets use their median realized vol (`base_vol`).

## Setup (dev)
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"

## Run (placeholder)
python -m regime_engine.cli --symbol SPY
