#!/usr/bin/env python3
"""Pullback-in-uptrend screener for NSE equities, in Polars.

The setup: a stock whose *higher* timeframes are strongly trending, whose *daily* RSI has
pulled back into a dip, and whose daily RSI has just turned back up — so the entry lands as
strength resumes rather than after the move has already run.

    structure   monthly RSI(14) > 60  and  weekly RSI(14) > 60   (trend intact)
                close above its 200-day SMA                      (trend guard)
    pullback    daily RSI dipped to <= 45 within the last 15 bars (a real dip happened)
    turn        daily RSI rising for the last 2 bars, and at least
                3 points above its trough, with the trough <= 7 bars ago
    not late    daily RSI still below 65                         (caught early)
    tradable    market cap > 5000 crore, 20-day turnover > 5 crore

Every threshold above is a flag; see --help. `--mode trend` instead reproduces the plain
"daily and weekly and monthly RSI all > 60" screen, which finds already-extended names.

Prices come from the committed daily panel; weekly and monthly are resampled from it.
Market caps are fetched live, since the repository stores prices but not fundamentals.

Usage:
    python scripts/screener.py                          # pullback setup, full NSE
    python scripts/screener.py --universe nifty500
    python scripts/screener.py --pullback-max 40 --max-rsi-now 60
    python scripts/screener.py --mode trend             # the original all-three-above-60 screen
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import polars as pl
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
MANIFEST = REPO_ROOT / "data" / "ohlcv" / "_manifest.json"
CACHE = REPO_ROOT / ".cache" / "screener"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
CRORE = 1e7  # market cap and turnover are quoted in rupees crore


# ------------------------------------------------------------------------- indicators


def rsi(column: str = "close", period: int = 14) -> pl.Expr:
    """Wilder's RSI. Wilder smoothing is an EWMA with alpha = 1/period."""
    delta = pl.col(column).diff()
    gain = pl.when(delta > 0).then(delta).otherwise(0.0)
    loss = pl.when(delta < 0).then(-delta).otherwise(0.0)
    avg_gain = gain.ewm_mean(alpha=1 / period, adjust=False, ignore_nulls=True)
    avg_loss = loss.ewm_mean(alpha=1 / period, adjust=False, ignore_nulls=True)
    # avg_loss == 0 means an unbroken run of up-bars: RSI is 100 by definition.
    return (
        pl.when(avg_loss == 0)
        .then(pl.lit(100.0))
        .otherwise(100.0 - 100.0 / (1.0 + avg_gain / avg_loss))
    )


def resample(daily: pl.DataFrame, every: str) -> pl.DataFrame:
    """Daily bars -> weekly/monthly OHLCV. The in-progress period is kept."""
    return (
        daily.sort("symbol", "date")
        .group_by_dynamic("date", every=every, group_by="symbol")
        .agg(
            pl.col("open").first(), pl.col("high").max(),
            pl.col("low").min(), pl.col("close").last(), pl.col("volume").sum(),
        )
    )


def last_rsi(bars: pl.DataFrame, period: int, label: str) -> pl.DataFrame:
    """RSI on each symbol's most recent bar, once it has had room to settle."""
    return (
        bars.sort("symbol", "date")
        .with_columns(rsi("close", period).over("symbol").alias(label))
        .group_by("symbol")
        .agg(pl.col(label).last(), pl.len().alias("n"))
        .filter(pl.col("n") > period * 3)
        .drop("n")
    )


