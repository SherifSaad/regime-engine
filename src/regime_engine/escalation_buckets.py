from __future__ import annotations

import numpy as np
import pandas as pd

def compute_bucket_from_percentile(esc_pct: float) -> tuple[str, str, dict]:
    """
    Deterministic percentile-based bucket.
    Assumes esc_pct already in [0,1] (rolling percentile transformed).
    """

    if np.isnan(esc_pct):
        return "LOW", "NORMAL_SIZE", {"logic": "nan->low"}

    if esc_pct >= 0.85:
        return "HIGH", "HEDGE_OR_CASH", {"logic": ">=85pct"}
    elif esc_pct >= 0.60:
        return "MED", "REDUCE_40", {"logic": "60-85pct"}
    else:
        return "LOW", "NORMAL_SIZE", {"logic": "<60pct"}
