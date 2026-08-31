#!/usr/bin/env python3
"""Sweep the portfolio slot count on one feature build.

`--slots` turned out to carry most of the headline: on the 2.9-year full-NSE panel the
CAGR runs from +47.9% at three slots to +8.5% at forty, crossing the benchmark at about
twelve. That makes it the parameter most worth measuring rather than defaulting, and it is
cheap to measure properly — a trade's exit depends only on its own entry bar and stop, not
on how many slots exist, so the forward walk runs once and only the portfolio pass repeats.

Deployment is reported alongside return, because a book with three slots sits in cash most
of the time while the benchmark is fully invested. Comparing them without that column
mistakes lower exposure for lower risk.

Usage:
    python scripts/rsi_slots_sweep.py --hourly-dir 60minute_kite --daily-from-hourly \
        --skip-market-cap --reward-risk 10
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

from screener import rsi, resample, fetch_market_caps
from hourly_rsi_screener import ema
from rsi_backtest import (
    attach_htf, attach_market_cap, elapsed_years, find_trades, performance, simulate,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CAP_CACHE = REPO_ROOT / ".cache" / "screener" / "market_caps.csv"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--universe", default="nifty500")
    p.add_argument("--hourly-dir", default="60minute_kite")
    p.add_argument("--daily-from-hourly", action="store_true")
    p.add_argument("--skip-market-cap", action="store_true")
    p.add_argument("--min-close-pos", type=float, default=0.70)
    p.add_argument("--reward-risk", type=float, default=10.0)
    p.add_argument("--rsi-period", type=int, default=14)
    p.add_argument("--ema-span", type=int, default=21)
    p.add_argument("--ema-max", type=float, default=53.0)
    p.add_argument("--cost-bps", type=float, default=10.0)
    p.add_argument("--slots", type=int, nargs="+", default=[3, 5, 10, 15, 20, 30, 40])
    args = p.parse_args()
    cost = args.cost_bps / 10_000

    universe = pl.read_parquet(UNIVERSE)
    if args.universe != "nse_all":
        universe = universe.filter(pl.col(f"in_{args.universe}"))
    symbols = universe["symbol"].to_list()

    hourly = (pl.scan_parquet(str(REPO_ROOT / "data" / "ohlcv" / args.hourly_dir / "**" / "*.parquet"),
                              hive_partitioning=True)
              .filter(pl.col("symbol").is_in(symbols))
              .select("symbol", "datetime", "open", "high", "low", "close").collect())
    if args.daily_from_hourly:
        daily = (hourly.with_columns(pl.col("datetime").dt.date().alias("date"))
                 .group_by("symbol", "date")
                 .agg(pl.col("open").first(), pl.col("high").max(),
                      pl.col("low").min(), pl.col("close").last())
                 .with_columns(pl.lit(0, dtype=pl.Int64).alias("volume")).sort("symbol", "date"))
    else:
        daily = (pl.scan_parquet(str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet"),
                                 hive_partitioning=True)
                 .filter(pl.col("symbol").is_in(symbols))
                 .select("symbol", "date", "open", "high", "low", "close", "volume").collect())
    print(f"universe {universe.height} | hourly {hourly.height:,} rows from {args.hourly_dir}")

    frame = hourly.sort("symbol", "datetime").with_columns(
        rsi("close", args.rsi_period).over("symbol").alias("rsi_h"))
    frame = frame.with_columns(
        ema("rsi_h", args.ema_span).over("symbol").alias("rsi_ema"),
        pl.col("rsi_h").shift(1).over("symbol").alias("rsi_prev"))
    settle = args.rsi_period * 3 + args.ema_span
    frame = (frame.with_columns(pl.int_range(pl.len()).over("symbol").alias("_seen"))
             .filter(pl.col("_seen") >= settle).drop("_seen"))
    frame = attach_htf(frame, daily, args.rsi_period)
    if args.skip_market_cap:
        frame = frame.with_columns(pl.lit(1e9).alias("cap_cr"))
    else:
        frame = attach_market_cap(frame, daily, pl.read_csv(CAP_CACHE))
    rng = pl.col("high") - pl.col("low")
    frame = frame.with_columns(
        ((pl.col("close") - pl.col("low"))
         / pl.when(rng > 0).then(rng).otherwise(None)).alias("close_pos"))
    frame = frame.with_columns(
        ((pl.col("rsi_prev") <= 60) & (pl.col("rsi_h") > 60)
         & (pl.col("rsi_ema") < args.ema_max)
         & (pl.col("rsi_daily") > 60) & (pl.col("rsi_weekly") > 60)
         & (pl.col("rsi_monthly") > 60) & (pl.col("cap_cr") > 5000)
         & (pl.col("close_pos") >= args.min_close_pos)).fill_null(False).alias("signal")
    ).sort("symbol", "datetime")
    print(f"  {int(frame['signal'].sum()):,} entry signals")

    sig_symbols = frame.filter(pl.col("signal"))["symbol"].unique().to_list()
    prices = (hourly.filter(pl.col("symbol").is_in(sig_symbols))
              .select("symbol", "datetime", "close")
              .pivot(on="symbol", index="datetime", values="close").sort("datetime"))
    prices = prices.with_columns(
        [pl.col(c).forward_fill().backward_fill() for c in prices.columns if c != "datetime"])
    grid = prices["datetime"].dt.epoch("us").to_numpy()
    years = elapsed_years(grid)
    mid = prices["datetime"][prices.height // 2].timestamp() * 1_000_000

    trades = find_trades(frame, cost, args.reward_risk)          # slot-independent
    print(f"  {trades.height:,} trades resolved once at 1:{args.reward_risk:g}, "
          f"{years:.2f} years\n")

    # control, on the full universe
    wide = (hourly.select("symbol", "datetime", "close")
            .pivot(on="symbol", index="datetime", values="close").sort("datetime"))
    wide = wide.with_columns([pl.col(c).forward_fill() for c in wide.columns if c != "datetime"])
    cols = [c for c in wide.columns if c != "datetime"]
    m = wide.select(cols).to_numpy()
    listed = ~np.isnan(m[0])
    norm = m[:, listed] / m[0, listed]
    bench_cagr, bench_dd = performance(np.nanmean(norm, axis=1), years)

    matrix = prices.select([c for c in prices.columns if c != "datetime"]).to_numpy()
    print(f"{'slots':<7}{'taken':>7}{'%sig':>6}{'avg open':>10}{'%deployed':>11}"
          f"{'CAGR%':>8}{'maxDD%':>9}{'ret/DD':>8}{'h1':>8}{'h2':>8}")
    for slots in args.slots:
        equity, taken, skipped, _, _, _ = simulate(trades, prices, slots, cost)
        cagr, dd = performance(equity, years)
        # deployment: rebuild the open-position count over the grid
        entry_i = np.searchsorted(grid, trades["entry_time"].to_numpy())
        exit_i = np.searchsorted(grid, trades["exit_time"].to_numpy())
        open_ct = np.zeros(len(grid))
        cash_frac = []
        cur, held = 0, []
        for t in range(len(grid)):
            held = [e for e in held if e > t]
            cur = len(held)
            for k in np.flatnonzero(entry_i == t):
                if cur < slots:
                    held.append(exit_i[k]); cur += 1
            open_ct[t] = cur
        dep = open_ct.mean() / slots
        c = trades.filter(pl.col("outcome") != "open")
        h1 = c.filter(pl.col("entry_time") < mid)["ret"].mean() * 100
        h2 = c.filter(pl.col("entry_time") >= mid)["ret"].mean() * 100
        print(f"{slots:<7}{taken:>7}{taken/trades.height*100:>5.0f}%{open_ct.mean():>10.1f}"
              f"{dep*100:>10.0f}%{cagr*100:>8.2f}{dd*100:>9.2f}"
              f"{abs(cagr/dd):>8.2f}{h1:>8.3f}{h2:>8.3f}")
    print(f"\nCONTROL equal-weight buy-and-hold ({int(listed.sum())} symbols, fully invested): "
          f"{bench_cagr*100:+.2f}% / {bench_dd*100:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
