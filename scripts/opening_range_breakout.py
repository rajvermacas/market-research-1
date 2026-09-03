#!/usr/bin/env python3
"""Opening range breakout on Nifty equity, and the claim that it stopped working.

The source states its rules plainly, so they are tested as written rather than inferred:

    range   the high and low printed between the open and time X
    long    buy when price breaks ABOVE that range high, any time after X
    flip    the same but buying when price breaks BELOW the range low
    exit    the close of the same day, always. Nothing is held overnight.

and it states a result to check against: on the S&P 500 the best average gain per trade
was 0.04%, the win rate was low, and the downside-breakout flip was worse still. The
headline was that opening range breakouts "don't work very well anymore", so the time
split matters as much as the average and is reported separately.

Traded on the corporate-action-adjusted Kite 60-minute Nifty 500 panel. That granularity
is a real limitation and it is stated rather than hidden: NSE's session gives seven hourly
bars (09:15 through 15:15), so the opening range can only be defined in whole hours and a
breakout is detected by a later bar's high clearing the level, not tick by tick. The fill
is taken at the level itself, or at the bar's open when it gapped straight through — the
same convention the rest of this repository uses, and the conservative one.

Controls, because a return without one measures the market:

  * random entries — a randomly chosen bar of the same day, held to the same close, drawn
    only from bars the strategy could itself have entered on. This is the control that
    matters here: every arm exits at the close, so a positive average may be nothing more
    than the fact that Indian equity drifted up over the window.
  * buy-and-hold of the same universe over the same window.

Usage:
    python scripts/opening_range_breakout.py
    python scripts/opening_range_breakout.py --direction down --range-bars 1 2 3
    python scripts/opening_range_breakout.py --universe nifty50 --slots 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

from rsi_backtest import performance

REPO_ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"


def load_panel(panel_dir: str, universe: str, start: str | None) -> pl.DataFrame:
    """Intraday bars for the universe, with the defective prints nulled.

    Same guard as supertrend_rsi_w.py and for the same reason: clean_kite_panel.py nulls
    non-positive closes only, so zero opens and lows, broken OHLC ordering and mid-bar
    split breaks all survive into the "clean" panel. A zero low is the lowest possible low
    and would register as a breakout of every range ever drawn.
    """
    names = pl.read_parquet(UNIVERSE)
    if universe != "nse_all":
        names = names.filter(pl.col(f"in_{universe}"))
    glob = str(REPO_ROOT / "data" / "ohlcv" / panel_dir / "**" / "*.parquet")
    panel = (pl.scan_parquet(glob, hive_partitioning=True)
             .filter(pl.col("symbol").is_in(names["symbol"].implode()))
             .select("symbol", "datetime", "open", "high", "low", "close")
             .drop_nulls("close")
             .collect())
    if start:
        panel = panel.filter(pl.col("datetime").dt.date() >= pl.lit(start).str.to_date())

    body_high = pl.max_horizontal("open", "close")
    body_low = pl.min_horizontal("open", "close")
    broken = ((pl.col("open") <= 0) | (pl.col("high") <= 0) | (pl.col("low") <= 0)
              | (pl.col("high") < pl.col("low")) | (pl.col("high") < body_high)
              | (pl.col("low") > body_low)
              | (((pl.col("high") - pl.col("low")) / pl.col("close")) > 0.50))
    bad = panel.filter(broken).height
    if bad:
        print(f"  {bad:,} defective bars nulled, not repaired (upstream)")
        panel = panel.with_columns([
            pl.when(broken).then(None).otherwise(pl.col(k)).alias(k)
            for k in ("open", "high", "low")])
    return panel.sort("symbol", "datetime")


def orb_trades(frame: pl.DataFrame, range_bars: int, direction: str,
               cost: float, mode: str = "orb", seed: int = 7) -> pl.DataFrame:
    """One trade per symbol-day: break the opening range, exit at that day's close.

    Written as window expressions rather than a per-day loop. The panel holds well over a
    million symbol-days and looping over them in Python takes longer than every other
    backtest in this repository put together.

    `mode="random"` replaces the breakout test with a randomly chosen eligible bar of the
    same day, keeping everything else identical — same universe, same days, same
    close-of-day exit. Without it, "the average trade was positive" says only that the
    market rose over the window.
    """
    by = ["symbol", "date"]
    out = frame.with_columns(
        pl.int_range(pl.len()).over(by).alias("bar"),
        pl.len().over(by).alias("n_bars"),
    )
    head = pl.col("bar") < range_bars
    out = out.with_columns(
        pl.col("high").filter(head).max().over(by).alias("or_high"),
        pl.col("low").filter(head).min().over(by).alias("or_low"),
        pl.col("high").filter(head).is_finite().all().over(by).alias("or_ok_h"),
        pl.col("low").filter(head).is_finite().all().over(by).alias("or_ok_l"),
        pl.col("close").last().over(by).alias("day_close"),
    )
    # An entry bar comes after the range and before the exit bar; the last bar is the exit.
    eligible = (
        (pl.col("bar") >= range_bars)
        & (pl.col("bar") < pl.col("n_bars") - 1)
        & (pl.col("n_bars") >= range_bars + 2)
        & pl.col("or_ok_h") & pl.col("or_ok_l")
        & pl.col("day_close").is_finite() & (pl.col("day_close") > 0)
    )

    if mode == "random":
        rng = np.random.default_rng(seed)
        out = out.with_columns(pl.Series("_r", rng.random(out.height)))
        usable = eligible & pl.col("close").is_finite() & (pl.col("close") > 0)
        out = out.with_columns(
            (usable & (pl.col("_r") == pl.col("_r").filter(usable).min().over(by)))
            .fill_null(False).alias("_take"),
            pl.col("close").alias("_entry"))
    else:
        level = pl.col("or_high") if direction == "up" else pl.col("or_low")
        broke = (eligible & (pl.col("high") >= level) if direction == "up"
                 else eligible & (pl.col("low") <= level))
        first = broke & (broke.cast(pl.Int8).cum_sum().over(by) == 1)
        gap = pl.col("open")
        # Filled at the level, unless the bar opened straight through it — then the open
        # is the honest fill, and it is the worse one.
        entry = (pl.when(gap.is_finite() & (gap > level)).then(gap).otherwise(level)
                 if direction == "up"
                 else pl.when(gap.is_finite() & (gap < level)).then(gap).otherwise(level))
        out = out.with_columns(first.fill_null(False).alias("_take"),
                               entry.alias("_entry"))

    return (out.filter(pl.col("_take")
                       & pl.col("_entry").is_finite() & (pl.col("_entry") > 0))
            .select("symbol", "date",
                    pl.col("_entry").alias("entry"),
                    pl.col("day_close").alias("exit"),
                    (pl.col("n_bars") - 1 - pl.col("bar")).alias("bars_held"),
                    (pl.col("day_close") / pl.col("_entry") * (1 - cost) ** 2 - 1)
                    .alias("ret")))


def daily_curve(trades: pl.DataFrame, days: list, slots: int,
                seed: int = 7) -> tuple[np.ndarray, float, float]:
    """Equal-weight the day's signals, everything flat overnight.

    A day-trading rule needs a day-shaped portfolio: each taken trade gets an equal share
    of equity, and the book is in cash between sessions. Modelling it with the multi-day
    simulator would misreport both the compounding and the exposure.

    `slots = 0` takes every signal of the day, equal weight, and is the default here
    because the rule fires on hundreds of names a session. When `slots` is positive and
    the day is oversubscribed the survivors are drawn AT RANDOM, not taken in frame order:
    the panel is sorted by symbol, so first-come-first-served would silently build a
    portfolio of the alphabetically earliest tickers and report its return as the
    strategy's. That is a selection effect, not a result, and it was visible as a positive
    CAGR sitting on top of a negative mean trade.
    """
    rng = np.random.default_rng(seed)
    index = {d: k for k, d in enumerate(days)}
    per_day: dict[int, list[float]] = {}
    for row in trades.iter_rows(named=True):
        k = index.get(row["date"])
        if k is not None:
            per_day.setdefault(k, []).append(row["ret"])

    equity = np.ones(len(days))
    level, filled, capacity = 1.0, 0, 0
    for k in range(len(days)):
        today = per_day.get(k, [])
        if slots and len(today) > slots:
            today = list(rng.choice(today, size=slots, replace=False))
        if today:
            level *= 1.0 + float(np.mean(today))    # equal weight across what was taken
        equity[k] = level
        filled += len(today)
        capacity += slots if slots else max(len(per_day.get(k, [])), 1)
    return equity, filled / max(capacity, 1), filled / max(len(days), 1)


def breadth_profile(trades: pl.DataFrame) -> dict:
    """Split the signal's return by how many names fired that day.

    This is the column that decides whether a day-trading result is real. A book that
    equal-weights each day's signals gives every session the same vote regardless of how
    many opportunities it held, so its compounded curve is a DAY-weighted mean, while the
    average signal is a TRADE-weighted one. When those two disagree the strategy is paying
    on the days it barely trades and losing on the days it trades most — which is a
    negative-skew profile that a headline CAGR hides completely. The downside-breakout arm
    here posts +15% CAGR and a NEGATIVE average trade for exactly that reason.
    """
    per = (trades.group_by("date")
           .agg(pl.len().alias("n"), pl.col("ret").mean().alias("m")).sort("date"))
    n, m = per["n"].to_numpy(), per["m"].to_numpy()
    if not len(n):
        return {}
    out = {"day_weighted_pct": round(float(m.mean()) * 100, 4),
           "median_signals_per_day": int(np.median(n))}
    for lo, hi, key in ((0.0, 0.5, "quiet"), (0.5, 0.9, "normal"), (0.9, 1.0, "heavy")):
        sel = (n >= np.quantile(n, lo)) & (n <= np.quantile(n, hi))
        out[f"{key}_days_pct"] = (round(float(m[sel].mean()) * 100, 4)
                                  if sel.any() else None)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--panel", default="60minute_kite_clean")
    parser.add_argument("--universe", default="nifty500")
    parser.add_argument("--range-bars", type=int, nargs="+", default=[1, 2, 3, 4],
                        help="hours of the session that define the opening range")
    parser.add_argument("--direction", choices=("up", "down", "both"), default="both")
    parser.add_argument("--slots", type=int, default=0,
                        help="max positions a day; 0 (the default) takes every signal "
                             "equal-weight, which is what this rule implies — it fires on "
                             "hundreds of names a session. A positive value samples the "
                             "day's signals at RANDOM rather than in frame order")
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--start", default=None)
    parser.add_argument("--random-seed", type=int, default=7)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    cost = args.cost_bps / 10_000

    panel = load_panel(args.panel, args.universe, args.start)
    frame = panel.with_columns(pl.col("datetime").dt.date().alias("date"))
    days = sorted(frame["date"].unique().to_list())
    years = (days[-1] - days[0]).days / 365.25
    print(f"{args.universe} on {args.panel}: {panel.height:,} bars, "
          f"{panel['symbol'].n_unique()} symbols, {days[0]} -> {days[-1]} "
          f"({len(days):,} sessions, {years:.2f} years)")

    # Equal-weight buy-and-hold of the names trading at the window start: the MEAN of
    # normalised closes, never the median, which is not tradeable and reads low.
    wide = (frame.group_by("symbol", "date").agg(pl.col("close").last())
            .pivot(on="symbol", index="date", values="close").sort("date"))
    wide = wide.with_columns([pl.col(c).forward_fill()
                              for c in wide.columns if c != "date"])
    matrix = wide.select([c for c in wide.columns if c != "date"]).to_numpy()
    listed = ~np.isnan(matrix[0])
    normalised = matrix[:, listed] / matrix[0, listed]
    step = normalised[1:] / np.where(normalised[:-1] == 0, np.nan, normalised[:-1])
    with np.errstate(invalid="ignore"):
        artefact = np.nanmax(np.abs(step - 1.0), axis=0) > 0.50
    bench_cagr, bench_dd = performance(np.nanmean(normalised[:, ~artefact], axis=1), years)
    print(f"CONTROL equal-weight buy-and-hold ({int(listed.sum())} symbols, fully "
          f"invested): {bench_cagr * 100:+.2f}% CAGR / {bench_dd * 100:.2f}% max DD "
          f"(ret/DD {abs(bench_cagr / bench_dd):.2f})")

    directions = ["up", "down"] if args.direction == "both" else [args.direction]
    mid = days[len(days) // 2]
    summary = []
    print(f"\n{'arm':<18}{'trades':>9}{'win%':>7}{'mean%':>9}{'se%':>7}{'sigma':>7}"
          f"{'CAGR%':>8}{'maxDD%':>9}{'ret/DD':>8}{'dayW%':>8}{'quiet%':>8}{'heavy%':>8}")
    print("-" * 105)
    for direction in directions:
        for bars in args.range_bars:
            control = orb_trades(frame, bars, direction, cost, mode="random",
                                 seed=args.random_seed)
            for label, trades in ((f"{direction} {bars}h", orb_trades(frame, bars,
                                                                     direction, cost)),
                                  (f"random {bars}h", control)):
                if trades.is_empty():
                    print(f"{label:<18} no trades")
                    continue
                equity, deployed, per_day = daily_curve(trades, days, args.slots,
                                                        args.random_seed)
                cagr, maxdd = performance(equity, years)
                ret = trades["ret"]
                mean, se = float(ret.mean()), float(ret.std()) / np.sqrt(trades.height)
                h1 = trades.filter(pl.col("date") < mid)["ret"].mean()
                h2 = trades.filter(pl.col("date") >= mid)["ret"].mean()
                summary.append({
                    "arm": label, "trades": trades.height,
                    "win_rate_pct": round(float((ret > 0).mean()) * 100, 1),
                    "mean_trade_pct": round(mean * 100, 4), "se_pct": round(se * 100, 4),
                    "cagr_pct": round(cagr * 100, 2),
                    "max_drawdown_pct": round(maxdd * 100, 2),
                    "ret_per_dd": round(abs(cagr / maxdd), 2) if maxdd else None,
                    "deployed_pct": round(deployed * 100, 1),
                    "positions_per_day": round(per_day, 1),
                    "h1_mean_pct": round(float(h1) * 100, 4) if h1 is not None else None,
                    "h2_mean_pct": round(float(h2) * 100, 4) if h2 is not None else None,
                    **breadth_profile(trades),
                    "_mean": mean, "_se": se, "_dir": direction, "_bars": bars})
            # sigma of the strategy arm against its own matched control
            if len(summary) >= 2 and summary[-1]["arm"].startswith("random"):
                a, b = summary[-2], summary[-1]
                spread = np.sqrt(a["_se"] ** 2 + b["_se"] ** 2)
                a["vs_random_sigma"] = (round((a["_mean"] - b["_mean"]) / spread, 2)
                                        if spread > 0 else None)
                b["vs_random_sigma"] = None
            for row in summary[-2:]:
                print(f"{row['arm']:<18}{row['trades']:>9,}{row['win_rate_pct']:>7.1f}"
                      f"{row['mean_trade_pct']:>9.4f}{row['se_pct']:>7.4f}"
                      f"{(row.get('vs_random_sigma') if row.get('vs_random_sigma') is not None else float('nan')):>7.2f}"
                      f"{row['cagr_pct']:>8.2f}{row['max_drawdown_pct']:>9.2f}"
                      f"{(row['ret_per_dd'] or 0):>8.2f}"
                      f"{row.get('day_weighted_pct', float('nan')):>8.4f}"
                      f"{row.get('quiet_days_pct', float('nan')):>8.4f}"
                      f"{row.get('heavy_days_pct', float('nan')):>8.4f}")
            print()

    table = pl.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")}
                          for r in summary])
    if args.out:
        table.write_csv(args.out)
        print(f"wrote {args.out}")
    print(f"buy-and-hold: {bench_cagr * 100:+.2f}% CAGR / {bench_dd * 100:.2f}% max DD, "
          f"fully invested. Every arm above is a day-trading book, flat overnight — read "
          f"its drawdown against the deployed column.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
