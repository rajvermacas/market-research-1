#!/usr/bin/env python3
"""Backtest of the hourly RSI re-ignition setup, in Polars + NumPy.

The strategy under test:

    entry   the hourly candle where RSI(14) crosses above 60, while
            EMA(RSI,21) < 60 and the daily, weekly and monthly RSI are all > 60
            and market cap > 5000 crore. Filled at that candle's close.
    stop    the *entry candle's low*. Risk per trade is entry-to-that-low.
    target  five times that risk above the entry (1:5 reward:risk).
            The position closes on whichever level a later candle reaches first.
            When one candle spans both, the stop is assumed to fill first — the
            hourly bar does not say which came first, and the alternative
            silently books the win every time the two collide.

Point-in-time discipline, because a screen is not a backtest:

  * The daily/weekly/monthly RSI filters read the last *completed* bar of their
    timeframe (shift of one), so an hourly bar inside day D is judged on the RSI
    through D-1. Using day D's own close would leak the session's outcome into
    the entry decision.
  * Market cap is a *current* number from Yahoo, so it is walked back as
    cap_t = cap_now * close_t / close_now. That assumes share count never
    changed, which is wrong across splits and issuance, but it removes the much
    larger error of applying today's size to a 2023 bar.
  * The universe is NSE's current main board, so the test carries survivorship
    bias: companies delisted during the window are absent. Results are therefore
    optimistic by an unmeasured amount.

Reported against an equal-weight buy-and-hold of the same universe over the same
window, because a return without a control measures the market, not the setup.

Usage:
    python scripts/rsi_backtest.py
    python scripts/rsi_backtest.py --slots 20 --cost-bps 20
    python scripts/rsi_backtest.py --skip-market-cap
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl

from screener import fetch_market_caps
from hourly_rsi_screener import ema
from screener import rsi, resample

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
HOURLY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "hourly" / "**" / "*.parquet")
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CAP_CACHE = REPO_ROOT / ".cache" / "screener" / "market_caps.csv"
BARS_PER_YEAR = 252 * 7  # NSE trades roughly seven hourly bars a session


# --------------------------------------------------------------- point-in-time filters


def prior_bar_rsi(bars: pl.DataFrame, period: int, label: str, column: str) -> pl.DataFrame:
    """RSI of each bar, shifted one bar forward so it is knowable when that bar opens."""
    return (
        bars.sort("symbol", column)
        .with_columns(rsi("close", period).over("symbol").alias(label))
        .with_columns(pl.col(label).shift(1).over("symbol").alias(label))
        .select("symbol", column, label)
        .drop_nulls(label)
    )


def attach_htf(hourly: pl.DataFrame, daily: pl.DataFrame, period: int) -> pl.DataFrame:
    """Join the last completed daily / weekly / monthly RSI onto every hourly bar."""
    out = hourly.with_columns(pl.col("datetime").dt.date().alias("date"))

    day = prior_bar_rsi(daily, period, "rsi_daily", "date")
    out = out.join(day, on=["symbol", "date"], how="inner")

    for label, every in (("rsi_weekly", "1w"), ("rsi_monthly", "1mo")):
        coarse = prior_bar_rsi(resample(daily, every), period, label, "date")
        # as-of: the most recent completed weekly/monthly bar at or before this date
        out = (
            out.sort("date")
            .join_asof(coarse.sort("date"), on="date", by="symbol", strategy="backward")
            .drop_nulls(label)
        )
    return out


def attach_market_cap(bars: pl.DataFrame, daily: pl.DataFrame, caps: pl.DataFrame) -> pl.DataFrame:
    """Walk today's market cap back through the price series (share count held constant)."""
    latest = (
        daily.sort("symbol", "date").group_by("symbol")
        .agg(pl.col("close").last().alias("close_now"))
    )
    ratio = caps.join(latest, on="symbol", how="inner").with_columns(
        (pl.col("market_cap_cr") / pl.col("close_now")).alias("cap_per_price")
    )
    return bars.join(ratio.select("symbol", "cap_per_price"), on="symbol", how="inner") \
               .with_columns((pl.col("close") * pl.col("cap_per_price")).alias("cap_cr"))


# ------------------------------------------------------------------------- trade search


