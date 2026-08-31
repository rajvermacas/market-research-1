#!/usr/bin/env python3
"""Cross-sectional momentum rotation on the Nifty 500, with a regime overlay.

The hourly RSI family tops out around +18% CAGR against a +20.5% market, so this tests a
different mechanism entirely rather than another setting of the same one. Cross-sectional
momentum — hold the strongest names, rebalance periodically — is among the most replicated
effects in equities and has historically been pronounced in Indian mid-caps.

    signal      total return over `--lookback` months, skipping the most recent month.
                The skip is standard: the latest month carries short-term reversal, which
                is a different and opposing effect.
    hold        the top `--top` names, equal weight, rebalanced monthly.
    regime      optional. Invest only while an equal-weight index of the universe is above
                its own `--regime-ma` month average, otherwise sit in cash. Momentum's
                weakness is the crash at a market turn, and the turn is what this detects.

Prices come from the committed daily panel, which is split-adjusted and reaches back to
2000, so the ranking is computed on fully-formed history from the first test month.

Survivorship: the universe is today's Nifty 500. Names that fell out of the index are
absent, which flatters any long-only result measured over a decade. Read accordingly.

Usage:
    python scripts/momentum_rotation.py --lookback 12 --top 25 --regime-ma 10
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY = REPO_ROOT / "data" / "ohlcv" / "daily"
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"


def performance(curve: np.ndarray, years: float) -> tuple[float, float]:
    cagr = curve[-1] ** (1 / years) - 1
    dd = (curve / np.maximum.accumulate(curve) - 1).min()
    return cagr, dd


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--universe", default="nifty500")
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--lookback", type=int, nargs="+", default=[12])
    ap.add_argument("--top", type=int, nargs="+", default=[25])
    ap.add_argument("--regime-ma", type=int, nargs="+", default=[0],
                    help="months in the index average; 0 disables the overlay")
    ap.add_argument("--stock-ma", type=int, default=0,
                    help="months in each stock's own average; hold only names above it")
    ap.add_argument("--abs-mom", action="store_true",
                    help="require the name's own lookback return to be positive")
    ap.add_argument("--leverage", type=float, nargs="+", default=[1.0],
                    help="gross exposure while invested; >1 borrows at --funding-rate")
    ap.add_argument("--funding-rate", type=float, default=0.09,
                    help="annual cost of borrowed capital (default 9%%, Indian margin)")
    ap.add_argument("--cost-bps", type=float, default=25.0,
                    help="round-trip cost per name replaced at each rebalance")
    args = ap.parse_args()

    u = pl.read_parquet(UNIVERSE)
    if args.universe != "nse_all":
        u = u.filter(pl.col(f"in_{args.universe}"))
    syms = u["symbol"].to_list()
    d = (pl.scan_parquet(str(DAILY / "**" / "*.parquet"), hive_partitioning=True)
         .filter(pl.col("symbol").is_in(syms))
         .select("symbol", "date", "close").collect().sort("symbol", "date"))
    # month-end closes
    m = (d.with_columns(pl.col("date").dt.truncate("1mo").alias("mo"))
         .group_by("symbol", "mo").agg(pl.col("close").last()).sort("symbol", "mo"))
    wide = m.pivot(on="symbol", index="mo", values="close").sort("mo")
    months = wide["mo"].to_list()
    cols = [c for c in wide.columns if c != "mo"]
    px = wide.select(cols).to_numpy()

    start_i = next(i for i, mm in enumerate(months) if str(mm) >= args.start)
    cost = args.cost_bps / 10_000

    print(f"{len(cols)} symbols | {len(months)} months | test from {months[start_i]}")
    print(f"{'lookback':>9}{'top':>5}{'regimeMA':>9}{'CAGR%':>9}{'maxDD%':>9}{'ret/DD':>8}"
          f"{'invested':>10}")
    rows = []
    for lb in args.lookback:
        # momentum: total return from t-lb-1 to t-1  (skip the most recent month)
        mom = np.full_like(px, np.nan)
        mom[lb + 1:] = px[1:-lb] / px[: -lb - 1] - 1
        for ma in args.regime_ma:
            # equal-weight index of names alive at the test start, and its own average
            alive = ~np.isnan(px[start_i])
            idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
            idx_ma = pl.Series(idx).rolling_mean(ma).to_numpy() if ma else None
            for top in args.top:
              for lev in args.leverage:
                  eq, invested, held = [1.0], 0, set()
                  for t in range(start_i, len(months) - 1):
                      on = True if not ma else bool(idx[t] > idx_ma[t]) if not np.isnan(idx_ma[t]) else False
                      scores = mom[t].copy()
                      scores[np.isnan(px[t]) | np.isnan(px[t + 1])] = np.nan
                      if args.stock_ma:
                          # Hold only names above their own average. Cross-sectional momentum
                          # ranks a stock against its peers, which keeps ranking a falling
                          # stock highly while everything falls; this asks the separate
                          # question of whether the name itself is still trending.
                          k = args.stock_ma
                          if t >= k:
                              own = np.nanmean(px[t - k + 1:t + 1], axis=0)
                              scores[~(px[t] > own)] = np.nan
                      if args.abs_mom:
                          # Absolute momentum: never hold a name whose own lookback return
                          # is negative, however good its rank.
                          scores[~(scores > 0)] = np.nan
                      pick = set()
                      if on and np.isfinite(scores).sum() >= max(top // 2, 3):
                          n = min(top, int(np.isfinite(scores).sum()))
                          pick = set(np.argsort(-np.nan_to_num(scores, nan=-1e9))[:n])
                      turnover = len(pick - held) / max(len(pick), 1) if pick else 0.0
                      if pick:
                          r = np.nanmean(px[t + 1, list(pick)] / px[t, list(pick)]) - 1
                          # Leverage scales the month's return and pays funding on the
                          # borrowed part only while the position is actually held.
                          gross = lev * r - max(lev - 1.0, 0.0) * args.funding_rate / 12
                          eq.append(eq[-1] * (1 + gross) * (1 - cost * turnover * lev))
                          invested += 1
                      else:
                          eq.append(eq[-1])
                      held = pick
                  curve = np.array(eq)
                  years = (len(curve) - 1) / 12
                  c, dd = performance(curve, years)
                  rows.append((c * 100, dd * 100, lb, top, ma, lev,
                               invested / (len(curve) - 1)))
                  print(f"{lb:>9}{top:>5}{ma if ma else '-':>9}{c * 100:>9.2f}"
                        f"{dd * 100:>9.2f}{abs(c / dd):>8.2f}"
                        f"{invested / (len(curve) - 1) * 100:>8.0f}%  x{lev:g}")
    hits = [r for r in rows if r[0] >= 35 and r[1] >= -25]
    print(f"\nmeeting >=35% CAGR and DD better than -25%: {len(hits)}")
    for c, dd, lb, top, ma, lev, inv in sorted(hits, reverse=True)[:6]:
        print(f"   lookback {lb}mo, top {top}, regimeMA {ma}, leverage x{lev:g}: "
              f"{c:+.2f}% CAGR / {dd:.2f}% DD  ({inv * 100:.0f}% invested)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
