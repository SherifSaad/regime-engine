import argparse

def main() -> None:
    parser = argparse.ArgumentParser(description="Run the regime engine (offline placeholder).")
    parser.add_argument("--symbol", required=True, help="Asset symbol, e.g., SPY")
    args = parser.parse_args()

    # Placeholder output for now (we'll wire loader/features/metrics next)
    print({"symbol": args.symbol, "status": "ok", "message": "Skeleton ready. Next: loader + features."})

if __name__ == "__main__":
    main()