def find_trades(frame: pl.DataFrame, cost: float, reward_risk: float,
                stop_column: str | None = None, stack: bool = True) -> pl.DataFrame:
    """Walk each signal forward to whichever of the stop or the target it reaches first.

    The stop defaults to the entry candle's low. `stop_column` names a column holding a
    stop *price* instead, so a noise-aware stop (an ATR multiple, say) can be tested
    against the structural one without touching the rest of the machinery.

    With `stack` (the default) every signal becomes a candidate trade and how many may be
    live in one symbol is the portfolio's decision, made in simulate(). Suppressing the
    re-entry here instead would be wrong whenever the earlier trade never opened for want
    of a slot: the walk would block a name on the strength of a position that does not
    exist. `stack=False` restores the old one-at-a-time walk for comparison.
    """
    rows = []
    for (symbol,), part in frame.group_by("symbol", maintain_order=True):
        part = part.sort("datetime")
        signal = part["signal"].to_numpy()
        idx = np.flatnonzero(signal)
        if not idx.size:
            continue
        times = part["datetime"].dt.epoch("us").to_numpy()
        high = part["high"].to_numpy()
        low = part["low"].to_numpy()
        stops = part[stop_column].to_numpy() if stop_column else low
        open_ = part["open"].to_numpy()
        close = part["close"].to_numpy()

        last_exit = -1
        for i in idx:
            if not stack and i <= last_exit:   # legacy: one position per symbol at a time
                continue
            stop, entry = stops[i], close[i]
            if not np.isfinite(entry) or entry <= 0 or not np.isfinite(stop) or stop >= entry:
                continue            # a cross closing at its own low leaves no risk to size
            risk = entry - stop
            target = entry + reward_risk * risk

            after_low, after_high = low[i + 1:], high[i + 1:]
            stop_hits = np.flatnonzero(after_low <= stop)
            target_hits = np.flatnonzero(after_high >= target)
            first_stop = stop_hits[0] if stop_hits.size else np.inf
            first_target = target_hits[0] if target_hits.size else np.inf

            if first_stop == np.inf and first_target == np.inf:
                j = len(close) - 1
                exit_price, outcome = close[j], "open"
            elif first_stop <= first_target:   # a tie resolves against us, deliberately
                j = i + 1 + int(first_stop)
                exit_price = open_[j] if open_[j] <= stop else stop
                outcome = "stop"
            else:
                j = i + 1 + int(first_target)
                exit_price = open_[j] if open_[j] >= target else target
                outcome = "target"
            last_exit = j
            rows.append({
                "symbol": symbol,
                "entry_time": int(times[i]), "entry": float(entry),
                "stop": float(stop), "target": float(target),
                "exit_time": int(times[j]), "exit": float(exit_price),
                "outcome": outcome,
                "bars_held": int(j - i),
                "ret": float(exit_price / entry * (1 - cost) ** 2 - 1),
                "risk_pct": float(risk / entry),
            })
    if not rows:
        return pl.DataFrame()
    trades = pl.DataFrame(rows).sort("entry_time")

    # Invariant, only meaningful for the one-at-a-time walk: a backtest that doubles up on
    # a name unintentionally inflates trade count and return together. Under stacking the
    # overlap is deliberate and the cap lives in simulate().
    if stack:
        return trades
    overlap = (
        trades.sort("symbol", "entry_time")
        .with_columns(pl.col("exit_time").shift(1).over("symbol").alias("prev_exit"))
        .filter(pl.col("entry_time") <= pl.col("prev_exit"))
    )
    if overlap.height:
        raise AssertionError(
            f"{overlap.height} re-entries overlap an open position in the same symbol, "
            f"e.g. {overlap['symbol'][0]}"
        )
    return trades


# ---------------------------------------------------------------------------- portfolio


