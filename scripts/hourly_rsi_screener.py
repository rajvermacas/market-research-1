#!/usr/bin/env python3
"""Hourly RSI re-ignition screener for NSE equities, in Polars.

The setup: a stock trending strongly on every *higher* timeframe, whose *hourly* momentum
cooled off and is only now turning back up through 60 — so the entry lands as hourly
strength resumes, while the daily/weekly/monthly regime is still intact.

    regime      daily RSI(14) > 60, weekly RSI(14) > 60, monthly RSI(14) > 60
    size        market cap > 5000 crore
    trigger     hourly RSI(14) crossed above 60 on the evaluated bar
                (previous bar <= 60, this bar > 60)
    fresh       EMA(hourly RSI, 21) still < 60 — the smoothed RSI has not reached the
                zone yet, so the cross is an early turn rather than a late continuation
    confirm     EMA(hourly RSI, 21) < hourly RSI — RSI above its own signal line

Note that `confirm` is implied by `trigger` and `fresh` together: the cross forces
RSI > 60 and `fresh` forces the EMA < 60, so EMA < 60 < RSI always holds. It is kept
because the source screen lists it, and --no-implied-confirm drops it; either way the
matched set is identical, which `--explain` demonstrates.

The trigger reads the *last closed* hourly bar by default. Chartink's `[0]` is the live
candle, where a cross can appear and vanish before the hour ends; --live evaluates that
bar instead, and is not a tradable signal on its own.

Prices come from the committed daily and hourly panels; weekly and monthly are resampled
from daily. Market caps are fetched live, since the repository stores prices but not
fundamentals.

Usage:
    python scripts/hourly_rsi_screener.py                     # full NSE, last closed bar
    python scripts/hourly_rsi_screener.py --universe nifty500
    python scripts/hourly_rsi_screener.py --live              # the [0] live-candle reading
    python scripts/hourly_rsi_screener.py --explain           # per-condition funnel
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import polars as pl

# Same directory: reuse the RSI that is already checked against a textbook Wilder loop,
# rather than writing a second implementation that can drift from it.
from screener import CRORE, fetch_market_caps, resample, rsi

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
HOURLY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "hourly" / "**" / "*.parquet")
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CACHE = REPO_ROOT / ".cache" / "screener"

NSE_CLOSE = dt.time(15, 30)


# ------------------------------------------------------------------------- indicators


def ema(column: str, span: int) -> pl.Expr:
    """Standard EMA, alpha = 2/(span+1), matching what charting packages draw."""
    return pl.col(column).ewm_mean(span=span, adjust=False, ignore_nulls=True)


def hourly_features(hourly: pl.DataFrame, period: int, ema_span: int, live: bool) -> pl.DataFrame:
    """Per-symbol RSI, its signal EMA, and the previous bar's RSI, on the evaluated bar."""
    enriched = hourly.sort("symbol", "datetime").with_columns(
        rsi("close", period).over("symbol").alias("rsi_h")
    )
    enriched = enriched.with_columns(
        ema("rsi_h", ema_span).over("symbol").alias("rsi_ema"),
        pl.col("rsi_h").shift(1).over("symbol").alias("rsi_h_prev"),
    )
    # Drop the newest bar unless --live: it is the in-progress candle, and a cross on it
    # can reverse before the hour closes.
    if not live:
        enriched = enriched.filter(
            pl.col("datetime") < pl.col("datetime").max().over("symbol")
        )
    settle = period * 3 + ema_span  # RSI and its EMA both need room to converge
    return (
        enriched.group_by("symbol")
        .agg(
            pl.len().alias("hourly_bars"),
            pl.col("datetime").last().alias("bar"),
            pl.col("close").last().alias("close"),
            pl.col("rsi_h").last().alias("rsi_hourly"),
            pl.col("rsi_h_prev").last().alias("rsi_hourly_prev"),
            pl.col("rsi_ema").last().alias("rsi_hourly_ema"),
        )
        .filter(pl.col("hourly_bars") > settle)
    )


