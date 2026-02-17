import numpy as np
import pandas as pd

def hysteresis_high_state(
    esc_pct: pd.Series,
    enter: float = 0.90,
    exit: float = 0.75,
) -> pd.Series:
    """
    Deterministic hysteresis state machine.
    Returns a boolean Series: True if in HIGH state.
    No lookahead. NaNs -> False until enough history exists.
    """
    x = esc_pct.astype(float).values
    out = np.zeros(len(x), dtype=bool)

    high = False
    for i in range(len(x)):
        xi = x[i]
        if np.isnan(xi):
            out[i] = False
            continue

        if not high and xi >= enter:
            high = True
        elif high and xi <= exit:
            high = False

        out[i] = high

    return pd.Series(out, index=esc_pct.index)

def bucket_from_high_state(
    is_high: pd.Series,
    default_bucket: str = "LOW"
) -> pd.Series:
    """
    Map boolean high state to buckets.
    HIGH if is_high True else default_bucket (LOW).
    """
    return is_high.map(lambda v: "HIGH" if bool(v) else default_bucket).astype(str)
