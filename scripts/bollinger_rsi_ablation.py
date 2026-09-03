#!/usr/bin/env python3
"""RSI + Bollinger Band components, ablated on Nifty equity.

What this is testing, and what it is not. The source is a five-minute video whose only
machine-readable content is its chapter list — "RSI Signals / Bollinger Bands / Breakout
Strategy / Divergence / Trading Strategies" — so the rules inside it are not recoverable
and nothing here should be read as a reproduction of them. What is testable is the
canonical reading of those four components, which are standard and unambiguous
individually, measured separately and together so the contribution of each is visible
whatever recipe combines them.

    rsi_os      RSI(14) crosses back up through 30. The oversold buy.
    bb_lower    close returns above the lower Bollinger Band (20, 2) after closing
                below it. The band-touch mean-reversion trade.
    squeeze     bandwidth in its own bottom quintile, then a close above the upper
                band. The volatility-contraction breakout.
    divergence  price makes a lower low over the lookback while RSI makes a higher low,
                and RSI is turning up. Classic bullish divergence, with both pivots
                confirmed by later bars so nothing is read before it was knowable.
    combo       rsi_os and bb_lower and divergence together — the confluence the last
                chapter is for.

Every arm trades the same bars against the same two controls: equal-weight buy-and-hold,
and random entries drawn from the same days and walked to an exit by identical code.

The exit is held constant across arms and the headline is the fixed-horizon one. That is
not a stylistic choice: the previous study in this repository (supertrend_rsi_w.py) found
a clean, stable-looking ablation ordering that turned out to be entirely an artefact of
arms getting systematically different stop distances from a price-based stop. A fixed
horizon is the only exit here that cannot do that.

Daily bars from the committed panel. Survivorship bias applies — today's index membership
walked backwards — and the panel is thin before about 2015, so --start defaults there.

Usage:
    python scripts/bollinger_rsi_ablation.py
    python scripts/bollinger_rsi_ablation.py --universe nifty50 --horizon 10
    python scripts/bollinger_rsi_ablation.py --start 2005-01-01 --slots 20
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

from screener import rsi
from rsi_backtest import simulate, performance

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"

ARMS = ("rsi_os", "bb_lower", "squeeze", "divergence", "combo")


# ------------------------------------------------------------------------- indicators


def attach(panel: pl.DataFrame, rsi_period: int, bb: int, width: float,
           squeeze_pct: float, sma: int) -> pl.DataFrame:
    """RSI, Bollinger Bands and bandwidth per symbol, with the warm-up guard.

    Bandwidth is (upper - lower) / middle, and "squeezed" is measured against the symbol's
    OWN recent bandwidth rather than an absolute number: a 4% band is tight for a small
    cap and loose for a large one, so a fixed threshold would just select by volatility.
    The quantile is rolling and backward-looking — a full-sample quantile would be
    lookahead, and it flatters the breakout arm by telling it in advance which
    contractions were unusual.
    """
    out = panel.sort("symbol", "date").with_columns(
        rsi("close", rsi_period).over("symbol").alias("rsi"),
        pl.col("close").rolling_mean(bb).over("symbol").alias("bb_mid"),
        pl.col("close").rolling_std(bb, ddof=0).over("symbol").alias("bb_sd"),
        pl.col("close").rolling_mean(sma).over("symbol").alias("sma"),
        pl.int_range(pl.len()).over("symbol").alias("_seen"),
    )
    out = out.with_columns(
        (pl.col("bb_mid") + width * pl.col("bb_sd")).alias("bb_up"),
        (pl.col("bb_mid") - width * pl.col("bb_sd")).alias("bb_dn"),
    )
    out = out.with_columns(
        ((pl.col("bb_up") - pl.col("bb_dn")) / pl.col("bb_mid")).alias("bandwidth"))
    out = out.with_columns(
        pl.col("bandwidth").rolling_quantile(squeeze_pct, window_size=250)
        .over("symbol").alias("bw_floor"))
    settle = max(rsi_period * 3, bb * 3, 250)
    return out.with_columns(
        (pl.col("_seen") >= settle).alias("warm"),
        pl.col("rsi").shift(1).over("symbol").alias("rsi_prev"),
        pl.col("close").shift(1).over("symbol").alias("close_prev"),
        pl.col("bb_dn").shift(1).over("symbol").alias("bb_dn_prev"),
    )


def divergence_flags(rsi_a: np.ndarray, low: np.ndarray, *, confirm: int,
                     min_sep: int, max_sep: int, max_age: int,
                     settle: int) -> np.ndarray:
    """Bullish divergence: a lower price low against a higher RSI low.

    Both lows are *confirmed* pivots — `confirm` later bars had to fail to undercut them —
    so a divergence is treated as unknown until bar pivot + confirm. Drawn on a finished
    chart divergence is trivially visible; the whole difficulty is that its second low is
    only a low in hindsight, and a detector that ignores that is reading the future.

    The troughs are also required to be past the RSI warm-up, not merely the signalling
    bar: Wilder's RSI is a recursive EWM seeded at zero and its opening bars are the seed
    converging, which reads as a perfectly good pivot low to any geometric test.
    """
    n = len(rsi_a)
    flags = np.zeros(n, dtype=bool)
    if n < 2 * confirm + 2:
        return flags

    window = 2 * confirm + 1
    if n < window:
        return flags
    view = np.lib.stride_tricks.sliding_window_view(low, window)
    centre = low[confirm:n - confirm]
    with np.errstate(invalid="ignore"):
        keep = ((centre < np.nanmin(view[:, :confirm], axis=1))
                & (centre <= np.nanmin(view[:, confirm + 1:], axis=1)))
    keep &= ~np.isnan(centre)
    pivots = confirm + np.flatnonzero(keep)
    pivots = pivots[pivots >= settle]
    if pivots.size < 2:
        return flags

    known = pivots + confirm
    cursor = 0
    for t in range(n):
        while cursor < len(pivots) and known[cursor] <= t:
            cursor += 1
        if cursor < 2:
            continue
        p1, p2 = int(pivots[cursor - 2]), int(pivots[cursor - 1])
        if not (min_sep <= p2 - p1 <= max_sep) or t - p2 > max_age:
            continue
        if np.isnan(rsi_a[p1]) or np.isnan(rsi_a[p2]):
            continue
        # price lower, momentum higher — the definition
        if low[p2] < low[p1] and rsi_a[p2] > rsi_a[p1] and rsi_a[t] > rsi_a[t - 1]:
            flags[t] = True
    return flags


def arm_expression(arm: str, oversold: float) -> pl.Expr:
    """The entry condition for one arm, before the warm-up guard is applied."""
    return {
        "rsi_os": (pl.col("rsi_prev") <= oversold) & (pl.col("rsi") > oversold),
        # closed below the lower band yesterday, back inside today
        "bb_lower": (pl.col("close_prev") < pl.col("bb_dn_prev"))
                    & (pl.col("close") > pl.col("bb_dn")),
        "squeeze": (pl.col("bandwidth") <= pl.col("bw_floor"))
                   & (pl.col("close") > pl.col("bb_up")),
        "divergence": pl.col("div"),
        "combo": ((pl.col("rsi_prev") <= oversold) & (pl.col("rsi") > oversold)
                  & (pl.col("close_prev") < pl.col("bb_dn_prev"))
                  & (pl.col("close") > pl.col("bb_dn"))
                  & pl.col("div")),
    }[arm]


# ------------------------------------------------------------------------ trade search


def horizon_trades(panel: pl.DataFrame, cost: float, horizon: int) -> pl.DataFrame:
    """Hold every signal exactly `horizon` bars. No stop, no target, no discretion."""
    rows = []
    for (symbol,), part in panel.group_by("symbol", maintain_order=True):
        part = part.sort("date")
        idx = np.flatnonzero(part["signal"].to_numpy())
        if not idx.size:
            continue
        close = part["close"].to_numpy()
        stamp = part["date"].cast(pl.Datetime("us")).dt.epoch("us").to_numpy()
        n = len(close)
        idx = idx[idx < n - 1]
        exits = np.minimum(idx + horizon, n - 1)
        entry, out = close[idx], close[exits]
        keep = np.isfinite(entry) & (entry > 0) & np.isfinite(out)
        for i, j, e, x in zip(idx[keep], exits[keep], entry[keep], out[keep]):
            rows.append({"symbol": symbol, "entry_time": int(stamp[i]),
                         "exit_time": int(stamp[j]), "entry": float(e), "exit": float(x),
                         "bars_held": int(j - i),
                         "outcome": "horizon" if j == i + horizon else "open",
                         "ret": float(x / e * (1 - cost) ** 2 - 1)})
    return pl.DataFrame(rows).sort("entry_time") if rows else pl.DataFrame()


def mean_reversion_trades(panel: pl.DataFrame, cost: float, cap: int) -> pl.DataFrame:
    """Exit on the first close above the previous bar's high — the Connors exit.

    Included as a second, differently shaped exit. It is still uniform across arms, so it
    cannot reintroduce the stop-distance confound a price-based stop would; `cap` bounds
    a trade that never gets its up-close so one bad entry cannot hold a slot for years.
    """
    rows = []
    for (symbol,), part in panel.group_by("symbol", maintain_order=True):
        part = part.sort("date")
        signal = part["signal"].to_numpy()
        close, high = part["close"].to_numpy(), part["high"].to_numpy()
        stamp = part["date"].cast(pl.Datetime("us")).dt.epoch("us").to_numpy()
        n = len(close)
        for i in np.flatnonzero(signal):
            if i >= n - 1 or not np.isfinite(close[i]) or close[i] <= 0:
                continue
            j, outcome = None, "exit"
            for k in range(i + 1, min(i + cap + 1, n)):
                if np.isfinite(high[k - 1]) and close[k] > high[k - 1]:
                    j = k
                    break
            if j is None:
                j = min(i + cap, n - 1)
                outcome = "cap"
            rows.append({"symbol": symbol, "entry_time": int(stamp[i]),
                         "exit_time": int(stamp[j]), "entry": float(close[i]),
                         "exit": float(close[j]), "bars_held": int(j - i),
                         "outcome": outcome,
                         "ret": float(close[j] / close[i] * (1 - cost) ** 2 - 1)})
    return pl.DataFrame(rows).sort("entry_time") if rows else pl.DataFrame()


def deployment(trades: pl.DataFrame, grid: np.ndarray, slots: int) -> float:
    """Share of capital actually at work — a part-time book is not a low-risk one."""
    entry_i = np.searchsorted(grid, trades["entry_time"].to_numpy())
    exit_i = np.searchsorted(grid, trades["exit_time"].to_numpy())
    starts: dict[int, list[int]] = {}
    for k, t in enumerate(entry_i):
        starts.setdefault(int(t), []).append(int(exit_i[k]))
    count = np.zeros(len(grid))
    held: list[int] = []
    for t in range(len(grid)):
        if held:
            held = [e for e in held if e > t]
        for exit_at in starts.get(t, ()):
            if len(held) >= slots:
                break
            held.append(exit_at)
        count[t] = len(held)
    return float(count.mean() / slots)


def run_arm(name: str, panel: pl.DataFrame, prices: pl.DataFrame, grid: np.ndarray,
            years: float, args, cost: float) -> dict | None:
    signals = int(panel["signal"].sum())
    if not signals:
        print(f"  {name:<11} no signals")
        return None
    trades = (horizon_trades(panel, cost, args.horizon) if args.exit == "horizon"
              else mean_reversion_trades(panel, cost, args.cap))
    if trades.is_empty():
        print(f"  {name:<11} {signals:,} signals, none resolvable")
        return None
    equity, taken, skipped, _, _, _ = simulate(trades, prices, args.slots, cost)
    cagr, maxdd = performance(equity, years)
    closed = trades.filter(pl.col("outcome") != "open")
    wins = closed.filter(pl.col("ret") > 0)
    mean = float(closed["ret"].mean())
    se = float(closed["ret"].std()) / np.sqrt(closed.height) if closed.height > 1 else np.nan
    mid = grid[len(grid) // 2]
    h1 = closed.filter(pl.col("entry_time") < mid)["ret"].mean()
    h2 = closed.filter(pl.col("entry_time") >= mid)["ret"].mean()
    return {
        "arm": name, "signals": signals, "taken": taken,
        "win_rate_pct": round(wins.height / max(closed.height, 1) * 100, 1),
        "mean_trade_pct": round(mean * 100, 3), "se_pct": round(se * 100, 3),
        "median_hold": int(trades["bars_held"].median()),
        "cagr_pct": round(cagr * 100, 2), "max_drawdown_pct": round(maxdd * 100, 2),
        "deployed_pct": round(deployment(trades, grid, args.slots) * 100, 1),
        "final_equity": round(float(equity[-1]), 3),
        "h1_mean_pct": round(float(h1) * 100, 3) if h1 is not None else None,
        "h2_mean_pct": round(float(h2) * 100, 3) if h2 is not None else None,
        "vs_random_sigma": None, "_mean": mean, "_se": se,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--universe", default="nifty500")
    parser.add_argument("--arms", nargs="+", default=list(ARMS), choices=ARMS)
    parser.add_argument("--exit", choices=("horizon", "mr"), default="horizon")
    parser.add_argument("--horizon", type=int, default=10,
                        help="horizon exit: bars held, unconditionally (default 10)")
    parser.add_argument("--cap", type=int, default=40,
                        help="mr exit: give up after this many bars without an up-close")
    parser.add_argument("--start", default="2015-01-01",
                        help="the daily panel is thin before ~2015; earlier windows rank "
                             "survivors rather than the market")
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--oversold", type=float, default=30.0)
    parser.add_argument("--bb", type=int, default=20)
    parser.add_argument("--bb-width", type=float, default=2.0)
    parser.add_argument("--squeeze-pct", type=float, default=0.20,
                        help="bandwidth quantile, measured against the symbol's own "
                             "trailing 250 bars, that counts as squeezed")
    parser.add_argument("--sma", type=int, default=200)
    parser.add_argument("--confirm", type=int, default=3)
    parser.add_argument("--min-sep", type=int, default=5)
    parser.add_argument("--max-sep", type=int, default=40)
    parser.add_argument("--max-age", type=int, default=5)
    parser.add_argument("--confluence-window", type=int, default=5,
                        help="bars within which the combo arm's components must all have "
                             "fired. Requiring them on one bar is a different and much "
                             "rarer event than the confluence a trader actually waits for")
    parser.add_argument("--slots", type=int, default=10)
    parser.add_argument("--min-bars", type=int, default=500)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--random-draws", type=int, default=50_000)
    parser.add_argument("--random-seed", type=int, default=7)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    cost = args.cost_bps / 10_000

    universe = pl.read_parquet(UNIVERSE).filter(pl.col(f"in_{args.universe}"))
    symbols = universe["symbol"].to_list()
    panel = (pl.scan_parquet(DAILY_GLOB, hive_partitioning=True)
             .filter(pl.col("symbol").is_in(symbols))
             .select("symbol", "date", "open", "high", "low", "close")
             .drop_nulls("close")
             .collect())
    if args.start:
        panel = panel.filter(pl.col("date") >= pl.lit(args.start).str.to_date())
    counts = panel.group_by("symbol").len().filter(pl.col("len") >= args.min_bars)
    panel = panel.filter(pl.col("symbol").is_in(counts["symbol"].implode())).sort("symbol", "date")
    print(f"{args.universe}: {panel.height:,} daily bars, "
          f"{panel['symbol'].n_unique()} symbols, "
          f"{panel['date'].min()} -> {panel['date'].max()}")

    panel = attach(panel, args.rsi_period, args.bb, args.bb_width,
                   args.squeeze_pct, args.sma)
    settle = max(args.rsi_period * 3, args.bb * 3, 250)
    parts = []
    for (symbol,), part in panel.group_by("symbol", maintain_order=True):
        part = part.sort("date")
        div = divergence_flags(
            part["rsi"].to_numpy(), part["low"].to_numpy(), confirm=args.confirm,
            min_sep=args.min_sep, max_sep=args.max_sep, max_age=args.max_age,
            settle=settle)
        parts.append(part.with_columns(pl.Series("div", div)))
    panel = pl.concat(parts)
    # "Recently" rather than "on this very bar" for the confluence arm.
    window = args.confluence_window
    panel = panel.with_columns(
        ((pl.col("close_prev") < pl.col("bb_dn_prev")) & (pl.col("close") > pl.col("bb_dn")))
        .cast(pl.Int8).rolling_sum(window).over("symbol").gt(0).alias("_bb_recent"),
        pl.col("div").cast(pl.Int8).rolling_sum(window).over("symbol").gt(0).alias("_div_recent"),
    )
    eligible = pl.col("warm") & pl.col("rsi").is_not_null() & pl.col("bb_dn").is_not_null()

    prices = (panel.select("symbol", "date", "close")
              .with_columns(pl.col("date").cast(pl.Datetime("us")).alias("datetime"))
              .pivot(on="symbol", index="datetime", values="close").sort("datetime"))
    prices = prices.with_columns([pl.col(c).forward_fill().backward_fill()
                                  for c in prices.columns if c != "datetime"])
    grid = prices["datetime"].dt.epoch("us").to_numpy()
    years = float(grid[-1] - grid[0]) / (365.25 * 86400 * 1_000_000)

    matrix = prices.select([c for c in prices.columns if c != "datetime"]).to_numpy()
    listed = ~np.isnan(matrix[0])
    normalised = matrix[:, listed] / matrix[0, listed]
    step = normalised[1:] / np.where(normalised[:-1] == 0, np.nan, normalised[:-1])
    with np.errstate(invalid="ignore"):
        artefact = np.nanmax(np.abs(step - 1.0), axis=0) > 0.50
    bench_cagr, bench_dd = performance(np.nanmean(normalised[:, ~artefact], axis=1), years)
    label = (f"held exactly {args.horizon} bars — no stop, no target"
             if args.exit == "horizon"
             else f"exit on the first close above the previous high (cap {args.cap})")
    print(f"window {prices['datetime'][0]} -> {prices['datetime'][-1]} ({years:.2f} years)")
    print(f"CONTROL equal-weight buy-and-hold ({int(listed.sum())} symbols, fully "
          f"invested): {bench_cagr * 100:+.2f}% CAGR / {bench_dd * 100:.2f}% max DD")
    print(f"\n--- {label} ---")

    summary = []
    for arm in args.arms:
        marked = panel.with_columns((arm_expression(arm, args.oversold) & eligible)
                                    .fill_null(False).alias("signal"))
        if arm == "combo":     # the "recently" version, per --confluence-window
            marked = panel.with_columns(
                ((pl.col("rsi_prev") <= args.oversold) & (pl.col("rsi") > args.oversold)
                 & pl.col("_bb_recent") & pl.col("_div_recent") & eligible)
                .fill_null(False).alias("signal"))
        row = run_arm(arm, marked, prices, grid, years, args, cost)
        if row is None:
            continue
        summary.append(row)
        print(f"  {arm:<11} {row['signals']:>7,} sig  {row['taken']:>6,} taken  "
              f"win {row['win_rate_pct']:>5.1f}%  mean {row['mean_trade_pct']:>+7.3f}%  "
              f"CAGR {row['cagr_pct']:>+7.2f}%  DD {row['max_drawdown_pct']:>7.2f}%  "
              f"deployed {row['deployed_pct']:>5.1f}%")

    rng = np.random.default_rng(args.random_seed)
    ok = np.flatnonzero(panel.with_columns(eligible.fill_null(False).alias("_e"))["_e"].to_numpy())
    picks = np.zeros(panel.height, dtype=bool)
    picks[rng.choice(ok, size=min(args.random_draws, ok.size), replace=False)] = True
    control = panel.with_columns(pl.Series("signal", picks))
    row = run_arm("random", control, prices, grid, years, args, cost)
    if row is not None:
        summary.append(row)
        print(f"  {'random':<11} {row['signals']:>7,} sig  {row['taken']:>6,} taken  "
              f"win {row['win_rate_pct']:>5.1f}%  mean {row['mean_trade_pct']:>+7.3f}%  "
              f"CAGR {row['cagr_pct']:>+7.2f}%  DD {row['max_drawdown_pct']:>7.2f}%  "
              f"deployed {row['deployed_pct']:>5.1f}%   <- control")
        for entry in summary[:-1]:
            spread = np.sqrt(entry["_se"] ** 2 + row["_se"] ** 2)
            entry["vs_random_sigma"] = (round((entry["_mean"] - row["_mean"]) / spread, 2)
                                        if np.isfinite(spread) and spread > 0 else None)

    table = pl.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")}
                          for r in summary])
    print(f"\n{'=' * 100}")
    print("ABLATION — same bars, same exit, same benchmark")
    print(f"{'=' * 100}")
    with pl.Config(tbl_rows=20, tbl_cols=16, tbl_width_chars=200):
        print(table)
    print(f"\nbuy-and-hold control: {bench_cagr * 100:+.2f}% CAGR / {bench_dd * 100:.2f}% "
          f"max DD, fully invested. Read each arm's drawdown against its deployed column.")
    print("Survivorship: today's index membership walked backwards.")
    if args.out:
        table.write_csv(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
