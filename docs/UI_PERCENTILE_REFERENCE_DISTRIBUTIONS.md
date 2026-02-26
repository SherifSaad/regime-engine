# UI: Percentile Reference Distributions

**Purpose:** When displaying escalation percentiles in the UI, label each series by its **reference distribution**. Without explicit labels, users will misinterpret what a percentile means.

---

## Required Labels

| Percentile | Reference Distribution | Label in UI |
|------------|-------------------------|-------------|
| `esc_pctl_expanding` | **Expanding (all history)** | e.g. "Expanding (full history)" |
| `esc_pctl_252`, `esc_pctl_504`, `esc_pctl_1260`, `esc_pctl_2520` | **Rolling** (trailing 252/504/1260/2520 bars) | e.g. "Rolling 252" / "Rolling 504" / etc. |
| `esc_pctl_era` | **Era-conditioned** (raw within-era) | e.g. "Era-conditioned (raw)" |
| `esc_pctl_era_adj` | **Production** (era + confidence shrinkage) | e.g. "Era-adjusted (production)" |
| `esc_pctl_era_confidence` | — | Show with era: opacity/color/tooltip (min(1, bars_in_era/CONF_TARGET)) |

---

## Why This Matters

These percentiles are **not comparable**—they use different reference distributions:

- **Expanding:** Rank vs. all prior bars. Production signal.
- **Rolling:** Rank vs. trailing N bars. Different windows = different distributions.
- **Era-conditioned:** Rank vs. bars within the same structural era only. Resets at era boundaries; min 252 bars per era before output.

If the UI does not label them explicitly, users will assume they are comparable and create interpretive confusion.

---

## Implementation Checklist

- [ ] Chart legends / axis labels include reference distribution
- [ ] Toggle/selector labels: "Expanding (all history)", "Rolling 252", "Rolling 504", etc., "Era-conditioned (structural segmentation)"
- [ ] Tooltip or help text explains the difference when hovering/clicking
