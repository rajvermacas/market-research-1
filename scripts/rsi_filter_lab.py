#!/usr/bin/env python3
"""Measure candidate entry filters for the hourly RSI setup, one feature build per run.

The backtest says the setup has a real gross edge at 1:5 (+13.6% CAGR before costs)
that turnover then eats, and that signals outnumber portfolio slots four to one. So the
useful filter is one that *removes* trades while raising the edge on those that remain —
it improves selection and cuts cost drag at the same time. This script measures each
candidate's marginal effect against the unfiltered base, holding everything else fixed.

Thresholds are quoted against the distribution they sit in (printed first), rather than
picked because they sounded reasonable.

Every filter is also scored on the first and second half of the window separately. With
~2.9 years of data and a dozen candidates, the best in-sample number is partly luck; a
filter that only works in one half is noise, not an edge.

Usage:
    python scripts/rsi_filter_lab.py
    python scripts/rsi_filter_lab.py --reward-risk 5 --slots 10
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

from screener import rsi, resample, fetch_market_caps
from hourly_rsi_screener import ema
from rsi_backtest import (
    BARS_PER_YEAR, attach_htf, attach_market_cap, find_trades, performance, simulate,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
HOURLY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "hourly" / "**" / "*.parquet")
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CAP_CACHE = REPO_ROOT / ".cache" / "screener" / "market_caps.csv"


def candle_features(frame: pl.DataFrame) -> pl.DataFrame:
    """Shape, participation, location and timing of the signal candle."""
    rng = (pl.col("high") - pl.col("low"))
    safe = pl.when(rng > 0).then(rng).otherwise(None)
    return frame.with_columns(
        ((pl.col("close") - pl.col("low")) / safe).alias("close_pos"),
        ((pl.col("close") - pl.col("open")).abs() / safe).alias("body"),
        ((pl.col("high") - pl.col("close")) / safe).alias("upper_wick"),
        ((pl.col("close") - pl.col("low")) / pl.col("close")).alias("risk_pct"),
        (pl.col("rsi_h") - pl.col("rsi_prev")).alias("rsi_jump"),
        (pl.col("volume")
         / pl.col("volume").rolling_mean(20).over("symbol")).alias("vol_ratio"),
        ((pl.col("close") * pl.col("volume")).rolling_mean(20).over("symbol")
         / 1e7).alias("turnover_cr"),
        (pl.col("close") / pl.col("close").rolling_mean(50).over("symbol") - 1)
        .alias("above_h50"),
        pl.col("datetime").dt.hour().alias("hour"),
        (pl.col("rsi_ema") > pl.col("rsi_ema").shift(1).over("symbol")).alias("ema_rising"),
        # a repeat cross inside 20 bars is the same chop firing twice
        (pl.col("signal_raw").cast(pl.Int32).rolling_sum(20).over("symbol").shift(1))
        .alias("recent_signals"),
    )


def breadth_by_date(daily: pl.DataFrame) -> pl.DataFrame:
    """Share of the universe trading above its own 20-day SMA — a market regime gauge."""
    return (
        daily.sort("symbol", "date")
        .with_columns(pl.col("close").rolling_mean(20).over("symbol").alias("sma20"))
        .drop_nulls("sma20")
        .group_by("date")
        .agg((pl.col("close") > pl.col("sma20")).mean().alias("breadth"))
        .sort("date")
        # shift so a bar inside day D sees breadth through D-1
        .with_columns(pl.col("breadth").shift(1).alias("breadth"))
        .drop_nulls("breadth")
    )


def evaluate(frame: pl.DataFrame, prices: pl.DataFrame, condition, label: str,
             reward_risk: float, slots: int, cost: float, halves: bool = True) -> dict:
    tagged = frame.with_columns((pl.col("signal_raw") & condition).fill_null(False).alias("signal"))
    n = int(tagged["signal"].sum())
    if n < 50:
        return {"filter": label, "signals": n, "cagr_pct": None, "max_dd_pct": None}
    trades = find_trades(tagged, cost, reward_risk)
    if trades.is_empty():
        return {"filter": label, "signals": n, "cagr_pct": None, "max_dd_pct": None}
    equity, taken, *_ = simulate(trades, prices, slots, cost)
    cagr, maxdd = performance(equity, prices.height)
    closed = trades.filter(pl.col("outcome") != "open")
    row = {
        "filter": label, "signals": n, "taken": taken,
        "win_pct": round(closed.filter(pl.col("ret") > 0).height / max(closed.height, 1) * 100, 1),
        "mean_trade_pct": round(float(closed["ret"].mean()) * 100, 3),
        "cagr_pct": round(cagr * 100, 2), "max_dd_pct": round(maxdd * 100, 2),
    }
    if halves:
        mid = prices["datetime"][prices.height // 2]
        for tag, sub in (("h1", trades.filter(pl.col("entry_time") < mid.timestamp() * 1_000_000)),
                         ("h2", trades.filter(pl.col("entry_time") >= mid.timestamp() * 1_000_000))):
            if sub.height >= 20:
                sub_closed = sub.filter(pl.col("outcome") != "open")
                row[f"{tag}_mean_pct"] = round(float(sub_closed["ret"].mean()) * 100, 3)
            else:
                row[f"{tag}_mean_pct"] = None
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reward-risk", type=float, default=5.0)
    parser.add_argument("--slots", type=int, default=10)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--ema-max", type=float, default=53.0)
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--ema-span", type=int, default=21)
    args = parser.parse_args()
    cost = args.cost_bps / 10_000

    universe = pl.read_parquet(UNIVERSE)
    symbols = universe["symbol"].to_list()
    daily = (pl.scan_parquet(DAILY_GLOB, hive_partitioning=True)
             .filter(pl.col("symbol").is_in(symbols))
             .select("symbol", "date", "open", "high", "low", "close", "volume").collect())
    hourly = (pl.scan_parquet(HOURLY_GLOB, hive_partitioning=True)
              .filter(pl.col("symbol").is_in(symbols))
              .select("symbol", "datetime", "open", "high", "low", "close", "volume").collect())
    print(f"daily {daily.height:,} rows | hourly {hourly.height:,} rows")

    frame = hourly.sort("symbol", "datetime").with_columns(
        rsi("close", args.rsi_period).over("symbol").alias("rsi_h"))
    frame = frame.with_columns(
        ema("rsi_h", args.ema_span).over("symbol").alias("rsi_ema"),
        pl.col("rsi_h").shift(1).over("symbol").alias("rsi_prev"))
    frame = attach_htf(frame, daily, args.rsi_period)

    caps = pl.read_csv(CAP_CACHE) if CAP_CACHE.exists() else fetch_market_caps(symbols)
    frame = attach_market_cap(frame, daily, caps)

    frame = frame.with_columns(
        ((pl.col("rsi_prev") <= 60) & (pl.col("rsi_h") > 60) & (pl.col("rsi_ema") < args.ema_max)
         & (pl.col("rsi_daily") > 60) & (pl.col("rsi_weekly") > 60)
         & (pl.col("rsi_monthly") > 60) & (pl.col("cap_cr") > 5000)).alias("signal_raw")
    ).sort("symbol", "datetime")
    frame = candle_features(frame)
    frame = frame.join(breadth_by_date(daily), on="date", how="left")

    signals = frame.filter(pl.col("signal_raw"))
    print(f"\nbase signals: {signals.height:,}")
    print("\nDistribution across the base signals (pick thresholds against these, "
          "not against intuition):")
    for col in ("close_pos", "body", "upper_wick", "risk_pct", "rsi_jump",
                "vol_ratio", "turnover_cr", "above_h50", "breadth"):
        q = signals[col].drop_nulls()
        if not q.len():
            continue
        print(f"  {col:<12} p10 {q.quantile(0.1):>8.3f}  p25 {q.quantile(0.25):>8.3f}  "
              f"median {q.median():>8.3f}  p75 {q.quantile(0.75):>8.3f}  "
              f"p90 {q.quantile(0.9):>8.3f}")
    print("  hour     " + str(signals["hour"].value_counts().sort("hour").to_dicts()))

    signal_symbols = signals["symbol"].unique().to_list()
    prices = (hourly.filter(pl.col("symbol").is_in(signal_symbols))
              .select("symbol", "datetime", "close")
              .pivot(on="symbol", index="datetime", values="close").sort("datetime"))
    prices = prices.with_columns(
        [pl.col(c).forward_fill().backward_fill() for c in prices.columns if c != "datetime"])

    candidates = [
        ("(base, no extra filter)", pl.lit(True)),
        ("marubozu: close_pos >= 0.8", pl.col("close_pos") >= 0.8),
        ("weak close: close_pos <= 0.5", pl.col("close_pos") <= 0.5),
        ("decisive body >= 0.6 & green", (pl.col("body") >= 0.6) & (pl.col("close") > pl.col("open"))),
        ("no upper wick <= 0.15", pl.col("upper_wick") <= 0.15),
        ("tight risk <= 1%", pl.col("risk_pct") <= 0.01),
        ("wide risk >= 2%", pl.col("risk_pct") >= 0.02),
        ("volume >= 1.5x avg", pl.col("vol_ratio") >= 1.5),
        ("volume >= 2.5x avg", pl.col("vol_ratio") >= 2.5),
        ("liquid: turnover >= 5cr", pl.col("turnover_cr") >= 5.0),
        ("decisive cross: jump >= 8", pl.col("rsi_jump") >= 8),
        ("no repeat cross in 20 bars", pl.col("recent_signals") == 0),
        ("skip first/last bar", ~pl.col("hour").is_in([9, 15])),
        ("not extended: daily RSI<=75", pl.col("rsi_daily") <= 75),
        ("above hourly 50-SMA", pl.col("above_h50") > 0),
        ("RSI-EMA turning up", pl.col("ema_rising")),
        ("breadth >= 0.5", pl.col("breadth") >= 0.5),
    ]

    print(f"\nevaluating {len(candidates)} filters at 1:{args.reward_risk:g}, "
          f"{args.slots} slots, {args.cost_bps:g}bps/side\n")
    rows = []
    for label, condition in candidates:
        row = evaluate(frame, prices, condition, label, args.reward_risk,
                       args.slots, cost)
        rows.append(row)
        print(f"  {row['filter']:<32} n={row['signals']:>5}  "
              f"CAGR {str(row['cagr_pct']):>7}%  DD {str(row['max_dd_pct']):>7}%  "
              f"mean {str(row.get('mean_trade_pct')):>7}%")

    table = pl.DataFrame(rows).sort("cagr_pct", descending=True, nulls_last=True)
    print(f"\n{'=' * 108}\nFILTER SWEEP (base screen + one filter), 1:{args.reward_risk:g}\n{'=' * 108}")
    with pl.Config(tbl_rows=40, tbl_width_chars=200, fmt_str_lengths=34):
        print(table)
    out = REPO_ROOT / ".cache" / "screener" / "filter_lab.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    table.write_csv(out)
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
