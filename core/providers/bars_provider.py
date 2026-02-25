# core/providers/bars_provider.py
from pathlib import Path
import polars as pl
from typing import Optional
import logging

from core.timeframes import normalize_timeframe

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # core/providers/ → root
ASSETS_ROOT = PROJECT_ROOT / "data" / "assets"


def get_bars_path(symbol: str, timeframe: str) -> Path:
    """Canonical path for bars Parquet: data/assets/{symbol}/bars/{timeframe}/"""
    return ASSETS_ROOT / symbol / "bars" / normalize_timeframe(timeframe)


class BarsProvider:
    """Abstract data access layer for bars – compute never touches files directly.
    Bars live in data/assets/{symbol}/bars/{timeframe}/ (one folder per asset).
    """

    ROOT = ASSETS_ROOT  # data/assets – bars are under {symbol}/bars/{tf}/

    @staticmethod
    def _ensure_dir(path: Path) -> None:
        """Create directory if it doesn't exist."""
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_bars(
        symbol: str,
        timeframe: str,
        manifest_hash: Optional[str] = None,  # future: filter by manifest
        upto_ts: Optional[str] = None,  # e.g. "2026-02-24T00:00:00"
    ) -> pl.LazyFrame:
        """
        Returns a Polars LazyFrame of bars for the given symbol/timeframe.
        Timeframe is normalized (e.g. 1d → 1day) for consistent folder names.
        """
        tf = normalize_timeframe(timeframe)
        path = get_bars_path(symbol, tf)

        if not path.exists():
            logger.warning(f"No bars directory found for {symbol}/{timeframe}")
            return pl.LazyFrame(
                schema={
                    "ts": pl.Datetime,
                    "open": pl.Float64,
                    "high": pl.Float64,
                    "low": pl.Float64,
                    "close": pl.Float64,
                    "volume": pl.Int64,
                }
            )

        # Scan all partitioned Parquet files recursively
        lf = pl.scan_parquet(path / "**/*.parquet")

        # Apply upto_ts filter if provided
        if upto_ts:
            lf = lf.filter(pl.col("ts") <= pl.lit(upto_ts).cast(pl.Datetime))

        # Future: apply manifest_hash filter if needed
        if manifest_hash:
            pass  # Placeholder for manifest-based selection logic

        return lf

    @staticmethod
    def write_bars(symbol: str, timeframe: str, df: pl.DataFrame) -> None:
        """
        Append-only write with deduplication.
        Partitions by date (YYYY-MM-DD) for fast scans.
        Timeframe is normalized (e.g. 1d → 1day) for consistent folder names.
        """
        if df.is_empty():
            logger.info("No new bars to write")
            return

        tf = normalize_timeframe(timeframe)
        path = get_bars_path(symbol, tf)
        BarsProvider._ensure_dir(path)

        # Ensure required schema
        required_schema = {
            "ts": pl.Datetime,
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Int64,
        }
        df = df.select(required_schema.keys()).cast(required_schema)

        # Deduplicate against existing data (5-bar overlap tolerance)
        existing_files = list(path.glob("**/*.parquet"))
        if existing_files:
            existing_lf = pl.scan_parquet(path / "**/*.parquet").select(
                "ts", "open", "high", "low", "close", "volume"
            )
            combined = pl.concat([existing_lf, df.lazy()]).unique(subset=["ts"], keep="last")
            df = combined.collect()  # materialize for write
        else:
            df = df  # already DataFrame

        # Add partition column
        df = df.with_columns(pl.col("ts").dt.date().alias("date"))

        # Write partitioned
        df.write_parquet(
            path,
            partition_by="date",
            compression="zstd",
        )

        logger.info(f"Wrote {len(df)} bars to {path}")
