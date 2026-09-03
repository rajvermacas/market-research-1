#!/usr/bin/env python3
"""Connors' RSI(2) mean reversion, as published by QuantifiedStrategies, on Indian equity.

The strategy, which the source states plainly and which is therefore testable exactly as
written rather than inferred:

    entry   RSI(2) closes below 10. Bought at that close.
    exit    the first close above the PREVIOUS bar's high. Sold at that close.
    filter  optionally, only take the entry while the close is above its 200-day SMA.

Published on QQQ it returns 12.75% CAGR against 6.4% buy-and-hold, 75% winners, profit
factor 3.15, 19.5% max drawdown, from 196 trades and 14% time in the market. The headline
attached to it — "56% annual, risk-adjusted" — is what that becomes when the return is
divided by how little of the time the capital is actually at work, so this reports
exposure and the exposure-adjusted figure side by side and lets the reader see which one
is being quoted.

Two translations to Indian equity, because they answer different questions:

    index   the real cap-weighted Nifty series from Yahoo (^NSEI 2007-, ^CRSLDX 2005-).
            The faithful analogue of the QQQ test: one instrument, long or flat. It is
            also the only version free of this repository's survivorship bias, since an
            index series is not a basket of today's survivors.
    stocks  the same rule on individual constituents out of the committed daily panel,
            portfolio-simulated with a slot cap. Mean reversion in a single stock is a
            different claim from mean reversion in an index — the index cannot be
            delisted, taken over, or hit by a fraud, and a stock can.

Controls, because a return without one measures the market:

  * buy-and-hold of the same series over the same window.
  * random entries with the identical exit rule, so the question is whether RSI(2) < 10
    beats picking a day out of a hat and selling on the first close above yesterday's
    high — the exit does a great deal of work here and it has to be held constant.

Costs are the thing that decides this strategy, so they are a first-class argument rather
than a footnote: a 3-day hold repeated a few hundred times pays the spread far more often
than a trend system does. --cost-sweep reports the whole curve.

Usage:
    python scripts/rsi2_mean_reversion.py --mode index
    python scripts/rsi2_mean_reversion.py --mode index --trend-filter --cost-sweep
    python scripts/rsi2_mean_reversion.py --mode stocks --universe nifty50 --slots 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl

from screener import rsi
from rsi_backtest import simulate, performance

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CACHE = REPO_ROOT / ".cache" / "indices"

INDICES = {
    "nifty50": "^NSEI",
    "nifty100": "^CNX100",
    "nifty500": "^CRSLDX",
}


# ------------------------------------------------------------------------------ data


def fetch_index(name: str) -> pl.DataFrame:
    """Daily OHLC for a real Nifty index, cached under .cache/ (gitignored).

    The index rather than a basket of today's constituents. An equal-weight proxy built
    from the current membership list would carry the survivorship bias this repository
    warns about in its own README, and would carry it into precisely the number being
    checked. Yahoo needs a browser User-Agent from this environment or it answers 429.
    """
    ticker = INDICES[name]
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.parquet"
    if path.exists():
        return pl.read_parquet(path)

    import yfinance as yf
    from download_market_data import make_session

    raw = yf.download(ticker, start="1995-01-01", end="2026-09-02",
                      session=make_session(), progress=False, auto_adjust=False)
    if raw is None or not len(raw):
        raise SystemExit(f"Yahoo returned nothing for {ticker} — refusing to guess")
    if hasattr(raw.columns, "droplevel"):
        raw.columns = raw.columns.droplevel(1)
    frame = (pl.from_pandas(raw.reset_index())
             .rename({"Date": "date", "Open": "open", "High": "high",
                      "Low": "low", "Close": "close"})
             .select(pl.col("date").cast(pl.Date), "open", "high", "low", "close")
             .drop_nulls()
             .sort("date"))
    frame.write_parquet(path)
    return frame


# ------------------------------------------------------------------------- the rule


def attach_signal(frame: pl.DataFrame, period: int, level: float,
                  trend_filter: bool, sma: int, group: str | None = None,
                  rule: str = "rsi2", r3_from: float = 60.0,
                  ibs_level: float = 0.2) -> pl.DataFrame:
    """The entry condition for one rule, optionally above the SMA. Warm-up guarded.

    Three rules, so the marginal value of each extra condition is visible rather than
    assumed:

        rsi2  RSI(period) < level. The plain Connors rule.
        r3    Connors' R3, from "High Probability ETF Trading": RSI(2) must have fallen on
              three consecutive days, the first of those falls starting from a reading
              below `r3_from`, and today's reading must be under `level`. The difference
              from rsi2 is entirely a *path* condition — the same destination, reached in
              a specified way — so running the two side by side prices what the path is
              worth on its own.
        ibs   Internal Bar Strength, (close - low) / (high - low), below `ibs_level`. A
              different indicator entirely, and included because it is the strongest
              documented daily mean-reversion signal in the literature: if nothing in this
              family works on Nifty, it should fail too, and if the family works at all it
              is the one that should show it.

    The warm-up guard is not decoration even at period 2. Wilder's RSI is a recursive EWM
    seeded at zero and reads 100.0 on the first bar and 0.0 shortly after, and a 0.0
    satisfies "RSI < 10" for free. At period 2 it settles in a handful of bars, but the SMA
    filter needs its full window regardless, so the binding guard is that one.
    """
    def maybe(expr):
        return expr.over(group) if group else expr

    out = frame.with_columns(maybe(rsi("close", period)).alias("rsi"))
    span = pl.col("high") - pl.col("low")
    out = out.with_columns(
        maybe(pl.col("close").rolling_mean(sma)).alias("sma"),
        maybe(pl.col("high").shift(1)).alias("prev_high"),
        maybe(pl.int_range(pl.len())).alias("_seen"),
        # A doji prints high == low and would divide by zero; those bars are simply not
        # eligible for an IBS rule rather than being assigned an arbitrary 0 or 0.5.
        ((pl.col("close") - pl.col("low"))
         / pl.when(span > 0).then(span).otherwise(None)).alias("ibs"),
    )
    for lag in (1, 2, 3):
        out = out.with_columns(maybe(pl.col("rsi").shift(lag)).alias(f"rsi_{lag}"))

    warm = pl.col("_seen") >= (max(sma, period * 10) if trend_filter else period * 10)
    if rule == "rsi2":
        condition = pl.col("rsi") < level
    elif rule == "r3":
        condition = (
            (pl.col("rsi_3") < r3_from)                 # the run starts from below 60
            & (pl.col("rsi_2") < pl.col("rsi_3"))       # three consecutive falls
            & (pl.col("rsi_1") < pl.col("rsi_2"))
            & (pl.col("rsi") < pl.col("rsi_1"))
            & (pl.col("rsi") < level)                   # and finishes oversold
        )
    elif rule == "ibs":
        condition = pl.col("ibs") < ibs_level
    else:
        raise SystemExit(f"unknown rule {rule!r}")
    condition = condition & warm
    if trend_filter:
        condition = condition & (pl.col("close") > pl.col("sma"))
    return out.with_columns(condition.fill_null(False).alias("signal"))


def walk(frame: pl.DataFrame, cost: float, max_hold: int | None = None,
         exit_rule: str = "up-close", exit_level: float = 70.0,
         horizon: int = 5) -> pl.DataFrame:
    """Buy on a signal close, sell when the exit rule fires. One position at a time.

    Three exits, held identical across every rule being compared:

        up-close  the first close above the previous bar's high. Connors' RSI(2) exit.
        rsi70     the first close with RSI(period) above `exit_level`. R3's own exit.
        horizon   exactly `horizon` bars later, unconditionally.

    The third is the arbiter and it is not a stylistic preference. Both of the others are
    themselves mean-reversion bets that resolve within days whatever opened the trade, so
    comparing two entry rules through them measures the exit as much as the entry. Only a
    fixed horizon holds the exit genuinely constant.

    One position at a time — the published strategies are single-instrument long-or-flat
    rules, and stacking entries would be testing something else. A signal that fires while
    already in the trade is ignored rather than added to.
    """
    close = frame["close"].to_numpy()
    high = frame["high"].to_numpy()
    signal = frame["signal"].to_numpy()
    rsi_a = frame["rsi"].to_numpy()
    dates = frame["date"].to_list()      # date objects, not numpy: a numpy datetime64
    n = len(close)                       # round-trips into an Object column downstream

    rows, i = [], 0
    while i < n - 1:
        if not signal[i]:
            i += 1
            continue
        entry, j, outcome = close[i], None, "exit"
        if exit_rule == "horizon":
            if i + horizon <= n - 1:
                j = i + horizon
            else:
                j, outcome = n - 1, "open"   # the window ran out before the horizon did
        else:
            for k in range(i + 1, n):
                done = (close[k] > high[k - 1] if exit_rule == "up-close"
                        else rsi_a[k] > exit_level)
                if done or (max_hold is not None and k - i >= max_hold):
                    j = k
                    break
            if j is None:                    # never triggered before the data ended
                j, outcome = n - 1, "open"
        rows.append({
            "entry_date": dates[i], "exit_date": dates[j],
            "entry": float(entry), "exit": float(close[j]),
            "bars_held": int(j - i), "outcome": outcome,
            "ret": float(close[j] / entry * (1 - cost) ** 2 - 1),
        })
        i = j + 1                           # flat again on the exit bar
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def equity_curve(frame: pl.DataFrame, trades: pl.DataFrame, cost: float) -> np.ndarray:
    """Mark the account daily: it rides the index while in a trade and is flat otherwise.

    Marking daily rather than trade-to-trade is what makes the drawdown comparable with
    the benchmark's. A curve stepped only at exits hides every excursion the position sat
    through and reports a drawdown the strategy did not actually have.
    """
    close = frame["close"].to_numpy()
    dates = frame["date"].to_list()
    equity = np.ones(len(close))
    held = 1.0
    index = {d: k for k, d in enumerate(dates)}
    spans = [(index[r["entry_date"]], index[r["exit_date"]])
             for r in trades.iter_rows(named=True)]
    entry_at = {a: b for a, b in spans}

    k = 0
    while k < len(close):
        if k in entry_at:
            b = entry_at[k]
            base = close[k]
            for t in range(k, b + 1):
                equity[t] = held * (close[t] / base) * (1 - cost)
            held = held * (close[b] / base) * (1 - cost) ** 2
            equity[b] = held
            k = b + 1
        else:
            equity[k] = held
            k += 1
    return equity


def random_control(frame: pl.DataFrame, count: int, cost: float, seed: int,
                   warm: int, **walk_kwargs) -> pl.DataFrame:
    """The same exit rule from entries chosen at random, matched in number.

    The exit — "first close above yesterday's high" — is itself a mean-reversion bet and
    resolves most trades within days whatever the entry was. Without this control, its
    work is credited to RSI(2)."""
    rng = np.random.default_rng(seed)
    n = frame.height
    eligible = np.arange(warm, n - 1)
    if not eligible.size:
        return pl.DataFrame()
    picks = np.zeros(n, dtype=bool)
    picks[rng.choice(eligible, size=min(count, eligible.size), replace=False)] = True
    return walk(frame.with_columns(pl.Series("signal", picks)), cost, **walk_kwargs)


# ---------------------------------------------------------------------- verification


def verify_rsi(frame: pl.DataFrame, period: int) -> None:
    """Check the Polars RSI against a textbook Wilder loop before trading on it.

    At period 2 the two seed differently — Polars runs its EWM from the first bar, the
    textbook loop from a simple average of the first `period` changes — and with
    alpha = 1/2 that difference decays by a factor of two per bar, so it is visible only
    in the opening handful of bars. A deviation that survives into the body of the series
    would be a real disagreement.
    """
    close = frame["close"].to_numpy()
    computed = frame.with_columns(rsi("close", period).alias("_r"))["_r"].to_numpy()
    gains = losses = 0.0
    for i in range(1, period + 1):
        change = close[i] - close[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    worst = worst_late = 0.0
    for i in range(period + 1, len(close)):
        change = close[i] - close[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        reference = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
        if not np.isfinite(computed[i]):
            continue
        gap = abs(computed[i] - reference)
        worst = max(worst, gap)
        if i > period * 20:
            worst_late = max(worst_late, gap)
    print(f"  RSI({period}) vs a textbook Wilder loop: max deviation {worst:.8f} "
          f"overall, {worst_late:.10f} past the seed")
    if worst_late > 1e-6:
        raise SystemExit("RSI disagrees with the reference implementation")


def event_study(frame: pl.DataFrame, level: float, trend_filter: bool) -> None:
    """Forward returns after the signal, against the same days without it.

    The trade walk cannot separate the entry from the exit — "sell on the first close
    above yesterday's high" is itself a mean-reversion bet and resolves most trades in
    days whatever triggered them. This measures only the entry: what the next N sessions
    did after RSI < level, against every other session the filter would have allowed.
    Costs are excluded deliberately, so the edge can be compared with them directly.
    """
    close = frame["close"].to_numpy()
    signal = frame["signal"].to_numpy()
    baseline = np.ones(len(close), dtype=bool)
    if trend_filter:
        sma = frame["sma"].to_numpy()
        baseline = np.isfinite(sma) & (close > sma)
    baseline &= frame["_seen"].to_numpy() >= 0
    baseline &= np.isfinite(frame["rsi"].to_numpy())

    print(f"\n  forward returns, gross of costs — {int(signal.sum())} signal days "
          f"against {int(baseline.sum()):,} comparable days")
    print(f"    {'days':>5} {'after signal':>14} {'baseline':>11} {'edge':>9} {'t':>7}")
    for horizon in (1, 2, 3, 5, 10):
        forward = np.full(len(close), np.nan)
        forward[:-horizon] = close[horizon:] / close[:-horizon] - 1
        good = np.isfinite(forward)
        a, b = forward[signal & good], forward[baseline & good]
        if len(a) < 2 or len(b) < 2:
            continue
        spread = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        print(f"    {horizon:>5} {a.mean() * 100:>13.3f}% {b.mean() * 100:>10.3f}% "
              f"{(a.mean() - b.mean()) * 100:>8.3f}% "
              f"{(a.mean() - b.mean()) / spread:>7.2f}")


# ------------------------------------------------------------------------- reporting


def summarise(name: str, trades: pl.DataFrame, equity: np.ndarray,
              years: float, bars: int) -> dict:
    closed = trades.filter(pl.col("outcome") != "open")
    wins = closed.filter(pl.col("ret") > 0)
    losses = closed.filter(pl.col("ret") <= 0)
    gross_win = float(wins["ret"].sum()) if wins.height else 0.0
    gross_loss = -float(losses["ret"].sum()) if losses.height else 0.0
    exposure = float(trades["bars_held"].sum() + trades.height) / bars if trades.height else 0.0
    cagr, maxdd = performance(equity, years)
    return {
        "run": name,
        "trades": trades.height,
        "win_rate_pct": round(wins.height / max(closed.height, 1) * 100, 1),
        "avg_trade_pct": round(float(closed["ret"].mean()) * 100, 3) if closed.height else None,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "median_hold": int(trades["bars_held"].median()) if trades.height else 0,
        "time_in_market_pct": round(exposure * 100, 1),
        "cagr_pct": round(cagr * 100, 2),
        "max_drawdown_pct": round(maxdd * 100, 2),
        # What a "risk-adjusted" headline is usually doing: crediting the return with the
        # capital's idle time. Reported so the reader can see the arithmetic, not because
        # it is a number anyone can earn — the cash has to sit somewhere the other 90%.
        "cagr_per_exposure_pct": round(cagr / exposure * 100, 1) if exposure > 0 else None,
        "final_equity": round(float(equity[-1]), 3),
    }


def stock_event_study(panel: pl.DataFrame, trend_filter: bool) -> None:
    """Pooled forward returns after the signal against every comparable symbol-day.

    Same purpose as the index version: strip the exit out and look only at what the entry
    predicted.

    Two t-statistics, and only the second is worth anything. The pooled one treats every
    symbol-day as an independent observation, which they emphatically are not: RSI(2) < 10
    fires on hundreds of names at once during a market-wide selloff, so a few dozen bad
    days supply most of the sample and the same market move is counted over and over. The
    clustered one collapses each calendar date to a single number — the day's mean signal
    return minus the day's mean baseline return — and tests that series across dates. It
    is the honest one, and it is typically several times smaller.
    """
    close = panel["close"].to_numpy()
    signal = panel["signal"].to_numpy()
    symbols = panel["symbol"].to_numpy()
    baseline = np.isfinite(panel["rsi"].to_numpy())
    if trend_filter:
        sma = panel["sma"].to_numpy()
        baseline &= np.isfinite(sma) & (close > sma)

    print(f"\n  forward returns, gross of costs — {int(signal.sum()):,} signal days "
          f"against {int(baseline.sum()):,} comparable days")
    # Raw and winsorised, because this panel is known to carry unadjusted corporate
    # actions: a handful of symbol-days move hundreds of percent and two of them can set
    # the mean of a 16,000-day sample. Winsorising at the 1st/99th percentile of the
    # pooled distribution is applied to signal and baseline alike, so it cannot favour
    # either — unlike trimming on the outcome, which is lookahead.
    print(f"    {'days':>5} {'after signal':>14} {'baseline':>11} {'edge':>9} "
          f"{'t (pooled)':>11} {'edge (wins.)':>14} {'t (by date)':>12} {'dates':>7}")
    dates = panel["date"].to_numpy()
    for horizon in (1, 3, 5, 10):
        # The panel is one long stacked frame, so a forward return must not be allowed to
        # read across the boundary between two symbols — that would price the last bars of
        # one stock off the first bars of the next.
        same = symbols[horizon:] == symbols[:-horizon]
        forward = np.full(len(close), np.nan)
        forward[:-horizon] = np.where(
            same, close[horizon:] / close[:-horizon] - 1, np.nan)
        good = np.isfinite(forward)
        a, b = forward[signal & good], forward[baseline & good]
        spread = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        lo, hi = np.percentile(forward[good], [1, 99])
        aw, bw = np.clip(a, lo, hi), np.clip(b, lo, hi)
        spread_w = np.sqrt(aw.var(ddof=1) / len(aw) + bw.var(ddof=1) / len(bw))
        # Clustered by calendar date: one observation per day, so a selloff that puts 300
        # names into the signal at once counts once rather than 300 times.
        daily = (pl.DataFrame({"date": dates, "fwd": np.clip(forward, lo, hi),
                               "sig": signal, "base": baseline, "ok": good})
                 .filter(pl.col("ok"))
                 .group_by("date")
                 .agg(pl.col("fwd").filter(pl.col("sig")).mean().alias("s"),
                      pl.col("fwd").filter(pl.col("base")).mean().alias("b"))
                 .drop_nulls()
                 .with_columns((pl.col("s") - pl.col("b")).alias("d")))
        d = daily["d"].to_numpy()
        t_cluster = (d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))) if len(d) > 1 else float("nan")
        print(f"    {horizon:>5} {a.mean() * 100:>13.3f}% {b.mean() * 100:>10.3f}% "
              f"{(a.mean() - b.mean()) * 100:>8.3f}% "
              f"{(a.mean() - b.mean()) / spread:>11.2f}"
              f" {(aw.mean() - bw.mean()) * 100:>13.3f}% "
              f"{t_cluster:>12.2f} {len(d):>7,}")


def stock_trades(panel: pl.DataFrame, cost: float, max_hold: int | None,
                 **walk_kwargs) -> pl.DataFrame:
    """The same walk, per symbol, emitted in the shape rsi_backtest.simulate() expects."""
    rows = []
    for (symbol,), part in panel.group_by("symbol", maintain_order=True):
        part = part.sort("date")
        found = walk(part, cost, max_hold, **walk_kwargs)
        if found.is_empty():
            continue
        rows.append(found.with_columns(pl.lit(symbol).alias("symbol")))
    if not rows:
        return pl.DataFrame()
    trades = pl.concat(rows)
    return (trades.with_columns(
        pl.col("entry_date").cast(pl.Datetime("us")).dt.epoch("us").alias("entry_time"),
        pl.col("exit_date").cast(pl.Datetime("us")).dt.epoch("us").alias("exit_time"))
        .sort("entry_time"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("index", "stocks"), default="index")
    parser.add_argument("--rules", nargs="+", default=["rsi2", "r3", "ibs"],
                        choices=("rsi2", "r3", "ibs"),
                        help="entry rules to compare on the same bars (default all three)")
    parser.add_argument("--exit-rule", choices=("up-close", "rsi70", "horizon"),
                        default="up-close",
                        help="up-close is Connors' RSI(2) exit, rsi70 is R3's own, "
                             "horizon holds a fixed number of bars and is the only one "
                             "that cannot flatter one entry rule over another")
    parser.add_argument("--exit-level", type=float, default=70.0)
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--r3-from", type=float, default=60.0,
                        help="R3: the reading the three-day decline must start below")
    parser.add_argument("--ibs-level", type=float, default=0.2)
    parser.add_argument("--universe", default="nifty50", choices=sorted(INDICES))
    parser.add_argument("--rsi-period", type=int, default=2)
    parser.add_argument("--level", type=float, default=10.0,
                        help="buy when RSI closes below this (default 10, as published)")
    parser.add_argument("--trend-filter", action="store_true",
                        help="only enter while the close is above its 200-day SMA")
    parser.add_argument("--sma", type=int, default=200)
    parser.add_argument("--max-hold", type=int, default=None,
                        help="force an exit after this many bars; off by default, since "
                             "the published rule has no time stop")
    parser.add_argument("--cost-bps", type=float, default=10.0,
                        help="one-way, in basis points (default 10 = 0.20%% round trip)")
    parser.add_argument("--cost-sweep", action="store_true",
                        help="repeat the index test across a range of costs — this is a "
                             "few-day hold repeated hundreds of times, so the cost "
                             "assumption decides the result and deserves a curve")
    parser.add_argument("--slots", type=int, default=10, help="stocks mode: max positions")
    parser.add_argument("--min-bars", type=int, default=1000,
                        help="stocks mode: skip symbols with less history than this")
    parser.add_argument("--random-seed", type=int, default=7)
    parser.add_argument("--start", default=None,
                        help="ISO date to start from. The daily panel holds ~9%% of the "
                             "symbols that actually traded in 2000 and is only solid from "
                             "about 2015, so a full-history stocks run is ranking "
                             "survivors — pass 2015-01-01 to see what that is worth")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    cost = args.cost_bps / 10_000
    warm = max(args.sma if args.trend_filter else 0, args.rsi_period * 10)

    def walk_args(c):
        return dict(max_hold=args.max_hold, exit_rule=args.exit_rule,
                    exit_level=args.exit_level, horizon=args.horizon)

    if args.mode == "index":
        raw = fetch_index(args.universe)
        years = (raw["date"][-1] - raw["date"][0]).days / 365.25
        print(f"{INDICES[args.universe]} ({args.universe}): {raw.height:,} sessions, "
              f"{raw['date'][0]} -> {raw['date'][-1]}  ({years:.2f} years)")
        exit_text = {"up-close": "exit on the first close above the previous high",
                     "rsi70": f"exit when RSI rises above {args.exit_level:g}",
                     "horizon": f"exit exactly {args.horizon} bars later"}[args.exit_rule]
        print(f"{exit_text}"
              + (f", entries filtered to close > SMA({args.sma})" if args.trend_filter else ""))
        verify_rsi(raw, args.rsi_period)

        close = raw["close"].to_numpy()
        bench_cagr, bench_dd = performance(close / close[0], years)
        print(f"\nCONTROL buy-and-hold {args.universe}, fully invested: "
              f"{bench_cagr * 100:+.2f}% CAGR / {bench_dd * 100:.2f}% max drawdown")

        costs = [0, 5, 10, 20, 30, 50] if args.cost_sweep else [args.cost_bps]
        summary = []
        for rule in args.rules:
            frame = attach_signal(raw, args.rsi_period, args.level, args.trend_filter,
                                  args.sma, rule=rule, r3_from=args.r3_from,
                                  ibs_level=args.ibs_level)
            print(f"\n--- {rule} --- {int(frame['signal'].sum()):,} days meet the entry "
                  f"condition")
            event_study(frame, args.level, args.trend_filter)
            for bps in costs:
                c = bps / 10_000
                trades = walk(frame, c, **walk_args(c))
                if trades.is_empty():
                    print(f"  {bps} bps: no trades")
                    continue
                summary.append(summarise(f"{rule} @ {bps:g}bps", trades,
                                         equity_curve(frame, trades, c), years,
                                         frame.height))
            # Same exit, entries from a hat, matched in count to this rule's.
            trades = walk(frame, cost, **walk_args(cost))
            if not trades.is_empty():
                control = random_control(frame, trades.height, cost, args.random_seed,
                                         warm, **walk_args(cost))
                if not control.is_empty():
                    summary.append(summarise(f"random({rule}) @ {args.cost_bps:g}bps",
                                             control,
                                             equity_curve(frame, control, cost), years,
                                             frame.height))
                mid = frame["date"][frame.height // 2]
                for label, part in (("first half ",
                                     trades.filter(pl.col("entry_date") < mid)),
                                    ("second half",
                                     trades.filter(pl.col("entry_date") >= mid))):
                    if part.height:
                        c2 = part.filter(pl.col("outcome") != "open")
                        if c2.height:
                            print(f"  {label}: {part.height:>4} trades, "
                                  f"mean {float(c2['ret'].mean()) * 100:+.3f}%, win "
                                  f"{c2.filter(pl.col('ret') > 0).height / c2.height * 100:.1f}%")
        table = pl.DataFrame(summary)
        print()
        with pl.Config(tbl_rows=60, tbl_cols=14, tbl_width_chars=190):
            print(table)
        if args.out:
            table.write_csv(args.out)
        return 0

    # ---------------------------------------------------------------- stocks mode
    universe = pl.read_parquet(UNIVERSE).filter(pl.col(f"in_{args.universe}"))
    symbols = universe["symbol"].to_list()
    panel = (pl.scan_parquet(DAILY_GLOB, hive_partitioning=True)
             .filter(pl.col("symbol").is_in(symbols))
             .select("symbol", "date", "open", "high", "low", "close")
             .drop_nulls("close")
             .collect()
             .sort("symbol", "date"))
    if args.start:
        panel = panel.filter(pl.col("date") >= pl.lit(args.start).str.to_date())
    counts = panel.group_by("symbol").len().filter(pl.col("len") >= args.min_bars)
    panel = panel.filter(pl.col("symbol").is_in(counts["symbol"].implode()))
    print(f"{args.universe}: {panel.height:,} daily bars, "
          f"{panel['symbol'].n_unique()} symbols with >= {args.min_bars} bars, "
          f"{panel['date'].min()} -> {panel['date'].max()}")

    # One price grid and one benchmark for every rule, so the curves are comparable.
    prices = (panel.select("symbol", "date", "close")
              .with_columns(pl.col("date").cast(pl.Datetime("us")).alias("datetime"))
              .pivot(on="symbol", index="datetime", values="close")
              .sort("datetime"))
    prices = prices.with_columns([pl.col(c).forward_fill().backward_fill()
                                  for c in prices.columns if c != "datetime"])
    grid = prices["datetime"].dt.epoch("us").to_numpy()
    years = float(grid[-1] - grid[0]) / (365.25 * 86400 * 1_000_000)

    # Equal-weight buy-and-hold of the names trading at the window start: the MEAN of
    # normalised prices, never the median, which is not tradeable and reads low.
    matrix = prices.select([c for c in prices.columns if c != "datetime"]).to_numpy()
    listed = ~np.isnan(matrix[0])
    normalised = matrix[:, listed] / matrix[0, listed]
    bench_cagr, bench_dd = performance(np.nanmean(normalised, axis=1), years)
    print(f"CONTROL equal-weight buy-and-hold ({int(listed.sum())} symbols, fully "
          f"invested): {bench_cagr * 100:+.2f}% CAGR / {bench_dd * 100:.2f}% max DD")

    base, rows = panel, []
    for rule in args.rules:
        marked = attach_signal(base, args.rsi_period, args.level, args.trend_filter,
                               args.sma, group="symbol", rule=rule,
                               r3_from=args.r3_from, ibs_level=args.ibs_level)
        print(f"\n--- {rule} --- {int(marked['signal'].sum()):,} entry days")
        stock_event_study(marked, args.trend_filter)

        # Exactly as many random signal days as this rule produced, drawn only from days
        # it could itself have fired on. Drawing at a matched *rate* instead is not the
        # same thing: real signals cluster inside market-wide selloffs, so many land while
        # the symbol is already in a trade and are skipped, and the control ends up with
        # half again as many actual trades and a deployment advantage that flatters it.
        rng = np.random.default_rng(args.random_seed)
        warm_days = (marked["_seen"].to_numpy()
                     >= (args.sma if args.trend_filter else args.rsi_period * 10))
        eligible = np.flatnonzero(warm_days & np.isfinite(marked["rsi"].to_numpy()))
        wanted = int(marked["signal"].sum())
        if not eligible.size or not wanted:
            continue
        picks = np.zeros(marked.height, dtype=bool)
        picks[rng.choice(eligible, size=min(wanted, eligible.size), replace=False)] = True
        shuffled = marked.with_columns(pl.Series("signal", picks))

        pair = []
        for label, source in ((rule, marked), (f"random({rule})", shuffled)):
            trades = stock_trades(source, cost, args.max_hold, exit_rule=args.exit_rule,
                                  exit_level=args.exit_level, horizon=args.horizon)
            if trades.is_empty():
                print(f"  {label}: no trades")
                continue
            equity, taken, skipped, _, _, _ = simulate(trades, prices, args.slots, cost)
            cagr, maxdd = performance(equity, years)
            closed = trades.filter(pl.col("outcome") != "open")
            if not closed.height:
                continue
            wins = closed.filter(pl.col("ret") > 0)
            mean = float(closed["ret"].mean())
            se = float(closed["ret"].std()) / np.sqrt(closed.height)
            pair.append({
                "run": label, "signals": trades.height, "taken": taken,
                "win_rate_pct": round(wins.height / closed.height * 100, 1),
                "mean_trade_pct": round(mean * 100, 3), "se_pct": round(se * 100, 3),
                "median_hold": int(trades["bars_held"].median()),
                "cagr_pct": round(cagr * 100, 2),
                "max_drawdown_pct": round(maxdd * 100, 2),
                "final_equity": round(float(equity[-1]), 3),
                "vs_random_sigma": None, "_mean": mean, "_se": se})
        if len(pair) == 2:
            spread = np.sqrt(pair[0]["_se"] ** 2 + pair[1]["_se"] ** 2)
            if np.isfinite(spread) and spread > 0:
                pair[0]["vs_random_sigma"] = round(
                    (pair[0]["_mean"] - pair[1]["_mean"]) / spread, 2)
        rows.extend(pair)

    if not rows:
        print("no trades on any rule")
        return 1
    table = pl.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")}
                          for r in rows])
    print()
    with pl.Config(tbl_rows=20, tbl_cols=12, tbl_width_chars=175):
        print(table)
    print(f"\nbuy-and-hold control: {bench_cagr * 100:+.2f}% CAGR / "
          f"{bench_dd * 100:.2f}% max DD, fully invested throughout.")
    print("Survivorship: this is today's index membership walked backwards, so every "
          "long-only number above is optimistic by an unmeasured amount.")
    if args.out:
        table.write_csv(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
