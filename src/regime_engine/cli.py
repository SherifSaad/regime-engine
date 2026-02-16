import argparse
from regime_engine.loader import load_sample_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the regime engine (offline).")
    parser.add_argument("--symbol", required=True, help="Asset symbol, e.g., SPY")
    args = parser.parse_args()

    df = load_sample_data(args.symbol, n_bars=10)
    print(df.head().to_string())


if __name__ == "__main__":
    main()
