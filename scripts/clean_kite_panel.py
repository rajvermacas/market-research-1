#!/usr/bin/env python3
"""Repair the Kite intraday panel: token reuse, zero prints, and adjustment breaks.

Kite reuses instrument tokens. A symbol listed in 2019 can carry 2015 bars at a price
that belonged to whatever security held the token before it — AFFLE trades at Rs 3.45 in
2015 with real volume and lists at Rs 745 in 2019, which reads as a 469x return and
poisons any equal-weight benchmark built from the panel.

Listing dates alone cannot decide this, because NSE's file records a *re*-listing date for
some old names (NESTLEIND 2023, FORCEMOT 2024) whose pre-date history is genuine. So each
candidate is checked against the Yahoo daily panel, which is independently sourced: if
Yahoo also has bars before the listing date, the history is real and kept; if Yahoo starts
at the listing date, the Kite bars before it are another instrument and are dropped.

Also nulls non-positive prints (1,677 bars, which read as a -100% move and trip any
outlier detector) and reports symbols whose Kite total return disagrees with Yahoo's by
more than a quarter — those carry a mid-series adjustment break and cannot be trusted.

Usage:
    python scripts/clean_kite_panel.py --in 60minute_kite --out 60minute_kite_clean
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
OHLCV = REPO_ROOT / "data" / "ohlcv"
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="src", default="60minute_kite")
    ap.add_argument("--out", dest="dst", default="60minute_kite_clean")
    args = ap.parse_args()

    panel = (pl.scan_parquet(str(OHLCV / args.src / "**" / "*.parquet"), hive_partitioning=True)
             .select("symbol", "datetime", "open", "high", "low", "close", "volume")
             .collect().sort("symbol", "datetime"))
    start = panel["datetime"].min().date()
    print(f"in : {panel.height:,} bars, {panel['symbol'].n_unique()} symbols, from {start}")

    # --- 1. non-positive prints -----------------------------------------------------
    bad = panel.filter(pl.col("close") <= 0).height
    panel = panel.filter(pl.col("close") > 0)
    print(f"  dropped {bad:,} non-positive prints")

    # --- 2. token reuse, adjudicated against Yahoo ------------------------------------
    universe = pl.read_parquet(UNIVERSE).select("symbol", "listing_date")
    late = universe.filter(pl.col("listing_date") > start)
    yahoo = (pl.scan_parquet(str(OHLCV / "daily" / "**" / "*.parquet"), hive_partitioning=True)
             .filter(pl.col("symbol").is_in(late["symbol"].to_list()))
             .group_by("symbol").agg(pl.col("date").min().alias("yahoo_first")).collect())
    check = late.join(yahoo, on="symbol", how="left")

    reuse, relisted = [], []
    for row in check.iter_rows(named=True):
        first = row["yahoo_first"]
        # Yahoo corroborates pre-listing history -> a re-listing, keep it.
        if first is not None and first < row["listing_date"] - dt.timedelta(days=30):
            relisted.append(row["symbol"])
        else:
            reuse.append((row["symbol"], row["listing_date"]))

    before = panel.height
    if reuse:
        cuts = pl.DataFrame({"symbol": [s for s, _ in reuse],
                             "listed": [d for _, d in reuse]})
        panel = (panel.join(cuts, on="symbol", how="left")
                 .filter(pl.col("listed").is_null()
                         | (pl.col("datetime").dt.date() >= pl.col("listed")))
                 .drop("listed"))
    print(f"  token reuse: cut {before - panel.height:,} pre-listing bars from "
          f"{len(reuse)} symbols; kept {len(relisted)} re-listed names with real history")
    if relisted:
        print(f"    kept as genuine re-listings: {', '.join(sorted(relisted)[:6])}")

    # --- 3. adjustment breaks, reported not silently patched --------------------------
    ykite = (pl.scan_parquet(str(OHLCV / "daily" / "**" / "*.parquet"), hive_partitioning=True)
             .select("symbol", "date", "close").collect())
    span = panel.group_by("symbol").agg(
        pl.col("datetime").dt.date().min().alias("a"), pl.col("datetime").dt.date().max().alias("b"),
        (pl.col("close").last() / pl.col("close").first()).alias("kite_ret"))
    yr = (ykite.join(span, on="symbol", how="inner")
          .filter(pl.col("date").is_between(pl.col("a"), pl.col("b")))
          .group_by("symbol").agg((pl.col("close").last() / pl.col("close").first()).alias("y_ret")))
    cmp = (span.join(yr, on="symbol", how="inner")
           .with_columns((pl.col("kite_ret") / pl.col("y_ret")).alias("ratio"))
           .filter((pl.col("ratio") > 1.25) | (pl.col("ratio") < 0.80)).sort("ratio"))
    print(f"  {cmp.height} symbols disagree with Yahoo's total return by >25% "
          f"(mid-series adjustment break — reported, not patched):")
    for r in cmp.head(8).iter_rows(named=True):
        print(f"    {r['symbol']:<12} kite {r['kite_ret']:>8.2f}x  yahoo {r['y_ret']:>8.2f}x"
              f"  ratio {r['ratio']:.2f}")

    out = OHLCV / args.dst
    total = 0
    for (year,), part in panel.group_by(pl.col("datetime").dt.year(), maintain_order=True):
        t = out / f"year={year}" / "data.parquet"
        t.parent.mkdir(parents=True, exist_ok=True)
        part.write_parquet(t, compression="zstd", statistics=True)
        total += t.stat().st_size
    print(f"\nout: {panel.height:,} bars, {panel['symbol'].n_unique()} symbols "
          f"-> data/ohlcv/{args.dst}/ ({total / 1024**2:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