def simulate(trades: pl.DataFrame, prices: pl.DataFrame, slots: int, cost: float,
             per_symbol: int | None = None):
    """Equal-weight portfolio, at most `slots` concurrent positions, marked hourly.

    `per_symbol` caps how many of those may be in one name at once; None is unlimited,
    which lets a trending stock stack several entries — and, at the extreme, occupy every
    slot. `max_stacked` in the return says how far that actually went.
    """
    grid = prices["datetime"].dt.epoch("us").to_numpy()
    symbols = [c for c in prices.columns if c != "datetime"]
    column = {s: i for i, s in enumerate(symbols)}
    matrix = prices.select(symbols).to_numpy()

    entry_at: dict[int, list] = {}
    for row in trades.iter_rows(named=True):
        entry_at.setdefault(int(np.searchsorted(grid, row["entry_time"])), []).append(row)

    cash, open_pos = 1.0, []          # open_pos: [col, shares, exit_index, exit_price]
    equity = np.empty(len(grid))
    taken = skipped = blocked = max_stacked = 0

    for t in range(len(grid)):
        for position in [p for p in open_pos if p[2] == t]:
            cash += position[1] * position[3] * (1 - cost)
            open_pos.remove(position)

        for row in entry_at.get(t, []):
            if len(open_pos) >= slots:
                skipped += 1
                continue
            if per_symbol is not None and sum(
                1 for p in open_pos if p[0] == column[row["symbol"]]
            ) >= per_symbol:
                blocked += 1
                continue
            held = sum(p[1] * matrix[t, p[0]] for p in open_pos)
            allocation = (cash + held) / slots
            if allocation > cash:
                allocation = cash
            if allocation <= 0:
                skipped += 1
                continue
            shares = allocation * (1 - cost) / row["entry"]
            cash -= allocation
            open_pos.append([
                column[row["symbol"]], shares,
                int(np.searchsorted(grid, row["exit_time"])), row["exit"], allocation,
            ])
            taken += 1
            # open_pos already holds the position just appended, so this count is the
            # concurrent depth in that name — it must not be incremented again on the way out.
            same = sum(1 for p in open_pos if p[0] == column[row["symbol"]])
            max_stacked = max(max_stacked, same)

        equity[t] = cash + sum(p[1] * matrix[t, p[0]] for p in open_pos)
    # What the final equity owes to positions never closed: booked at the last mark, not
    # at a real exit. Reported so the reader can discount it.
    unrealised = sum(p[1] * matrix[-1, p[0]] - p[4] for p in open_pos)
    return equity, taken, skipped, blocked, max_stacked, unrealised


def simulate_fixed(trades: pl.DataFrame, prices: pl.DataFrame, notional: float,
                   cost: float):
    """Unlimited cash, a fixed rupee ticket per trade: every signal is taken.

    Nothing compounds — position size never grows with the account — so "return" needs a
    capital base to divide by. The honest one is the most you ever had at risk at once:
    peak concurrent positions x the ticket. That is the cash you must actually possess to
    run the strategy, so the account is modelled as starting there and ending there plus
    total P&L.
    """
    grid = prices["datetime"].dt.epoch("us").to_numpy()
    symbols = [c for c in prices.columns if c != "datetime"]
    column = {s: i for i, s in enumerate(symbols)}
    matrix = prices.select(symbols).to_numpy()

    entry_at: dict[int, list] = {}
    for row in trades.iter_rows(named=True):
        entry_at.setdefault(int(np.searchsorted(grid, row["entry_time"])), []).append(row)

    realised = 0.0
    open_pos: list = []               # [col, shares, exit_index, exit_price]
    pnl = np.empty(len(grid))
    deployed = np.empty(len(grid))
    peak_open = 0

    for t in range(len(grid)):
        for position in [p for p in open_pos if p[2] == t]:
            realised += position[1] * position[3] * (1 - cost) - notional
            open_pos.remove(position)
        for row in entry_at.get(t, []):
            open_pos.append([column[row["symbol"]], notional * (1 - cost) / row["entry"],
                             int(np.searchsorted(grid, row["exit_time"])), row["exit"]])
        peak_open = max(peak_open, len(open_pos))
        unrealised = sum(p[1] * matrix[t, p[0]] - notional for p in open_pos)
        pnl[t] = realised + unrealised
        deployed[t] = len(open_pos) * notional

    base = max(peak_open, 1) * notional
    return pnl, base, peak_open, deployed


