import argparse
from regime_engine.loader import load_sample_data
from regime_engine.features import (
    compute_ema,
    compute_returns,
    compute_realized_vol,
)
from regime_engine.metrics import (
    compute_market_bias,
    compute_risk_level,
    compute_breakout_probability,
    compute_downside_shock_risk,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the regime engine (offline).")
    parser.add_argument("--symbol", required=True, help="Asset symbol, e.g., SPY")
    args = parser.parse_args()

    df = load_sample_data(args.symbol)
    close = df["close"]

    ema_fast = compute_ema(close, 20)
    ema_slow = compute_ema(close, 100)
    returns = compute_returns(close)
    rv = compute_realized_vol(returns)

    market_bias = compute_market_bias(df, n_f=20, n_s=100, alpha=0.7, beta=0.3)
    risk_level = compute_risk_level(df, n_f=20, n_s=100, peak_window=252)

    bp_up, bp_dn = compute_breakout_probability(
        df,
        mb=market_bias,
        rl=risk_level,
        n_f=20,
        atr_short_n=10,
        atr_long_n=50,
        level_lookback=50,
    )

    dsr = compute_downside_shock_risk(
        df,
        mb=market_bias,
        rl=risk_level,
        n_f=20,
        n_s=100,
        H=60,
        m=2.5,
    )

    asof = df.index[-1].date().isoformat()

    result = {
        "symbol": args.symbol.upper(),
        "asof": asof,
        "metrics": {
            "price": float(close.iloc[-1]),
            "ema_fast": float(ema_fast.iloc[-1]),
            "ema_slow": float(ema_slow.iloc[-1]),
            "realized_vol": float(rv.iloc[-1]),
            "market_bias": float(market_bias),
            "risk_level": float(risk_level),
            "breakout_up": float(bp_up),
            "breakout_down": float(bp_dn),
            "downside_shock_risk": float(dsr),
        },
    }

    print(result)


if __name__ == "__main__":
    main()
