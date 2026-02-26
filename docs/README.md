# Regime Engine Documentation Index

**Purpose:** Find the right doc by category. Core reference, standards, UI/ops, archive.

---

## Core Reference (use often)

| Doc | Purpose |
|-----|---------|
| [WHERE_WE_STAND.md](WHERE_WE_STAND.md) | **Start here.** Architecture + calculations summary |
| [SYMBOL_LIFECYCLE_AND_DEPLOYMENT.md](SYMBOL_LIFECYCLE_AND_DEPLOYMENT.md) | Who does what: new symbol, backfill, compute, schedulers |
| [METRIC_FORMULAS.md](METRIC_FORMULAS.md) | Metric formulas (MB, RL, DSR, VRS, etc.) |
| [METRIC_AND_ESCALATION_CODE.md](METRIC_AND_ESCALATION_CODE.md) | Escalation code reference, percentile modes, constants |
| [COMPUTE_PIPELINE_ARCHITECTURE.md](COMPUTE_PIPELINE_ARCHITECTURE.md) | Entrypoints, call chains, model vs table mapping |
| [SCHEMA_VERSIONS.md](SCHEMA_VERSIONS.md) | DB schema, escalation_history_v3 columns |
| [ERA_DETECTION_BAI_PERRON.md](ERA_DETECTION_BAI_PERRON.md) | Bai–Perron era detection, asset class → benchmark |
| [TIMEFRAME_CONVENTION.md](TIMEFRAME_CONVENTION.md) | Canonical timeframes, aliases |
| [data_contract.md](data_contract.md) | Bar format, required/optional fields |

---

## Standards & Audit

| Doc | Purpose |
|-----|---------|
| [INSTITUTIONAL_RISK_INTELLIGENCE_STANDARD_V2.md](INSTITUTIONAL_RISK_INTELLIGENCE_STANDARD_V2.md) | **Current** institutional standard (v2.2, locked) |
| [METRICS_AUDIT_INSTITUTIONAL_STANDARD.md](METRICS_AUDIT_INSTITUTIONAL_STANDARD.md) | Audit checklist, metric verification |
| [MATH_EVALUATION_INSTITUTIONAL_STANDARDS.md](MATH_EVALUATION_INSTITUTIONAL_STANDARDS.md) | Full math evaluation vs institutional standards |
| [HEDGE_FUND_STANDARDS_IMPLEMENTATION_SUMMARY.md](HEDGE_FUND_STANDARDS_IMPLEMENTATION_SUMMARY.md) | Hedge fund standards summary |

---

## UI & Ops

| Doc | Purpose |
|-----|---------|
| [UI_PERCENTILE_REFERENCE_DISTRIBUTIONS.md](UI_PERCENTILE_REFERENCE_DISTRIBUTIONS.md) | **Required** UI labels for percentile types |
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) | Deterministic compute, manifests |
| [VULTR_BACKFILL_GUIDE.md](VULTR_BACKFILL_GUIDE.md) | Ops: backfill on Vultr |
| [SaaS_DB_SCHEMA_v1.md](SaaS_DB_SCHEMA_v1.md) | SaaS DB schema (if used) |

---

## Archive (historical / one-time)

These are completed phases, handoffs, or superseded docs. Move to `docs/archive/` if you want a cleaner root.

| Doc | Why archive |
|-----|-------------|
| PHASE1_SUMMARY.md | Phase 1 complete |
| PHASE2_RECAP.md | Phase 2 complete |
| PHASE7_FINAL_VERIFICATION.md | Phase 7 complete |
| HANDOFF_NEXT_CHAT.md | One-time handoff |
| REFACTOR_OUTLINE.md | Draft; may be superseded |
| REVERSE_ENGINEER_49_SYMBOLS.md | One-time analysis |
| INSTITUTIONAL_RISK_INTELLIGENCE_STANDARD_V1.md | Superseded by V2 |
| HEDGE_FUND_STANDARDS_PLAN.md | Planning; implementation done |
| HEDGE_FUND_STANDARDS_IMPLEMENTATION.md | Detailed plan; summary exists |
| ARCHITECTURE_NAMING.md | Naming conventions (reference or archive) |

---

## Suggested Actions

1. **Keep** all Core Reference, Standards, and UI/Ops docs in `docs/`.
2. **Create** `docs/archive/` and move the Archive list above into it.
3. **Delete** any archive doc you’re sure you won’t need (e.g. HANDOFF_NEXT_CHAT).
4. **Update** this README when adding or removing docs.
