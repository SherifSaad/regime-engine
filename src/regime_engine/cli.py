import argparse
from regime_engine.loader import load_sample_data
from regime_engine.features import (
    compute_ema,
    compute_returns,
    compute_realized_vol,
)
from regime_engine.metrics import compute_market_bias


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

    market_bias = compute_market_bias(close, fast=20, slow=100)

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
        },
    }

    print(result)


if __name__ == "__main__":
    main()
