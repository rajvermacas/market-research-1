#!/usr/bin/env python3
"""Sanity-check the downloaded Parquet panels with Polars.

Reports schema, coverage and the data-quality issues that survive from the upstream source,
so a strategy author knows what they are backtesting on. Also cross-checks the weekly and
monthly panels against a resample of the daily panel, which catches misaligned or stale
bars that a single-panel check cannot see.

Exits non-zero only on structural problems (missing files, duplicate keys, null values,
an oversized partition, a panel whose symbols largely miss the universe). Upstream oddities
— Yahoo dropping a session for some tickers, a handful of bad ticks, a name delisted since
the panel was built — are reported, not treated as failures.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
OHLCV_DIR = REPO_ROOT / "data" / "ohlcv"
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
MANIFEST = OHLCV_DIR / "_manifest.json"

INTERVALS = ("hourly", "daily", "weekly", "monthly")
RESAMPLE = {"weekly": "1w", "monthly": "1mo"}
SAMPLE_SYMBOLS = 40


def load(interval: str) -> pl.DataFrame | None:
    directory = OHLCV_DIR / interval
    if not directory.exists():
        return None
    return pl.read_parquet(directory / "**" / "*.parquet", hive_partitioning=True)


def time_column(frame: pl.DataFrame) -> str:
    return "datetime" if "datetime" in frame.columns else "date"


def check_interval(name: str, prices: pl.DataFrame, universe: pl.DataFrame) -> list[str]:
    failures: list[str] = []
    column = time_column(prices)
    files = sorted((OHLCV_DIR / name).glob("year=*/data.parquet"))
    size_mb = sum(f.stat().st_size for f in files) / 1024**2
    largest = max((f.stat().st_size for f in files), default=0) / 1024**2

    print(f"\n=== {name} ===")
    print(f"  rows              {prices.height:,}")
    print(f"  symbols           {prices['symbol'].n_unique():,}")
    print(f"  range             {prices[column].min()} -> {prices[column].max()}")
    print(f"  distinct bars     {prices[column].n_unique():,}")
    print(f"  files             {len(files)} year partitions, {size_mb:.1f} MB "
          f"(largest {largest:.1f} MB)")
    if largest >= 100:
        failures.append(f"{name}: a partition exceeds GitHub's 100 MB file limit")

    lengths = prices.group_by("symbol").agg(pl.len().alias("bars"))["bars"]
    print(f"  bars per symbol   median {int(lengths.median()):,}, "
          f"min {int(lengths.min()):,}, max {int(lengths.max()):,}")

    nulls = {k: v for k, v in prices.null_count().to_dicts()[0].items() if v}
    print(f"  nulls                       {nulls or 'none'}")
    if nulls:
        failures.append(f"{name}: null values present")

    dupes = prices.height - prices.select("symbol", column).unique().height
    print(f"  duplicate keys              {dupes}")
    if dupes:
        failures.append(f"{name}: duplicate (symbol, {column}) keys")

    # A price panel outlives the listing file: a symbol suspended or delisted since the
    # panel was built keeps its history but loses its universe row. That churn is a handful
    # of names. A large share instead means a parsing bug or the wrong exchange, so fail on
    # the share rather than on the first stale ticker.
    orphans = sorted(set(prices["symbol"].unique()) - set(universe["symbol"]))
    share = len(orphans) / prices["symbol"].n_unique()
    detail = f" (no longer listed: {', '.join(orphans[:5])})" if orphans else ""
    print(f"  symbols outside universe    {len(orphans)} ({share:.2%}){detail}")
    if share > 0.01:
        failures.append(
            f"{name}: {len(orphans)} symbols ({share:.1%}) are not in the universe file — "
            f"too many to be delisting churn: {orphans[:5]}"
        )

    if "adj_close" in prices.columns:
        identical = prices.filter(pl.col("adj_close") == pl.col("close")).height
        print(f"  adj_close == close          {identical / prices.height:.1%} of bars")

    inconsistent = prices.filter(
        (pl.col("high") < pl.col("low"))
        | (pl.col("close") > pl.col("high"))
        | (pl.col("close") < pl.col("low"))
        | (pl.col("open") > pl.col("high"))
        | (pl.col("open") < pl.col("low"))
    )
    print(f"  OHLC ordering violations    {inconsistent.height:,} "
          f"({inconsistent.height / prices.height:.3%}, "
          f"{inconsistent['symbol'].n_unique()} symbols)")

    non_positive = prices.filter(pl.col("close") <= 0).height
    zero_volume = prices.filter(pl.col("volume") == 0).height
    print(f"  non-positive close          {non_positive:,}")
    print(f"  zero-volume bars            {zero_volume:,} ({zero_volume / prices.height:.2%})")

    # A period where many *already-listed* symbols have no bar is an upstream gap rather
    # than a market holiday (a holiday has no rows at all) or a young listing.
    span = prices.group_by("symbol").agg(
        pl.col(column).min().alias("from"), pl.col(column).max().alias("to")
    )
    expected = (
        prices.select(pl.col(column).unique().sort())
        .join(span, how="cross")
        .filter(pl.col(column).is_between(pl.col("from"), pl.col("to")))
        .group_by(column)
        .agg(pl.len().alias("expected"))
    )
    per_bar = (
        prices.group_by(column)
        .agg(pl.len().alias("present"))
        .join(expected, on=column, how="left")
        .with_columns((1 - pl.col("present") / pl.col("expected")).alias("missing_share"))
    )
    sparse = per_bar.filter(pl.col("missing_share") > 0.10).sort(column)
    print(f"  periods missing >10% of listed symbols  {sparse.height}")
    if sparse.height:
        for row in sparse.sort("missing_share", descending=True).head(3).iter_rows(named=True):
            print(f"    {row[column]}  {row['present']}/{row['expected']} "
                  f"({row['missing_share']:.0%} missing)")
        print(f"    most recent: {sparse[column].max()}")

    return failures


def cross_check(name: str, coarse: pl.DataFrame, daily: pl.DataFrame, every: str) -> None:
    """Compare the downloaded weekly/monthly bars against a resample of the daily panel."""
    symbols = sorted(daily["symbol"].unique().to_list())[:SAMPLE_SYMBOLS]
    resampled = (
        daily.filter(pl.col("symbol").is_in(symbols))
        .sort("date")
        .group_by_dynamic("date", every=every, group_by="symbol", label="left")
        .agg(
            pl.col("open").first().alias("r_open"),
            pl.col("high").max().alias("r_high"),
            pl.col("low").min().alias("r_low"),
            pl.col("close").last().alias("r_close"),
        )
    )
    # Yahoo stamps a weekly bar on the week's first *traded* day, so align on period start.
    joined = (
        coarse.filter(pl.col("symbol").is_in(symbols))
        .with_columns(pl.col("date").dt.truncate(every).alias("period"))
        .join(
            resampled.with_columns(pl.col("date").dt.truncate(every).alias("period")),
            on=["symbol", "period"],
            how="inner",
        )
    )
    if joined.is_empty():
        print(f"  {name} vs daily resample: no overlap to compare")
        return
    tol = 0.01  # 1% — daily and coarse bars can disagree slightly on thin, stale symbols
    mismatch = joined.filter(
        ((pl.col("close") - pl.col("r_close")).abs() / pl.col("r_close") > tol)
        | ((pl.col("high") - pl.col("r_high")).abs() / pl.col("r_high") > tol)
    )
    print(f"  {name} vs daily resample ({len(symbols)} symbols): "
          f"{joined.height:,} bars compared, {mismatch.height:,} disagree by >1% "
          f"({mismatch.height / joined.height:.2%})")


def main() -> int:
    if not UNIVERSE.exists():
        print(f"FAIL missing {UNIVERSE.relative_to(REPO_ROOT)}")
        return 1
    universe = pl.read_parquet(UNIVERSE)
    print(f"universe: {universe.height:,} NSE symbols "
          f"({universe['series'].value_counts().sort('series').to_dicts()})")

    failures: list[str] = []
    panels: dict[str, pl.DataFrame] = {}
    for name in INTERVALS:
        prices = load(name)
        if prices is None:
            print(f"\n=== {name} ===\n  not downloaded")
            continue
        panels[name] = prices
        failures += check_interval(name, prices, universe)

    if "daily" in panels:
        print("\n=== cross-interval consistency ===")
        for name, every in RESAMPLE.items():
            if name in panels:
                cross_check(name, panels[name], panels["daily"], every)

    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())
        print("\n=== manifest ===")
        print(f"  generated {manifest.get('generated_at_ist')} | universe "
              f"{manifest.get('universe')} ({manifest.get('universe_size')} symbols)")
        for name, entry in manifest.get("intervals", {}).items():
            flags = []
            if entry.get("last_bar_possibly_partial"):
                flags.append(f"last bar {entry['last']} is PARTIAL")
            if entry.get("symbols_unavailable_on_yahoo"):
                flags.append(f"{len(entry['symbols_unavailable_on_yahoo'])} symbols unavailable")
            print(f"  {name:<8} {entry['rows']:>10,} rows  {entry['first']} -> {entry['last']}"
                  + (f"  [{'; '.join(flags)}]" if flags else ""))

    print()
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("OK  structural checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
