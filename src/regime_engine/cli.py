import argparse
from regime_engine.loader import load_sample_data
from regime_engine.features import (
    compute_ema,
    compute_returns,
    compute_realized_vol,
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

    print("Latest Values:")
    print({
        "price": close.iloc[-1],
        "ema_fast": ema_fast.iloc[-1],
        "ema_slow": ema_slow.iloc[-1],
        "realized_vol": rv.iloc[-1],
    })


if __name__ == "__main__":
    main()