def simulate_shared_stop(trades: pl.DataFrame, panels: dict, slots: int, cost: float,
                         per_symbol: int | None = None):
    """Every open position in a symbol closes as soon as *any* of its stops is hit.

    With stacked entries each position normally carries its own stop, so the newest dies
    first and the older ones — sitting on lower stops — survive. Here the symbol is
    treated as one book instead: the effective stop is the highest among its open
    positions, and when price trades through it the whole holding in that name is closed
    at that level.

    That coupling makes an exit depend on what else is open, which depends on which
    signals won a slot, so it cannot be precomputed per trade the way find_trades() does.
    It is resolved here, bar by bar, against the actual highs and lows. Targets stay
    per-position: only the stop is shared. Within a bar the stop is assumed to fill first.
    """
    grid, close_m, open_m, high_m, low_m, column = (
        panels["grid"], panels["close"], panels["open"], panels["high"],
        panels["low"], panels["column"],
    )
    entry_at: dict[int, list] = {}
    for row in trades.iter_rows(named=True):
        entry_at.setdefault(int(np.searchsorted(grid, row["entry_time"])), []).append(row)

    cash = 1.0
    open_pos: list[dict] = []
    equity = np.empty(len(grid))
    closed: list[dict] = []
    taken = skipped = blocked = max_stacked = 0

    for t in range(len(grid)):
        by_col: dict[int, list] = {}
        for position in open_pos:
            by_col.setdefault(position["col"], []).append(position)

        for col, group in by_col.items():
            lo, op, hi = low_m[t, col], open_m[t, col], high_m[t, col]
            effective = max(p["stop"] for p in group)
            if not np.isnan(lo) and lo <= effective:
                fill = op if (not np.isnan(op) and op <= effective) else effective
                for position in group:            # the whole name goes, not just one leg
                    cash += position["shares"] * fill * (1 - cost)
                    closed.append({**position, "exit": fill, "exit_time": int(grid[t]),
                                   "outcome": "stop", "bars_held": t - position["entry_idx"]})
                    open_pos.remove(position)
                continue
            for position in group:
                if not np.isnan(hi) and hi >= position["target"]:
                    fill = op if (not np.isnan(op) and op >= position["target"]) \
                        else position["target"]
                    cash += position["shares"] * fill * (1 - cost)
                    closed.append({**position, "exit": fill, "exit_time": int(grid[t]),
                                   "outcome": "target", "bars_held": t - position["entry_idx"]})
                    open_pos.remove(position)

        for row in entry_at.get(t, []):
            if len(open_pos) >= slots:
                skipped += 1
                continue
            col = column[row["symbol"]]
            if per_symbol is not None and sum(1 for p in open_pos if p["col"] == col) >= per_symbol:
                blocked += 1
                continue
            held = sum(p["shares"] * close_m[t, p["col"]] for p in open_pos)
            allocation = min((cash + held) / slots, cash)
            if allocation <= 0:
                skipped += 1
                continue
            cash -= allocation
            open_pos.append({"col": col, "symbol": row["symbol"],
                             "shares": allocation * (1 - cost) / row["entry"],
                             "entry": row["entry"], "stop": row["stop"],
                             "target": row["target"], "entry_time": row["entry_time"],
                             "entry_idx": t})
            taken += 1
            max_stacked = max(max_stacked, sum(1 for p in open_pos if p["col"] == col))

        equity[t] = cash + sum(p["shares"] * close_m[t, p["col"]] for p in open_pos)

    for position in open_pos:
        closed.append({**position, "exit": close_m[-1, position["col"]],
                       "exit_time": int(grid[-1]), "outcome": "open",
                       "bars_held": len(grid) - 1 - position["entry_idx"]})
    unrealised = sum(p["shares"] * close_m[-1, p["col"]]
                     - p["shares"] * p["entry"] for p in open_pos)
    frame = pl.DataFrame([{k: v for k, v in c.items() if k not in ("col", "entry_idx")}
                          for c in closed])
    if frame.height:
        frame = frame.with_columns(
            (pl.col("exit") / pl.col("entry") * (1 - cost) ** 2 - 1).alias("ret"),
            ((pl.col("entry") - pl.col("stop")) / pl.col("entry")).alias("risk_pct"))
    return equity, taken, skipped, blocked, max_stacked, frame, unrealised


def performance(equity: np.ndarray, bars: int) -> tuple[float, float]:
    years = bars / BARS_PER_YEAR
    cagr = equity[-1] ** (1 / years) - 1
    drawdown = equity / np.maximum.accumulate(equity) - 1
    return cagr, drawdown.min()