def last_rsi(bars: pl.DataFrame, period: int, label: str, column: str = "date") -> pl.DataFrame:
    """RSI on each symbol's most recent bar, once it has had room to settle."""
    return (
        bars.sort("symbol", column)
        .with_columns(rsi("close", period).over("symbol").alias(label))
        .group_by("symbol")
        .agg(pl.col(label).last(), pl.len().alias("n"))
        .filter(pl.col("n") > period * 3)
        .drop("n")
    )


# ------------------------------------------------------------------------ verification


def verify_indicators(hourly: pl.DataFrame, period: int, ema_span: int, symbols: int = 3) -> None:
    """Check the Polars RSI and EMA against plain loops before anyone trades on them."""
    sample = sorted(hourly["symbol"].unique().to_list())[:symbols]
    worst_rsi = worst_ema = 0.0
    for symbol in sample:
        closes = (
            hourly.filter(pl.col("symbol") == symbol).sort("datetime")["close"].to_list()
        )
        if len(closes) < period * 4:
            continue
        # Wilder's RSI, textbook loop
        gains = losses = 0.0
        for i in range(1, period + 1):
            change = closes[i] - closes[i - 1]
            gains += max(change, 0.0)
            losses += max(-change, 0.0)
        avg_gain, avg_loss = gains / period, losses / period
        reference_rsi = []
        for i in range(period + 1, len(closes)):
            change = closes[i] - closes[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
            reference_rsi.append(
                100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
            )
        # EMA of that RSI, textbook loop
        alpha = 2.0 / (ema_span + 1.0)
        reference_ema, running = [], reference_rsi[0]
        for value in reference_rsi:
            running = alpha * value + (1 - alpha) * running
            reference_ema.append(running)

        computed = (
            hourly.filter(pl.col("symbol") == symbol)
            .sort("datetime")
            .with_columns(rsi("close", period).alias("r"))
            .with_columns(ema("r", ema_span).alias("e"))
        )
        worst_rsi = max(worst_rsi, abs(computed["r"].to_list()[-1] - reference_rsi[-1]))
        worst_ema = max(worst_ema, abs(computed["e"].to_list()[-1] - reference_ema[-1]))

    print(f"  indicator check on {len(sample)} symbols: "
          f"RSI max deviation {worst_rsi:.6f}, EMA-of-RSI max deviation {worst_ema:.4f}")
    if worst_rsi > 1e-6:
        raise SystemExit("hourly RSI disagrees with the reference implementation")
    # The EMA seeds differently (first RSI value vs Polars' own warm-up), so it converges
    # rather than matching to machine precision; a visible gap means a real disagreement.
    if worst_ema > 0.01:
        raise SystemExit("EMA-of-RSI disagrees with the reference implementation")


# ------------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--universe", default="nse_all",
                        help="nse_all (default) or a Nifty index flag, e.g. nifty500")
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--ema-span", type=int, default=21,
                        help="span of the EMA drawn on the hourly RSI (default 21)")
    parser.add_argument("--cross-level", type=float, default=60.0,
                        help="level the hourly RSI must cross above (default 60)")
    parser.add_argument("--htf-min", type=float, default=60.0,
                        help="daily, weekly and monthly RSI must all exceed this (default 60)")
    parser.add_argument("--market-cap-min", type=float, default=5000.0,
                        help="minimum market cap in crore (default 5000)")
    parser.add_argument("--live", action="store_true",
                        help="evaluate the in-progress hourly candle (Chartink's [0])")
    parser.add_argument("--no-implied-confirm", action="store_true",
                        help="drop the redundant EMA < RSI condition")
    parser.add_argument("--skip-market-cap", action="store_true",
                        help="run without the size filter instead of failing when Yahoo refuses")
    parser.add_argument("--explain", action="store_true",
                        help="show how many symbols each condition removes")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if not list(Path(REPO_ROOT / "data" / "ohlcv" / "hourly").glob("year=*/*.parquet")):
        print("No hourly panel found. Build it with:\n"
              "    python scripts/download_market_data.py --interval hourly", file=sys.stderr)
        return 1

    universe = pl.read_parquet(UNIVERSE)
    if args.universe != "nse_all":
        universe = universe.filter(pl.col(f"in_{args.universe}"))
    symbols = universe["symbol"].to_list()

    daily = (
        pl.scan_parquet(DAILY_GLOB, hive_partitioning=True)
        .filter(pl.col("symbol").is_in(symbols))
        .select("symbol", "date", "close", "volume")
        .collect()
    )
    hourly = (
        pl.scan_parquet(HOURLY_GLOB, hive_partitioning=True)
        .filter(pl.col("symbol").is_in(symbols))
        .select("symbol", "datetime", "close")
        .collect()
    )
    print(f"universe {universe.height} symbols | daily {daily.height:,} rows | "
          f"hourly {hourly.height:,} rows")
    verify_indicators(hourly, args.rsi_period, args.ema_span)

    # ---- higher-timeframe regime
    print(f"\n1. Regime: daily, weekly and monthly RSI({args.rsi_period}) > {args.htf_min}")
    passing = last_rsi(daily, args.rsi_period, "rsi_daily")
    for label, every in (("rsi_weekly", "1w"), ("rsi_monthly", "1mo")):
        passing = passing.join(
            last_rsi(resample(daily, every), args.rsi_period, label), on="symbol", how="inner"
        )
    for label in ("rsi_daily", "rsi_weekly", "rsi_monthly"):
        passing = passing.filter(pl.col(label) > args.htf_min)
        if args.explain:
            print(f"   after {label:<12} {passing.height:>5} symbols")
    print(f"   regime intact              {passing.height:>5} symbols")

    # ---- hourly trigger
    bar_kind = "in-progress" if args.live else "last closed"
    print(f"\n2. Hourly trigger on the {bar_kind} bar")
    features = hourly_features(hourly, args.rsi_period, args.ema_span, args.live)
    passing = passing.join(features, on="symbol", how="inner")

    conditions = [
        (f"RSI crossed above {args.cross_level:g}",
         (pl.col("rsi_hourly_prev") <= args.cross_level)
         & (pl.col("rsi_hourly") > args.cross_level)),
        (f"EMA({args.ema_span}) of RSI < {args.cross_level:g}",
         pl.col("rsi_hourly_ema") < args.cross_level),
    ]
    if not args.no_implied_confirm:
        conditions.append(
            (f"EMA({args.ema_span}) of RSI < RSI", pl.col("rsi_hourly_ema") < pl.col("rsi_hourly"))
        )
    for label, condition in conditions:
        before = passing.height
        passing = passing.filter(condition)
        if args.explain:
            print(f"   after {label:<28} {passing.height:>5} symbols "
                  f"(-{before - passing.height})")
    print(f"   hourly trigger             {passing.height:>5} symbols")

    # ---- size
    print(f"\n3. Market cap > {args.market_cap_min:,.0f} crore")
    if args.skip_market_cap:
        passing = passing.with_columns(pl.lit(None, dtype=pl.Float64).alias("market_cap_cr"))
        print("   SKIPPED — the size filter of the screen was not applied")
    elif passing.height:
        caps = fetch_market_caps(passing["symbol"].to_list())
        if caps.is_empty():
            print("   market cap lookup returned nothing — refusing to report a screen with "
                  "a silently missing filter. Re-run later, or pass --skip-market-cap.",
                  file=sys.stderr)
            return 1
        passing = (passing.join(caps, on="symbol", how="inner")
                          .filter(pl.col("market_cap_cr") > args.market_cap_min))
        print(f"   after market cap           {passing.height:>5} symbols")

    result = (
        passing.join(universe.select("symbol", "company_name", "industry"),
                     on="symbol", how="left")
        .sort("market_cap_cr", descending=True, nulls_last=True)
        .select("symbol", "company_name", "industry", "market_cap_cr", "bar", "close",
                "rsi_hourly_prev", "rsi_hourly", "rsi_hourly_ema",
                "rsi_daily", "rsi_weekly", "rsi_monthly")
    )
    as_of = features["bar"].max()
    print(f"\n{'=' * 78}\n{result.height} symbols match "
          f"(hourly bar {as_of}, {bar_kind})\n{'=' * 78}")
    if result.height:
        with pl.Config(tbl_rows=60, tbl_width_chars=210, fmt_str_lengths=28):
            print(result.with_columns(pl.col(pl.Float64).round(1)))

    CACHE.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else CACHE / f"screen_hourly_rsi_{dt.date.today()}.csv"
    result.write_csv(out)
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