def daily_features(daily: pl.DataFrame, period: int, lookback: int) -> pl.DataFrame:
    """Per-symbol snapshot of the daily RSI path, plus trend and liquidity context."""
    enriched = daily.sort("symbol", "date").with_columns(
        rsi("close", period).over("symbol").alias("rsi_d"),
        pl.col("close").rolling_mean(200).over("symbol").alias("sma200"),
        (pl.col("close") * pl.col("volume")).rolling_mean(20).over("symbol").alias("turnover"),
    )

    snapshot = (
        enriched.group_by("symbol")
        .agg(
            pl.len().alias("bars"),
            pl.col("date").last().alias("date"),
            pl.col("close").last().alias("close"),
            pl.col("sma200").last().alias("sma200"),
            pl.col("turnover").last().alias("turnover"),
            pl.col("rsi_d").tail(lookback).alias("path"),
        )
        .filter(pl.col("bars") > 250)  # need a 200-day SMA and settled RSI
    )

    steps = pl.col("path").list.diff(null_behavior="drop")
    return snapshot.with_columns(
        pl.col("path").list.last().alias("rsi_now"),
        pl.col("path").list.min().alias("rsi_trough"),
        # bars elapsed since the lowest RSI in the window (0 = the trough is the latest bar)
        (pl.col("path").list.len() - 1 - pl.col("path").list.arg_min()).alias("bars_since_trough"),
        steps.alias("steps"),
        (pl.col("close") / pl.col("sma200") - 1).alias("above_sma200"),
        (pl.col("turnover") / CRORE).alias("turnover_cr"),
    ).with_columns(
        (pl.col("rsi_now") - pl.col("rsi_trough")).alias("rsi_recovery"),
    )


def rising_for(bars: int) -> pl.Expr:
    """True when the daily RSI rose on each of the last `bars` steps."""
    if bars <= 0:
        return pl.lit(True)
    return pl.col("steps").list.tail(bars).list.min() > 0


# ----------------------------------------------------------------------- market caps


def fetch_market_caps(symbols: list[str], batch: int = 100) -> pl.DataFrame:
    """Market cap in crore, from Yahoo's quote endpoint (needs a crumb)."""
    session = requests.Session()
    session.headers.update({"User-Agent": BROWSER_UA, "Accept": "*/*"})
    session.get("https://fc.yahoo.com", timeout=20)
    crumb = session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=20).text.strip()

    tickers = [f"{s}.NS" for s in symbols]
    rows: list[dict] = []
    for offset in range(0, len(tickers), batch):
        chunk = tickers[offset : offset + batch]
        for attempt in range(3):
            try:
                response = session.get(
                    "https://query1.finance.yahoo.com/v7/finance/quote",
                    params={"symbols": ",".join(chunk), "crumb": crumb}, timeout=45,
                )
                response.raise_for_status()
                for quote in response.json()["quoteResponse"]["result"]:
                    cap = quote.get("marketCap")
                    if cap is None:  # reported cap is patchy; shares x price reproduces it exactly
                        shares, price = quote.get("sharesOutstanding"), quote.get("regularMarketPrice")
                        cap = shares * price if shares and price else None
                    if cap:
                        rows.append({"symbol": quote["symbol"].removesuffix(".NS"),
                                     "market_cap_cr": cap / CRORE})
                break
            except Exception as exc:
                if attempt == 2:
                    print(f"    market cap batch failed: {exc}", file=sys.stderr)
                else:
                    time.sleep(2**attempt)
    return pl.DataFrame(rows, schema={"symbol": pl.Utf8, "market_cap_cr": pl.Float64})


