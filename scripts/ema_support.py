#!/usr/bin/env python3
"""Which momentum stocks actually respect their daily 20/50 EMA as support?

"Takes support from the EMA" is a claim about behaviour over time, not a condition on
today's bar, so this measures it historically and ranks by how reliably it held.

Event definition — one clean touch, not a cluster of them:

    at bar t the previous close sat comfortably above the EMA (by --separation),
    and bar t's low came down to within --touch-tol of the EMA.

Requiring the prior bar to be clearly above the EMA is what keeps a week of chopping
along the average from counting as five separate touches.

Outcome, judged --horizon bars later:

    HELD   no close in the window fell more than --break-tol below the EMA at touch,
           and the close at t+horizon is back above the EMA
    FAILED otherwise

Reported per symbol and per EMA: number of touches, hold rate, median return from the
touch close to the close --horizon bars later, and the share of days spent above the EMA
(a trend-quality check — a stock below its EMA most of the time is not "taking support").

Hold rate alone is misleading: a stock in a relentless uptrend scores well because *any*
entry would have worked, not because the average did anything. So each symbol also gets an
edge — the median return after a touch minus the median return from a random bar in the
same window. Positive edge means the touch itself carried information. Ranking is by hold
rate, but read the edge column before acting on it.

Absolute hold rates are not comparable across setups; across this cohort the median is
around 37% on the 20 EMA and 41% on the 50 EMA, so judge a name against that, not against
50%. --min-hold defaults to 0 for exactly that reason: the tool ranks, it does not gate.

Usage:
    python scripts/ema_support.py                          # monthly RSI > 60 universe
    python scripts/ema_support.py --years 5 --min-touches 12
    python scripts/ema_support.py --universe nifty500 --no-market-cap
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screener import CRORE, fetch_market_caps, last_rsi, resample  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CACHE = REPO_ROOT / ".cache" / "screener"


def forward(column: str, offsets: range) -> list[pl.Expr]:
    return [pl.col(column).shift(-i).over("symbol") for i in offsets]


def measure(daily: pl.DataFrame, span: int, args) -> pl.DataFrame:
    """Touch events and their outcomes for one EMA length."""
    ema = f"ema{span}"
    horizon = args.horizon

    bars = daily.sort("symbol", "date").with_columns(
        pl.col("close").ewm_mean(span=span, adjust=False).over("symbol").alias(ema)
    )
    # EMA needs warm-up, so compute on full history and only then cut to the study window.
    cutoff = daily["date"].max() - dt.timedelta(days=int(args.years * 365.25))
    bars = bars.filter(pl.col("date") >= cutoff)

    prev_close = pl.col("close").shift(1).over("symbol")
    prev_ema = pl.col(ema).shift(1).over("symbol")

    bars = bars.with_columns(
        # clearly above yesterday, down to the average today
        (
            (prev_close > prev_ema * (1 + args.separation))
            & (pl.col("low") <= pl.col(ema) * (1 + args.touch_tol))
        ).alias("touch"),
        pl.min_horizontal(forward("close", range(1, horizon + 1))).alias("min_fwd"),
        pl.max_horizontal(forward("close", range(1, horizon + 1))).alias("max_fwd"),
        pl.col("close").shift(-horizon).over("symbol").alias("close_fwd"),
        pl.col(ema).shift(-horizon).over("symbol").alias("ema_fwd"),
        (pl.col("close") > pl.col(ema)).alias("is_above"),
    )

    above_share = bars.group_by("symbol").agg(pl.col("is_above").mean().alias(f"above_{span}"))

    events = bars.filter(pl.col("touch") & pl.col("close_fwd").is_not_null()).with_columns(
        (
            (pl.col("min_fwd") >= pl.col(ema) * (1 - args.break_tol))
            & (pl.col("close_fwd") > pl.col("ema_fwd"))
        ).alias("held"),
        (pl.col("close_fwd") / pl.col("close") - 1).alias("fwd_return"),
        (pl.col("max_fwd") / pl.col("close") - 1).alias("best_bounce"),
    )

    # Control: the same forward return measured from every bar in the window, so a touch's
    # return can be judged against simply having been long this stock at a random moment.
    baseline = (
        bars.filter(pl.col("close_fwd").is_not_null())
        .group_by("symbol")
        .agg((pl.col("close_fwd") / pl.col("close") - 1).median().alias(f"base_{span}"))
    )

    return (
        events.group_by("symbol")
        .agg(
            pl.len().alias(f"touches_{span}"),
            pl.col("held").mean().alias(f"hold_{span}"),
            pl.col("fwd_return").median().alias(f"ret_{span}"),
            pl.col("best_bounce").median().alias(f"bounce_{span}"),
        )
        .join(above_share, on="symbol", how="left")
        .join(baseline, on="symbol", how="left")
        .with_columns((pl.col(f"ret_{span}") - pl.col(f"base_{span}")).alias(f"edge_{span}"))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--universe", default="nse_all")
    parser.add_argument("--monthly-rsi-min", type=float, default=60.0,
                        help="monthly momentum gate (default 60; set 0 to skip)")
    parser.add_argument("--years", type=float, default=3.0, help="study window (default 3)")
    parser.add_argument("--horizon", type=int, default=10, help="bars to judge the bounce over")
    parser.add_argument("--separation", type=float, default=0.015,
                        help="prior close must be this far above the EMA (default 1.5%%)")
    parser.add_argument("--touch-tol", type=float, default=0.005,
                        help="low must reach within this of the EMA (default 0.5%%)")
    parser.add_argument("--break-tol", type=float, default=0.02,
                        help="a close this far below the EMA counts as broken (default 2%%)")
    parser.add_argument("--min-touches", type=int, default=8,
                        help="minimum touches on each EMA for a rate to mean anything")
    parser.add_argument("--min-hold", type=float, default=0.0,
                        help="optional absolute hold-rate floor; 0 (default) ranks instead of gates")
    parser.add_argument("--top", type=int, default=25, help="how many to show (default 25)")
    parser.add_argument("--turnover-min", type=float, default=5.0, help="rupees crore")
    parser.add_argument("--market-cap-min", type=float, default=5000.0, help="rupees crore")
    parser.add_argument("--no-market-cap", action="store_true")
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
    print(f"Universe {args.universe}: {universe.height} symbols | panel through {as_of}\n")

    if args.monthly_rsi_min > 0:
        monthly = last_rsi(resample(daily, "1mo"), 14, "rsi_monthly")
        keep = monthly.filter(pl.col("rsi_monthly") > args.monthly_rsi_min)
        print(f"1. Monthly RSI(14) > {args.monthly_rsi_min}: {keep.height} symbols")
        daily = daily.filter(pl.col("symbol").is_in(keep["symbol"].to_list()))
    else:
        keep = daily.select(pl.col("symbol").unique()).with_columns(pl.lit(None).alias("rsi_monthly"))

    # Liquidity first — a hold rate on an untradeable microcap is noise.
    turnover = (
        daily.sort("symbol", "date")
        .group_by("symbol")
        .agg(((pl.col("close") * pl.col("volume")).tail(20).mean() / CRORE).alias("turnover_cr"),
             pl.len().alias("bars"))
        .filter((pl.col("turnover_cr") > args.turnover_min) & (pl.col("bars") > 300))
    )
    daily = daily.filter(pl.col("symbol").is_in(turnover["symbol"].to_list()))
    print(f"2. Liquid enough (turnover > {args.turnover_min:g} cr, >300 bars): {turnover.height} symbols")

    print(f"\n3. Measuring EMA touches over the last {args.years:g} years "
          f"(horizon {args.horizon} bars)")
    stats = measure(daily, 20, args).join(measure(daily, 50, args), on="symbol", how="inner")

    enough = stats.filter(
        (pl.col("touches_20") >= args.min_touches) & (pl.col("touches_50") >= args.min_touches)
    )
    print(f"   with >= {args.min_touches} touches on both EMAs: {enough.height} symbols")

    print(f"   cohort median hold rate:  20 EMA {enough['hold_20'].median():.0%}, "
          f"50 EMA {enough['hold_50'].median():.0%}")
    respects = enough
    if args.min_hold > 0:
        respects = enough.filter(
            (pl.col("hold_20") >= args.min_hold) & (pl.col("hold_50") >= args.min_hold)
        )
        print(f"   holding >= {args.min_hold:.0%} on both:      {respects.height} symbols")

    result = (
        respects.join(keep, on="symbol", how="left")
        .join(turnover.select("symbol", "turnover_cr"), on="symbol", how="left")
        .join(universe.select("symbol", "company_name"), on="symbol", how="left")
        .with_columns(((pl.col("hold_20") + pl.col("hold_50")) / 2).alias("hold_avg"))
    )

    if not args.no_market_cap and result.height:
        print(f"\n4. Market cap > {args.market_cap_min:,.0f} crore")
        caps = fetch_market_caps(result["symbol"].to_list())
        result = result.join(caps, on="symbol", how="inner").filter(
            pl.col("market_cap_cr") > args.market_cap_min
        )
        print(f"   after market cap: {result.height} symbols")
    else:
        result = result.with_columns(pl.lit(None, dtype=pl.Float64).alias("market_cap_cr"))

    result = result.sort(["hold_avg", "touches_20"], descending=True).select(
        "symbol", "company_name", "market_cap_cr", "rsi_monthly",
        "touches_20", "hold_20", "ret_20", "edge_20", "above_20",
        "touches_50", "hold_50", "ret_50", "edge_50", "above_50",
        "hold_avg", "turnover_cr",
    )
    total = result.height
    result = result.head(args.top)

    print(f"\n{'=' * 78}\nTop {result.height} of {total} momentum names by 20/50 EMA hold rate"
          f"\n{'=' * 78}")
    if result.height:
        display = result.with_columns(
            [(pl.col(c) * 100).round(0) for c in ("hold_20", "hold_50", "above_20", "above_50", "hold_avg")]
            + [(pl.col(c) * 100).round(1) for c in ("ret_20", "ret_50", "edge_20", "edge_50")]
            + [pl.col("market_cap_cr").round(0), pl.col("rsi_monthly").round(1),
               pl.col("turnover_cr").round(0)]
        )
        with pl.Config(tbl_rows=60, tbl_width_chars=230, fmt_str_lengths=26):
            print(display)
        print(f"\nhold_*/above_* are percentages. ret_* is the median % return {args.horizon} "
              "bars after a touch; edge_* is that minus the same stock's median return from a "
              "random bar.\nA high hold rate with edge near zero means the stock simply trended, "
              "not that the EMA held it up.")
    out = Path(args.out) if args.out else CACHE / f"ema_support_{dt.date.today()}.csv"
    result.write_csv(out)
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
