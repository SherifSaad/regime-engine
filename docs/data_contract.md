# Regime Engine Data Contract

**Purpose:** Bar format, required/optional fields, and normalization rules. Use when ingesting or validating bar data.

## Required fields
The engine consumes a time-ordered series of bars.

Required per bar:
- timestamp (ISO 8601 string, UTC recommended)
- open (float)
- high (float)
- low (float)
- close (float)

Hard rules:
- high >= max(open, close)
- low <= min(open, close)
- prices must be > 0
- bars must be strictly increasing by timestamp
- compute metrics on bar close (never intrabar) unless explicitly configured later

## Optional fields
Optional per bar:
- volume (float) — used for Liquidity Score when available
- symbol (string) — may be provided externally (CLI arg) or embedded in records

If volume is missing:
- Liquidity uses the price-based proxy (VRS/ER) automatically (see fallbacks).

## Frequency and bar-close rule
Frequency:
- Any fixed timeframe is allowed (daily, 1h, 15m, 5m, etc.)
- Choose ONE timeframe per instrument and keep it consistent.

Bar-close rule:
- All metrics are computed once per bar at bar close.
- The engine does not attempt intrabar updates.
- Rolling windows operate in "bars", not "calendar time".

## Missing data fallbacks
The engine must remain deterministic under missing fields.

1) Missing volume
- Liquidity falls back to a price-based proxy:
  - relies on volatility regime + efficiency ratio + instability effects
- This keeps outputs stable for indices and thin feeds.

2) Missing open (gaps)
- Gap-based terms are disabled (treated as 0).
- Risk and instability still function using close-to-close returns and volatility.

3) Missing high/low (ATR)
- ATR-based components become weaker.
- Use realized-vol proxy if needed:
  - ATR_proxy ≈ close * realized_vol_fast * sqrt(Δt)

Note:
- In production, open/high/low should be present. These fallbacks are "degraded mode".

## Index liquidity proxy policy
Indices often have unreliable "volume".
Policy:
- For index-level analysis:
  - Use the ETF proxy volume (recommended)
    - SPX → SPY
    - NDX → QQQ
    - RUT → IWM
- If ETF proxy not used:
  - liquidity score uses the price-only proxy (acceptable but weaker).

## Canonical field names (engine normalization)
The engine normalizes input bars to:
- timestamp, open, high, low, close, volume (optional)

Internal outputs may use:
- vol_regime: { vrs, label, trend }
- liquidity: { lq, label, trend }
- momentum: { state, cms, ii, er }
- classification: { regime_label, confidence, ... }
