#!/usr/bin/env python3
"""Exhaustive filter-combination search for the hourly RSI setup.

Every subset of the optional filters is scored, on top of a fixed core: the hourly RSI
crossing above 60 while the weekly and monthly RSI are above 60 and market cap clears
5,000 crore. Those three are the setup's definition rather than tunables, so they stay on.

The search is cheap because stacking removed the one-position-per-symbol rule from the
forward walk: a trade's exit now depends only on its own entry bar and stop, not on which
other signals exist. So exits are resolved ONCE for the superset of signals and each
combination is a subset of that trade table, rather than 2^n forward walks.

Ranking is deliberately not by CAGR. With 2^8 combinations measured over 2.9 years of one
rising market, the best full-window number is substantially luck. A combination is only
reported as a candidate if it earns money in BOTH halves of the window, and the table
carries the halves so the reader can see the margin rather than trust the ordering.

Usage:
    python scripts/rsi_combo_search.py --reward-risk 10
"""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import numpy as np
import polars as pl

from rsi_backtest import find_trades, performance, simulate
from rsi_stop_lab import build_features

REPO_ROOT = Path(__file__).resolve().parents[1]

# name -> (predicate on the feature frame, short label)
OPTIONAL = {
    "dailyRSI>60":   pl.col("rsi_daily") > 60,
    "emaRSI<53":     pl.col("rsi_ema") < 53,
    # Paired with emaRSI<53 this brackets the smoothed RSI into 40-53: the hourly cooled
    # off, but did not collapse. Below 40 the "pullback" is a decline.
    "emaRSI>40":     pl.col("rsi_ema") > 40,
    "marubozu>=.8":  pl.col("close_pos") >= 0.8,
    "risk>=2%":      pl.col("risk_pct") >= 0.02,
    "vol>=1.5x":     pl.col("vol_ratio") >= 1.5,
    "rsiJump>=8":    pl.col("rsi_jump") >= 8,
    "noRepeat20":    pl.col("recent_signals") == 0,
    "skip9&15":      ~pl.col("hour").is_in([9, 15]),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reward-risk", type=float, default=10.0)
    parser.add_argument("--slots", type=int, default=10)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--min-trades", type=int, default=100,
                        help="ignore combinations with fewer signals than this")
    args = parser.parse_args()
    cost = args.cost_bps / 10_000

    frame = build_features(14, 21, 53.0)
    core = ((pl.col("rsi_prev") <= 60) & (pl.col("rsi_h") > 60)
            & (pl.col("rsi_weekly") > 60) & (pl.col("rsi_monthly") > 60)
            & (pl.col("cap_cr") > 5000))
    frame = frame.with_columns(core.fill_null(False).alias("signal"))
    superset = frame.filter(pl.col("signal"))
    print(f"core signals (cross + weekly + monthly + cap): {superset.height:,}")

    hourly = frame.select("symbol", "datetime", "close")
    traded = superset["symbol"].unique().to_list()
    prices = (hourly.filter(pl.col("symbol").is_in(traded))
              .pivot(on="symbol", index="datetime", values="close").sort("datetime"))
    prices = prices.with_columns(
        [pl.col(c).forward_fill().backward_fill() for c in prices.columns if c != "datetime"])
    mid = prices["datetime"][prices.height // 2].timestamp() * 1_000_000

    print(f"resolving exits once at 1:{args.reward_risk:g} ...", flush=True)
    trades = find_trades(frame, cost, args.reward_risk)
    print(f"  {trades.height:,} trades")

    # carry each filter's verdict onto its trade, so a combination is a boolean AND
    flags = superset.select(
        "symbol",
        pl.col("datetime").dt.epoch("us").alias("entry_time"),
        *[cond.fill_null(False).alias(name) for name, cond in OPTIONAL.items()],
    )
    trades = trades.join(flags, on=["symbol", "entry_time"], how="inner")
    print(f"  {trades.height:,} trades carry filter flags")

    names = list(OPTIONAL)
    rows = []
    combos = [c for r in range(len(names) + 1) for c in itertools.combinations(names, r)]
    print(f"scoring {len(combos)} combinations\n", flush=True)
    for i, combo in enumerate(combos, 1):
        subset = trades
        for name in combo:
            subset = subset.filter(pl.col(name))
        if subset.height < args.min_trades:
            continue
        equity, taken, *_ = simulate(subset, prices, args.slots, cost)
        cagr, maxdd = performance(equity, prices.height)
        closed = subset.filter(pl.col("outcome") != "open")
        h1 = closed.filter(pl.col("entry_time") < mid)
        h2 = closed.filter(pl.col("entry_time") >= mid)
        if h1.height < 20 or h2.height < 20:
            continue
        ranked = closed["ret"].sort(descending=True)
        gains = float(ranked.filter(ranked > 0).sum())
        rows.append({
            "filters": " + ".join(combo) if combo else "(core only)",
            "n": len(combo), "signals": subset.height, "taken": taken,
            "win_pct": round(closed.filter(pl.col("ret") > 0).height / closed.height * 100, 1),
            "cagr_pct": round(cagr * 100, 2), "max_dd_pct": round(maxdd * 100, 2),
            "h1_mean_pct": round(float(h1["ret"].mean()) * 100, 3),
            "h2_mean_pct": round(float(h2["ret"].mean()) * 100, 3),
            "top10_pct": round(float(ranked.head(10).sum()) / gains * 100, 1) if gains else None,
        })
        if i % 32 == 0:
            print(f"  {i}/{len(combos)} scored", flush=True)

    table = pl.DataFrame(rows)
    out = REPO_ROOT / ".cache" / "screener" / f"combo_rr{args.reward_risk:g}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    table.write_csv(out)

    robust = table.filter((pl.col("h1_mean_pct") > 0) & (pl.col("h2_mean_pct") > 0))
    print(f"\n{len(rows)} combinations scored, {robust.height} profitable in BOTH halves")
    print(f"\n=== top 15 by CAGR among those robust in both halves ===")
    with pl.Config(tbl_rows=15, tbl_width_chars=190, fmt_str_lengths=60):
        print(robust.sort("cagr_pct", descending=True).head(15))
    print(f"\n=== top 5 by CAGR overall (ignoring robustness — for contrast) ===")
    with pl.Config(tbl_rows=5, tbl_width_chars=190, fmt_str_lengths=60):
        print(table.sort("cagr_pct", descending=True).head(5))
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