# ------------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["pullback", "trend"], default="pullback")
    parser.add_argument("--universe", default="nse_all",
                        help="nse_all (default) or a Nifty index flag, e.g. nifty500")
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--htf-min", type=float, default=60.0,
                        help="weekly and monthly RSI must exceed this (default 60)")
    parser.add_argument("--lookback", type=int, default=15,
                        help="bars searched for the daily RSI trough (default 15)")
    parser.add_argument("--pullback-max", type=float, default=45.0,
                        help="daily RSI must have dipped to at most this (default 45)")
    parser.add_argument("--rising-bars", type=int, default=2,
                        help="consecutive rising daily RSI bars required (default 2)")
    parser.add_argument("--min-recovery", type=float, default=3.0,
                        help="daily RSI must be this far above its trough (default 3)")
    parser.add_argument("--max-bars-since-trough", type=int, default=7)
    parser.add_argument("--max-rsi-now", type=float, default=65.0,
                        help="skip names that have already run (default 65)")
    parser.add_argument("--market-cap-min", type=float, default=5000.0, help="rupees crore")
    parser.add_argument("--turnover-min", type=float, default=5.0,
                        help="20-day average turnover, rupees crore (default 5)")
    parser.add_argument("--require-sma200", action="store_true", default=True)
    parser.add_argument("--no-sma200", dest="require_sma200", action="store_false")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    universe = pl.read_parquet(UNIVERSE)
    if args.universe != "nse_all":
        universe = universe.filter(pl.col(f"in_{args.universe}"))

    daily = (
        pl.scan_parquet(DAILY_GLOB, hive_partitioning=True)
        .select("symbol", "date", "open", "high", "low", "close", "volume")
        .filter(pl.col("symbol").is_in(universe["symbol"].to_list()))
        .collect()
    )
    as_of = daily["date"].max()
    print(f"Universe {args.universe}: {universe.height} symbols | daily panel through {as_of}")
    if MANIFEST.exists():
        entry = json.loads(MANIFEST.read_text())["intervals"]["daily"]
        if entry.get("last_bar_possibly_partial"):
            print(f"  NOTE: the {entry['last']} bar was captured mid-session and is incomplete.")
    print()

    print(f"1. Higher-timeframe trend: weekly and monthly RSI({args.rsi_period}) > {args.htf_min}")
    weekly = last_rsi(resample(daily, "1w"), args.rsi_period, "rsi_weekly")
    monthly = last_rsi(resample(daily, "1mo"), args.rsi_period, "rsi_monthly")
    passing = weekly.join(monthly, on="symbol", how="inner")
    for label in ("rsi_weekly", "rsi_monthly"):
        passing = passing.filter(pl.col(label) > args.htf_min)
        print(f"   after {label:<12} {passing.height:>5} symbols")

    features = daily_features(daily, args.rsi_period, args.lookback)
    passing = passing.join(features, on="symbol", how="inner")

    if args.mode == "trend":
        print(f"\n2. Daily RSI > {args.htf_min} (already-extended screen)")
        passing = passing.filter(pl.col("rsi_now") > args.htf_min)
        print(f"   after rsi_daily   {passing.height:>5} symbols")
    else:
        print(f"\n2. Daily pullback and turn")
        stages = [
            (f"dipped to <= {args.pullback_max}", pl.col("rsi_trough") <= args.pullback_max),
            (f"trough <= {args.max_bars_since_trough} bars ago",
             pl.col("bars_since_trough") <= args.max_bars_since_trough),
            (f"rising {args.rising_bars} bars", rising_for(args.rising_bars)),
            (f"recovered >= {args.min_recovery} pts", pl.col("rsi_recovery") >= args.min_recovery),
            (f"rsi_now < {args.max_rsi_now}", pl.col("rsi_now") < args.max_rsi_now),
        ]
        for label, condition in stages:
            passing = passing.filter(condition)
            print(f"   after {label:<28} {passing.height:>5} symbols")

    if args.require_sma200:
        passing = passing.filter(pl.col("close") > pl.col("sma200"))
        print(f"\n3. Above 200-day SMA          {passing.height:>5} symbols")
    passing = passing.filter(pl.col("turnover_cr") > args.turnover_min)
    print(f"   turnover > {args.turnover_min:g} cr        {passing.height:>5} symbols")

    print(f"\n4. Market cap > {args.market_cap_min:,.0f} crore")
    if passing.height:
        caps = fetch_market_caps(passing["symbol"].to_list())
        passing = (passing.join(caps, on="symbol", how="inner")
                          .filter(pl.col("market_cap_cr") > args.market_cap_min))
    print(f"   after market cap           {passing.height:>5} symbols")

    result = (
        passing.join(universe.select("symbol", "company_name", "industry"), on="symbol", how="left")
        .with_columns((pl.col("above_sma200") * 100).alias("pct_above_200dma"))
        .sort("market_cap_cr", descending=True)
        .select("symbol", "company_name", "market_cap_cr", "close",
                "rsi_now", "rsi_trough", "rsi_recovery", "bars_since_trough",
                "rsi_weekly", "rsi_monthly", "pct_above_200dma", "turnover_cr")
    )

    print(f"\n{'=' * 78}\n{result.height} symbols match the {args.mode} setup (as of {as_of})\n{'=' * 78}")
    if result.height:
        with pl.Config(tbl_rows=60, tbl_width_chars=210, fmt_str_lengths=30):
            print(result.with_columns(pl.col(pl.Float64).round(1)))
    out = Path(args.out) if args.out else CACHE / f"screen_{args.mode}_{dt.date.today()}.csv"
    result.write_csv(out)
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
