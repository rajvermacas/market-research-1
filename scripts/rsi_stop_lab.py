#!/usr/bin/env python3
"""Do the winning entry filters stack, and is the stop itself the real problem?

The filter sweep found that every filter which helped — marubozu, no upper wick, wide
risk — says the same thing in different words: the entry candle closed far above its own
low, so the stop sits far from the entry. Their mirror images (weak close, tight risk)
are the worst performers. That is one effect, not three, and it is mechanical rather than
predictive: a stop a few ticks under the entry is inside the noise and gets hit whatever
the stock then does.

If that reading is right, filtering to wide-risk candles is the crude fix — it throws away
73% of the signals to avoid the bad stops. The direct fix is to stop using the candle low
as the stop at all, and place it a noise-aware distance away (an ATR multiple) on every
signal. This script tests both, plus whether the filters stack once stop distance is
controlled for.

Usage:
    python scripts/rsi_stop_lab.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from screener import rsi, fetch_market_caps
from hourly_rsi_screener import ema
from rsi_backtest import attach_htf, attach_market_cap, find_trades, performance, simulate
from rsi_filter_lab import candle_features

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
HOURLY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "hourly" / "**" / "*.parquet")
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CAP_CACHE = REPO_ROOT / ".cache" / "screener" / "market_caps.csv"
FEATURE_CACHE = REPO_ROOT / ".cache" / "screener" / "features_hourly.parquet"


def build_features(period: int, ema_span: int) -> pl.DataFrame:
    if FEATURE_CACHE.exists():
        print(f"features from cache {FEATURE_CACHE.name}")
        return pl.read_parquet(FEATURE_CACHE)
    universe = pl.read_parquet(UNIVERSE)
    symbols = universe["symbol"].to_list()
    daily = (pl.scan_parquet(DAILY_GLOB, hive_partitioning=True)
             .filter(pl.col("symbol").is_in(symbols))
             .select("symbol", "date", "open", "high", "low", "close", "volume").collect())
    hourly = (pl.scan_parquet(HOURLY_GLOB, hive_partitioning=True)
              .filter(pl.col("symbol").is_in(symbols))
              .select("symbol", "datetime", "open", "high", "low", "close", "volume").collect())
    frame = hourly.sort("symbol", "datetime").with_columns(
        rsi("close", period).over("symbol").alias("rsi_h"))
    frame = frame.with_columns(
        ema("rsi_h", ema_span).over("symbol").alias("rsi_ema"),
        pl.col("rsi_h").shift(1).over("symbol").alias("rsi_prev"))
    frame = attach_htf(frame, daily, period)
    caps = pl.read_csv(CAP_CACHE) if CAP_CACHE.exists() else fetch_market_caps(symbols)
    frame = attach_market_cap(frame, daily, caps)
    frame = frame.with_columns(
        ((pl.col("rsi_prev") <= 60) & (pl.col("rsi_h") > 60) & (pl.col("rsi_ema") < 60)
         & (pl.col("rsi_daily") > 60) & (pl.col("rsi_weekly") > 60)
         & (pl.col("rsi_monthly") > 60) & (pl.col("cap_cr") > 5000)).alias("signal_raw")
    ).sort("symbol", "datetime")
    frame = candle_features(frame)
    # ATR(14) on the hourly bar, the noise scale the stop has to clear
    prev_close = pl.col("close").shift(1).over("symbol")
    true_range = pl.max_horizontal(
        pl.col("high") - pl.col("low"),
        (pl.col("high") - prev_close).abs(),
        (pl.col("low") - prev_close).abs(),
    )
    frame = frame.with_columns(true_range.alias("tr"))
    frame = frame.with_columns(
        pl.col("tr").rolling_mean(14).over("symbol").alias("atr"))
    FEATURE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(FEATURE_CACHE, compression="zstd")
    print(f"features cached to {FEATURE_CACHE.name}")
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reward-risk", type=float, default=5.0)
    parser.add_argument("--slots", type=int, default=10)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    args = parser.parse_args()
    cost = args.cost_bps / 10_000

    frame = build_features(14, 21)
    hourly = frame.select("symbol", "datetime", "close")
    signals = frame.filter(pl.col("signal_raw"))
    signal_symbols = signals["symbol"].unique().to_list()
    prices = (hourly.filter(pl.col("symbol").is_in(signal_symbols))
              .pivot(on="symbol", index="datetime", values="close").sort("datetime"))
    prices = prices.with_columns(
        [pl.col(c).forward_fill().backward_fill() for c in prices.columns if c != "datetime"])
    mid = prices["datetime"][prices.height // 2].timestamp() * 1_000_000
    print(f"base signals {signals.height:,} | grid {prices.height:,} bars")

    # ATR-multiple stop prices, available on every signal
    frame = frame.with_columns([
        (pl.col("close") - k * pl.col("atr")).alias(f"stop_atr{k}")
        for k in (0.5, 1.0, 1.5, 2.0, 3.0)
    ])

    tests = [
        ("candle low (base)", pl.lit(True), None),
        ("candle low + marubozu>=0.8", pl.col("close_pos") >= 0.8, None),
        ("candle low + risk>=2%", pl.col("risk_pct") >= 0.02, None),
        ("candle low + marubozu + risk>=2%",
         (pl.col("close_pos") >= 0.8) & (pl.col("risk_pct") >= 0.02), None),
        ("candle low + risk>=2% + vol>=1.5x",
         (pl.col("risk_pct") >= 0.02) & (pl.col("vol_ratio") >= 1.5), None),
        ("candle low + risk>=2% + no wick",
         (pl.col("risk_pct") >= 0.02) & (pl.col("upper_wick") <= 0.15), None),
        ("0.5xATR stop", pl.lit(True), "stop_atr0.5"),
        ("1.0xATR stop", pl.lit(True), "stop_atr1.0"),
        ("1.5xATR stop", pl.lit(True), "stop_atr1.5"),
        ("2.0xATR stop", pl.lit(True), "stop_atr2.0"),
        ("3.0xATR stop", pl.lit(True), "stop_atr3.0"),
        ("2.0xATR stop + marubozu", pl.col("close_pos") >= 0.8, "stop_atr2.0"),
        ("2.0xATR stop + vol>=1.5x", pl.col("vol_ratio") >= 1.5, "stop_atr2.0"),
    ]

    rows = []
    for label, condition, stop_column in tests:
        tagged = frame.with_columns(
            (pl.col("signal_raw") & condition).fill_null(False).alias("signal"))
        n = int(tagged["signal"].sum())
        trades = find_trades(tagged, cost, args.reward_risk, stop_column)
        if trades.is_empty():
            continue
        equity, taken, _ = simulate(trades, prices, args.slots, cost)
        cagr, maxdd = performance(equity, prices.height)
        closed = trades.filter(pl.col("outcome") != "open")
        h1 = trades.filter(pl.col("entry_time") < mid).filter(pl.col("outcome") != "open")
        h2 = trades.filter(pl.col("entry_time") >= mid).filter(pl.col("outcome") != "open")
        rows.append({
            "variant": label, "signals": n, "taken": taken,
            "win_pct": round(closed.filter(pl.col("ret") > 0).height
                             / max(closed.height, 1) * 100, 1),
            "mean_trade_pct": round(float(closed["ret"].mean()) * 100, 3),
            "cagr_pct": round(cagr * 100, 2), "max_dd_pct": round(maxdd * 100, 2),
            "h1_mean_pct": round(float(h1["ret"].mean()) * 100, 3) if h1.height > 20 else None,
            "h2_mean_pct": round(float(h2["ret"].mean()) * 100, 3) if h2.height > 20 else None,
        })
        print(f"  {label:<34} n={n:>5}  CAGR {rows[-1]['cagr_pct']:>7}%  "
              f"DD {rows[-1]['max_dd_pct']:>7}%  h1 {str(rows[-1]['h1_mean_pct']):>7} "
              f"h2 {str(rows[-1]['h2_mean_pct']):>7}")

    table = pl.DataFrame(rows).sort("cagr_pct", descending=True, nulls_last=True)
    print(f"\n{'=' * 112}\nSTOP POLICY AND FILTER STACKING, 1:{args.reward_risk:g}\n{'=' * 112}")
    with pl.Config(tbl_rows=30, tbl_width_chars=200, fmt_str_lengths=36):
        print(table)
    out = REPO_ROOT / ".cache" / "screener" / "stop_lab.csv"
    table.write_csv(out)
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