# ------------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--universe", default="nse_all")
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--ema-span", type=int, default=21)
    parser.add_argument("--cross-level", type=float, default=60.0)
    parser.add_argument("--ema-max", type=float, default=53.0)
    parser.add_argument("--htf-min", type=float, default=60.0)
    parser.add_argument("--market-cap-min", type=float, default=5000.0)
    parser.add_argument("--reward-risk", type=float, nargs="+", default=[1, 2, 3, 4, 5],
                        help="target as a multiple of risk; several sweeps them (default 1..5)")
    parser.add_argument("--slots", type=int, default=10,
                        help="max concurrent positions (default 10)")
    parser.add_argument("--skip-daily-rsi", action="store_true",
                        help="drop the daily RSI > htf-min condition, keeping only the "
                             "weekly and monthly regime filters")
    parser.add_argument("--shared-stop", action="store_true",
                        help="one stop hit closes EVERY open position in that symbol, "
                             "instead of only the leg whose own stop was hit")
    parser.add_argument("--fixed-notional", type=float, default=None,
                        help="unlimited cash, this many rupees per trade; every signal is "
                             "taken and nothing compounds (e.g. 100000 for 1 lakh)")
    parser.add_argument("--per-symbol", type=int, default=None,
                        help="max concurrent positions in ONE symbol; omit for unlimited, "
                             "so a signal re-enters a name whose earlier trade is still open")
    parser.add_argument("--cost-bps", type=float, default=10.0,
                        help="one-way cost in basis points (default 10 = 0.20%% round trip)")
    parser.add_argument("--skip-market-cap", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    cost = args.cost_bps / 10_000

    universe = pl.read_parquet(UNIVERSE)
    if args.universe != "nse_all":
        universe = universe.filter(pl.col(f"in_{args.universe}"))
    symbols = universe["symbol"].to_list()

    daily = (pl.scan_parquet(DAILY_GLOB, hive_partitioning=True)
             .filter(pl.col("symbol").is_in(symbols))
             .select("symbol", "date", "open", "high", "low", "close", "volume")
             .collect())
    hourly = (pl.scan_parquet(HOURLY_GLOB, hive_partitioning=True)
              .filter(pl.col("symbol").is_in(symbols))
              .select("symbol", "datetime", "open", "high", "low", "close")
              .collect())
    print(f"universe {universe.height} | daily {daily.height:,} rows | "
          f"hourly {hourly.height:,} rows")

    print("\nbuilding point-in-time filters")
    frame = hourly.sort("symbol", "datetime").with_columns(
        rsi("close", args.rsi_period).over("symbol").alias("rsi_h")
    )
    frame = frame.with_columns(
        ema("rsi_h", args.ema_span).over("symbol").alias("rsi_ema"),
        pl.col("rsi_h").shift(1).over("symbol").alias("rsi_prev"),
    )
    frame = attach_htf(frame, daily, args.rsi_period)

    if args.skip_market_cap:
        frame = frame.with_columns(pl.lit(1e9).alias("cap_cr"))
        print("  market cap filter SKIPPED")
    else:
        if CAP_CACHE.exists():
            caps = pl.read_csv(CAP_CACHE)
            print(f"  market caps from cache ({caps.height} symbols)")
        else:
            caps = fetch_market_caps(symbols)
            CAP_CACHE.parent.mkdir(parents=True, exist_ok=True)
            caps.write_csv(CAP_CACHE)
            print(f"  fetched market caps ({caps.height} symbols)")
        if caps.is_empty():
            print("  market cap lookup empty — refusing to run a size-filtered test "
                  "without sizes. Re-run later or pass --skip-market-cap.", file=sys.stderr)
            return 1
        frame = attach_market_cap(frame, daily, caps)

    frame = frame.with_columns(
        ((pl.col("rsi_prev") <= args.cross_level)
         & (pl.col("rsi_h") > args.cross_level)
         & (pl.col("rsi_ema") < args.ema_max)
         & (pl.lit(True) if args.skip_daily_rsi
            else (pl.col("rsi_daily") > args.htf_min))
         & (pl.col("rsi_weekly") > args.htf_min)
         & (pl.col("rsi_monthly") > args.htf_min)
         & (pl.col("cap_cr") > args.market_cap_min)).alias("signal")
    ).sort("symbol", "datetime")
    print(f"  {frame['signal'].sum():,} entry signals")

    # Signals do not depend on the target, so the price grid and the control are built
    # once and only the forward walk to the exit is repeated per reward:risk ratio.
    signal_symbols = frame.filter(pl.col("signal"))["symbol"].unique().to_list()
    prices = (hourly.filter(pl.col("symbol").is_in(signal_symbols))
              .select("symbol", "datetime", "close")
              .pivot(on="symbol", index="datetime", values="close")
              .sort("datetime"))
    prices = prices.with_columns(
        [pl.col(c).forward_fill().backward_fill() for c in prices.columns if c != "datetime"]
    )
    bars = prices.height

    panels = None
    if args.shared_stop:
        # A shared stop resolves against real highs and lows, so those panels are needed
        # too. Deliberately left un-filled: a bar the symbol did not trade is NaN, and NaN
        # comparisons are False, so a missing bar can never trigger a stop.
        traded_cols = [c for c in prices.columns if c != "datetime"]
        panels = {"grid": prices["datetime"].dt.epoch("us").to_numpy(),
                  "column": {c: i for i, c in enumerate(traded_cols)},
                  "close": prices.select(traded_cols).to_numpy()}
        for field in ("open", "high", "low"):
            wf = (hourly.filter(pl.col("symbol").is_in(signal_symbols))
                  .select("symbol", "datetime", field)
                  .pivot(on="symbol", index="datetime", values=field).sort("datetime"))
            panels[field] = wf.select(traded_cols).to_numpy()

    # Control: equal-weight buy-and-hold of every symbol already trading at the start of
    # the window. Forward-filling first is essential — a handful of timestamps carry a bar
    # for only one or two symbols, and an unfilled mean over those is a single stock's
    # price masquerading as the market.
    wide = (hourly.select("symbol", "datetime", "close")
            .pivot(on="symbol", index="datetime", values="close").sort("datetime"))
    wide = wide.with_columns(
        [pl.col(c).forward_fill() for c in wide.columns if c != "datetime"]
    )
    matrix = wide.select([c for c in wide.columns if c != "datetime"]).to_numpy()
    listed = ~np.isnan(matrix[0])
    normalised = matrix[:, listed] / matrix[0, listed]
    # The *median* constituent, not the mean. A handful of micro caps in this panel show
    # impossible excursions (SUPREMEENG peaks at 2061x its 2023 price, ANTGRAPHIC at
    # 1656x) — almost certainly unadjusted corporate actions upstream rather than real
    # returns. They are reported by validate_data.py and left in the data, but an
    # equal-weight mean of ratios lets two such names dictate the whole benchmark.
    bench = np.nanmedian(normalised, axis=1)
    bench_cagr, bench_dd = performance(bench, len(bench))
    mean_bench = np.nanmean(normalised, axis=1)
    mean_cagr, mean_dd = performance(mean_bench, len(mean_bench))
    print(f"control basket: {int(listed.sum()):,} symbols trading at the window start "
          f"(median constituent; the outlier-driven mean would read "
          f"{mean_cagr * 100:+.2f}% / {mean_dd * 100:.2f}%)")

    print(f"\nwindow {prices['datetime'][0]} -> {prices['datetime'][-1]}"
          f"  ({bars:,} hourly bars, {bars / BARS_PER_YEAR:.2f} years)")

    summary = []
    for reward_risk in args.reward_risk:
        print(f"\n--- stop at the entry low, target at 1:{reward_risk:g} ---")
        trades = find_trades(frame, cost, reward_risk)
        if trades.is_empty():
            print("  no trades"); continue
        if args.shared_stop:
            equity, taken, skipped, blocked, max_stacked, closed_frame, unrealised = \
                simulate_shared_stop(trades, panels, args.slots, cost, args.per_symbol)
            trades = closed_frame
        elif args.fixed_notional:
            pnl, base, peak_open, deployed = simulate_fixed(
                trades, prices, args.fixed_notional, cost)
            equity = (base + pnl) / base       # normalise so CAGR/DD read as usual
            taken, skipped, blocked, max_stacked, unrealised = trades.height, 0, 0, 0, 0.0
        else:
            equity, taken, skipped, blocked, max_stacked, unrealised = simulate(
                trades, prices, args.slots, cost, args.per_symbol)
        cagr, maxdd = performance(equity, bars)
        closed = trades.filter(pl.col("outcome") != "open")
        wins = closed.filter(pl.col("ret") > 0).height
        hit = {o: trades.filter(pl.col("outcome") == o).height for o in ("target", "stop", "open")}
        if args.fixed_notional:
            print(f"  {trades.height:,} signals, ALL taken | peak {peak_open} positions "
                  f"open at once = Rs {base:,.0f} capital needed | "
                  f"avg deployed Rs {deployed.mean():,.0f}")
            print(f"  total P&L Rs {pnl[-1]:,.0f} on Rs {base:,.0f} base "
                  f"({pnl[-1] / base * 100:+.1f}% over the window)")
        print(f"  {trades.height:,} signals, {taken:,} taken, {skipped:,} skipped "
              f"(no free slot at {args.slots})"
              + (f", {blocked:,} blocked by the {args.per_symbol}/symbol cap"
                 if args.per_symbol else "")
              + f" | deepest stack in one name: {max_stacked}") if not args.fixed_notional else None
        print(f"  target {hit['target']:,} | stop {hit['stop']:,} | still open {hit['open']:,}")
        print(f"  win rate {wins / max(closed.height, 1):.1%}  "
              f"mean trade {closed['ret'].mean() * 100:+.2f}%  "
              f"median hold {trades['bars_held'].median():.0f} bars")
        print(f"  CAGR {cagr * 100:+.2f}%   max drawdown {maxdd * 100:.2f}%   "
              f"final equity x{equity[-1]:.3f}")
        # How much of the result rests on a handful of trades, and does it survive being
        # cut in half? A wide target wins rarely, so the whole edge can sit in a few
        # outliers that a different three years would not have produced.
        mid = prices["datetime"][prices.height // 2].timestamp() * 1_000_000
        h1 = closed.filter(pl.col("entry_time") < mid)
        h2 = closed.filter(pl.col("entry_time") >= mid)
        ranked = closed["ret"].sort(descending=True)
        top10 = float(ranked.head(10).sum())
        gross = float(ranked.filter(ranked > 0).sum())
        print(f"  unrealised in final equity: {unrealised:+.4f} of x{equity[-1]:.3f} "
              f"({unrealised / (equity[-1] - 1) * 100:.1f}% of the total gain)"
              if abs(equity[-1] - 1) > 1e-9 else "  unrealised: n/a")
        print(f"  half-split mean trade: h1 {float(h1['ret'].mean()) * 100:+.3f}%  "
              f"h2 {float(h2['ret'].mean()) * 100:+.3f}%"
              f"   | top 10 winners = {top10 / gross:.0%} of all gains")
        summary.append({
            "reward_risk": f"1:{reward_risk:g}", "trades": trades.height, "taken": taken,
            "target_hits": hit["target"], "stopped": hit["stop"], "open_at_end": hit["open"],
            "win_rate_pct": round(wins / max(closed.height, 1) * 100, 1),
            "mean_trade_pct": round(float(closed["ret"].mean()) * 100, 3),
            "cagr_pct": round(cagr * 100, 2), "max_drawdown_pct": round(maxdd * 100, 2),
            "final_equity": round(float(equity[-1]), 3),
            "h1_mean_pct": round(float(h1["ret"].mean()) * 100, 3),
            "h2_mean_pct": round(float(h2["ret"].mean()) * 100, 3),
            "top10_share_pct": round(top10 / gross * 100, 1),
            "max_stacked": max_stacked,
        })
        if args.out:
            trades.write_csv(f"{args.out.rstrip('.csv')}_rr{reward_risk:g}.csv")

    table = pl.DataFrame(summary)
    print(f"\n{'=' * 78}")
    print(f"REWARD:RISK SWEEP — stop always at the entry candle's low")
    print(f"{'=' * 78}")
    with pl.Config(tbl_rows=20, tbl_width_chars=160):
        print(table)
    print(f"\nCONTROL  equal-weight buy-and-hold, same universe and window:")
    print(f"         CAGR {bench_cagr * 100:+.2f}%   max drawdown {bench_dd * 100:.2f}%")
    print(f"{'=' * 78}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
