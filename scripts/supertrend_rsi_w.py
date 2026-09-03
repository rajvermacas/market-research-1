#!/usr/bin/env python3
"""Backtest of the RSI double-bottom ("W") + SuperTrend confluence.

The setup as it is taught:

    (1) RSI falls into the oversold zone
    (2) RSI carves a "W" — a first trough at the 30 line, a bounce, then a second
        trough at or above the first, and RSI turning up out of it
    (3) price rebounds too — its own double bottom / higher low against that second
        trough, and price back above where the trough closed
    (4) SuperTrend is pointing up
    (5) all of it agreeing at once is the entry

and the rule it is explicitly sold against — "RSI under 30, oversold, buy" — which the
same lesson calls dangerous on its own because it fires into falling knives.

That contrast is the entire testable claim, so this runs as an ablation. Five entry
rules trade the same window, the same universe and the same exit machinery:

    naive       RSI crosses back up through 30. The textbook oversold buy, and the
                charitable version of it: it at least waits for the turn instead of
                buying every bar under 30.
    st_flip     SuperTrend flips up. Trend alone, no RSI.
    w           the RSI W completes and turns up. Oscillator alone, no trend filter.
    w_price     the W, plus price confirming with its own higher low.
    full        all of it, including SuperTrend up. The setup as drawn.

Two controls, because a return without one measures the market rather than the setup:
an equal-weight buy-and-hold of the same universe over the same window, and random
entries drawn from the same bars and walked to an exit by the identical code.

Three exits, because the answer depends on which one you use and saying so is the point:

    rr          stop at the entry candle's low (or the SuperTrend line under it), target
                a fixed multiple of that risk. Comparable with the rest of the
                repository's backtests.
    trail       ride the SuperTrend line up and leave when price breaks it or the trend
                flips down. The strategy's own exit — the sell conditions in the lesson
                are the mirror image of the buy ones — and the tail is where a trend
                setup's return lives.
    horizon     hold a fixed number of bars. No stop, no target.

The third is the arbiter. Both of the others stop at a price derived from the entry bar,
and the arms disagree about what that price is: an arm entering in a SuperTrend uptrend
stops at the line far below, an arm with no trend filter enters mid-downtrend and stops
just under its own candle. That alone produced a median hold of 23 bars against 4, so a
gap in mean trade between them is partly a gap in how much room the trade was given. A
fixed horizon holds the exit genuinely constant and leaves only the entry being compared.

Point-in-time discipline:

  * An RSI pivot low is only a pivot once `--confirm` later bars have failed to undercut
    it, so it is treated as unknown until bar p + confirm. No signal reads a trough it
    could not yet have seen.
  * The trailing stop for bar j is the SuperTrend line as of bar j-1. The line at j is a
    function of j's own high, low and close, so trailing on it would be trading on a
    price the bar had not yet printed.
  * RSI and ATR are recursive; both are given a warm-up guard before any bar of theirs is
    allowed to signal. Wilder's RSI seeded at zero reads 100.0 on bar 1 and an unguarded
    ATR reads far too tight, and both flatter the result.
  * Within a bar the stop is assumed to fill before the target. The bar does not say
    which came first, and the alternative books the win every time they collide.

Traded on the corporate-action-adjusted Kite 60-minute panel (Nifty 500, 2015-02 on),
because the Yahoo intraday panel is unadjusted and only three years deep. Survivorship
bias remains: the universe is today's Nifty 500, so names that fell out of the index are
absent and every long-only number here is optimistic by an unmeasured amount.

Usage:
    python scripts/supertrend_rsi_w.py
    python scripts/supertrend_rsi_w.py --exit trail --slots 10
    python scripts/supertrend_rsi_w.py --exit horizon --horizon 24
    python scripts/supertrend_rsi_w.py --arms full --reward-risk 2 3 --charts 8
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

from screener import rsi
from rsi_backtest import find_trades, simulate, performance, elapsed_years

REPO_ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CHART_DIR = REPO_ROOT / ".cache" / "supertrend_rsi_w"

ARMS = ("naive", "st_flip", "w", "w_price", "full")


# ------------------------------------------------------------------------- indicators


def supertrend(high: np.ndarray, low: np.ndarray, close: np.ndarray,
               period: int, multiplier: float) -> tuple[np.ndarray, np.ndarray]:
    """SuperTrend line and its direction (+1 up, -1 down), Wilder ATR.

    The recursion is the whole indicator: the bands only ever tighten toward price while
    the trend holds, and reset when it breaks. A non-recursive "HL2 +/- k*ATR" is a
    different and much noisier line, so this follows the published definition rather than
    the shortcut, and verify_supertrend() checks it against a transcription of it.
    """
    n = len(close)
    line = np.full(n, np.nan)
    direction = np.zeros(n, dtype=np.int8)
    if n <= period + 1:
        return line, direction

    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    prev = close[:-1]
    tr[1:] = np.maximum(high[1:] - low[1:],
                        np.maximum(np.abs(high[1:] - prev), np.abs(low[1:] - prev)))
    # A bar whose open/high/low came through as a non-positive print carries no usable
    # range, and it must not enter the recursion. Left in, its NaN propagates through
    # every later ATR; and upstream the defect is a *zero* low, which does not read as
    # missing at all — it reads as a 100% range, blows the bands out, and hands the
    # backtest a stop at a price that never traded. It is skipped, not zeroed: a zero
    # would be a real observation of no movement and would drag the average down.
    good = np.isfinite(tr)

    atr = np.full(n, np.nan)
    seed = tr[:period][good[:period]]
    if not seed.size:
        return line, direction
    atr[period - 1] = seed.mean()
    for i in range(period, n):                      # Wilder smoothing, recursive
        atr[i] = ((atr[i - 1] * (period - 1) + tr[i]) / period if good[i]
                  else atr[i - 1])

    hl2 = (high + low) / 2.0
    upper_basic = hl2 + multiplier * atr
    lower_basic = hl2 - multiplier * atr
    usable = np.isfinite(upper_basic) & np.isfinite(lower_basic) & np.isfinite(close)

    start = period - 1
    while start < n and not usable[start]:
        start += 1
    if start >= n:
        return line, direction
    upper, lower = upper_basic[start], lower_basic[start]
    trend = 1                                       # seed long; it self-corrects on the
    line[start] = lower                             # first close outside a band
    direction[start] = trend
    for i in range(start + 1, n):
        if not usable[i]:
            # Carry the state across a defective bar and leave the line unset, so the bar
            # is ineligible to signal and cannot resolve a trade either way.
            direction[i] = trend
            continue
        ub, lb = upper_basic[i], lower_basic[i]
        # A band only moves toward price, unless price has already closed through it.
        if not (ub < upper or close[i - 1] > upper):
            ub = upper
        if not (lb > lower or close[i - 1] < lower):
            lb = lower
        if close[i] > upper:
            trend = 1
        elif close[i] < lower:
            trend = -1
        upper, lower = ub, lb
        line[i] = lower if trend == 1 else upper
        direction[i] = trend
    return line, direction


def pivot_lows(values: np.ndarray, confirm: int) -> np.ndarray:
    """Indices of local minima that `confirm` bars on each side fail to undercut.

    Strictly below on the left, at-or-below on the right, so a flat bottom marks its
    first bar once and not every bar of the shelf.
    """
    n = len(values)
    if n < 2 * confirm + 1:
        return np.empty(0, dtype=np.int64)
    window = np.lib.stride_tricks.sliding_window_view(values, 2 * confirm + 1)
    centre = values[confirm:n - confirm]
    with np.errstate(invalid="ignore"):
        left = np.nanmin(window[:, :confirm], axis=1)
        right = np.nanmin(window[:, confirm + 1:], axis=1)
        keep = (centre < left) & (centre <= right)
    keep &= ~np.isnan(centre)
    return confirm + np.flatnonzero(keep)


def w_state(rsi_a: np.ndarray, low: np.ndarray, close: np.ndarray, *,
            confirm: int, oversold: float, second_band: float, low_tol: float,
            min_bounce: float, min_sep: int, max_sep: int, max_age: int,
            price_tol: float, neckline: bool, settle: int):
    """Per bar: is a completed, turning-up RSI W in force, and does price confirm it.

    Returns (w_ok, price_ok, pair, trough1, trough2) — `pair` numbers each distinct pair
    of troughs so a signal can be deduplicated to the first bar the conditions align,
    rather than firing on every bar the W stays valid.

    Both legs are constrained in *duration*, not only in level. Without --max-sep a single
    long grind down qualifies: the "first trough" pins to whatever the oldest pivot in the
    series happens to be and the shape stops being a W at all.

    `settle` guards the *troughs*, not merely the bar that signals. Wilder's RSI is a
    recursive EWM seeded at zero: it prints 100 on bar 1 and 0 a few bars later, and those
    are pivot lows as far as any geometric test can tell. The first charts drawn from this
    code were all dated within nine sessions of the panel start, every one of them a W
    whose first trough was the seed converging rather than a price event.
    """
    n = len(rsi_a)
    w_ok = np.zeros(n, dtype=bool)
    price_ok = np.zeros(n, dtype=bool)
    pair = np.full(n, -1, dtype=np.int64)
    t1 = np.full(n, -1, dtype=np.int64)
    t2 = np.full(n, -1, dtype=np.int64)

    pivots = pivot_lows(rsi_a, confirm)
    pivots = pivots[pivots >= settle]        # no trough may predate the RSI settling
    if pivots.size < 2:
        return w_ok, price_ok, pair, t1, t2

    known = pivots + confirm            # the bar each pivot becomes knowable on
    cursor = 0                          # how many pivots are known at bar t
    peak_for = {}                       # (p1, p2) -> the RSI high between them
    pair_id = {}
    for t in range(n):
        while cursor < len(pivots) and known[cursor] <= t:
            cursor += 1
        if cursor < 2 or t == 0:
            continue
        p1, p2 = int(pivots[cursor - 2]), int(pivots[cursor - 1])
        key = (p1, p2)
        if key not in peak_for:
            peak_for[key] = float(np.nanmax(rsi_a[p1:p2 + 1]))
            pair_id[key] = len(pair_id)
        peak = peak_for[key]
        r1, r2, rt = rsi_a[p1], rsi_a[p2], rsi_a[t]
        if np.isnan(rt) or np.isnan(rsi_a[t - 1]):
            continue
        shape = (
            r1 <= oversold                                  # first trough is oversold
            and r2 <= oversold + second_band                # second still low
            and r2 >= r1 - low_tol                          # and not materially lower
            and peak - max(r1, r2) >= min_bounce            # a real middle, not a shelf
            and min_sep <= p2 - p1 <= max_sep               # legs bounded in time
            and t - p2 <= max_age                           # the turn is recent
        )
        if not shape:
            continue
        turning = rt > rsi_a[t - 1] and rt >= r2 + min_bounce
        if neckline:
            turning = turning and rt > peak
        if not turning:
            continue
        w_ok[t] = True
        pair[t] = pair_id[key]
        t1[t], t2[t] = p1, p2
        price_ok[t] = low[p2] >= low[p1] * (1 - price_tol) and close[t] > close[p2]
    return w_ok, price_ok, pair, t1, t2


# ------------------------------------------------------------------------ verification


def verify_supertrend(panel: pl.DataFrame, period: int, multiplier: float,
                      symbols: int = 25) -> None:
    """Check the array SuperTrend against a plain transcription of its definition.

    Same discipline the RSI here already gets. Two things are checked: agreement with an
    independently written loop, and the invariants that make the line a SuperTrend at all
    — it sits below price while the trend is up and above it while the trend is down. The
    second catches the class of error the first cannot, where both implementations share a
    misreading.
    """
    sample = sorted(panel["symbol"].unique().to_list())[:symbols]
    worst, checked, outside = 0.0, 0, 0
    for symbol in sample:
        part = panel.filter(pl.col("symbol") == symbol).sort("datetime")
        if part.height < period * 5:
            continue
        high = part["high"].to_numpy()
        low = part["low"].to_numpy()
        close = part["close"].to_numpy()

        # Reference: textbook loop, lists, no numpy.
        tr_list, atr_list = [], []
        for i in range(len(close)):
            if i == 0:
                tr_list.append(high[0] - low[0])
            else:
                tr_list.append(max(high[i] - low[i], abs(high[i] - close[i - 1]),
                                   abs(low[i] - close[i - 1])))
        ok = [t == t and abs(t) != float("inf") for t in tr_list]   # t != t is NaN
        head = [t for t, k in zip(tr_list[:period], ok[:period]) if k]
        if not head:
            continue
        running = sum(head) / len(head)
        for i in range(len(close)):
            if i < period - 1:
                atr_list.append(None)
            elif i == period - 1:
                atr_list.append(running)
            else:
                if ok[i]:
                    running = (running * (period - 1) + tr_list[i]) / period
                atr_list.append(running)
        ref_line, ref_dir = [None] * len(close), [0] * len(close)
        usable_ref = [i >= period - 1 and atr_list[i] is not None
                      and high[i] == high[i] and low[i] == low[i]
                      for i in range(len(close))]
        start = period - 1
        while start < len(close) and not usable_ref[start]:
            start += 1
        if start >= len(close):
            continue
        up = (high[start] + low[start]) / 2 + multiplier * atr_list[start]
        dn = (high[start] + low[start]) / 2 - multiplier * atr_list[start]
        trend = 1
        ref_line[start], ref_dir[start] = dn, 1
        for i in range(start + 1, len(close)):
            if not usable_ref[i]:
                ref_dir[i] = trend
                continue
            mid = (high[i] + low[i]) / 2
            bu, bl = mid + multiplier * atr_list[i], mid - multiplier * atr_list[i]
            nu = bu if (bu < up or close[i - 1] > up) else up
            nl = bl if (bl > dn or close[i - 1] < dn) else dn
            if close[i] > up:
                trend = 1
            elif close[i] < dn:
                trend = -1
            up, dn = nu, nl
            ref_line[i] = dn if trend == 1 else up
            ref_dir[i] = trend

        line, direction = supertrend(high, low, close, period, multiplier)
        checked += int(np.isfinite(line).sum())
        deviation = max(abs(line[i] - ref_line[i]) for i in range(start, len(close))
                        if ref_line[i] is not None and np.isfinite(line[i]))
        worst = max(worst, deviation)
        if (direction[start:] != np.array(ref_dir[start:], dtype=np.int8)).any():
            raise SystemExit(f"SuperTrend direction disagrees with the reference on {symbol}")
        if not np.isin(direction, (-1, 0, 1)).all():
            raise SystemExit(f"SuperTrend direction is not +/-1 on {symbol}")
        # The line normally sits below price in an uptrend and above it in a downtrend,
        # but that is a consequence rather than a rule, and it genuinely breaks on a bar
        # whose range exceeds 2 x multiplier x ATR: the band is rebuilt from that bar's
        # own midpoint and can land past the close, while direction is decided against the
        # PREVIOUS bar's band and so does not flip. The bar after it then trips the band's
        # reset clause and the line steps away from price. Both are the published
        # definition, not a defect, so they are counted and reported rather than asserted
        # away — 13 such bars in 7.86M here, every one downstream of a 6x-ATR spike. The
        # backtest is insulated from them regardless: find_trades_trailing() ratchets the
        # stop with np.maximum.accumulate, so a band that steps back can never loosen a
        # stop that is already live.
        flip = np.zeros(len(close), dtype=bool)
        flip[1:] = direction[1:] != direction[:-1]
        settled = ~np.isnan(line) & ~flip
        outside += int(((direction == 1) & settled & (close < line)).sum())
        outside += int(((direction == -1) & settled & (close > line)).sum())
    rate = outside / max(checked, 1)
    print(f"  SuperTrend check on {len(sample)} symbols ({checked:,} bars): max deviation "
          f"{worst:.10f}, direction identical, {outside} spike bars "
          f"({rate * 100:.4f}%) with the line the wrong side of price")
    if worst > 1e-9:
        raise SystemExit("SuperTrend disagrees with the reference implementation")
    # A handful of 6x-ATR bars is the indicator behaving as defined; a percent of them is
    # an implementation that has the band recursion wrong.
    if rate > 1e-4:
        raise SystemExit(f"SuperTrend line sits the wrong side of price on {rate:.2%} of "
                         f"bars — the band recursion is wrong, not the data")


# ------------------------------------------------------------------------- trade search


def find_trades_trailing(frame: pl.DataFrame, cost: float) -> pl.DataFrame:
    """Walk each signal forward until the SuperTrend line breaks or the trend flips.

    The stop for bar j is the highest line printed up to bar j-1: it ratchets up and never
    down, and it is never read from the bar it is being applied to. A flip to a downtrend
    that somehow misses the stop exits at that bar's close. The stop is checked first, so
    a bar that does both resolves against us.
    """
    rows = []
    for (symbol,), part in frame.group_by("symbol", maintain_order=True):
        part = part.sort("datetime")
        idx = np.flatnonzero(part["signal"].to_numpy())
        if not idx.size:
            continue
        times = part["datetime"].dt.epoch("us").to_numpy()
        high, low = part["high"].to_numpy(), part["low"].to_numpy()
        open_, close = part["open"].to_numpy(), part["close"].to_numpy()
        line, direction = part["st_line"].to_numpy(), part["st_dir"].to_numpy()
        n = len(close)

        # Only an up-trend line may act as a stop: while the trend is down the line sits
        # above price, and ratcheting on it would stop every trade out on its first bar.
        # The NaN a defective bar leaves in the line must become -inf here and not stay
        # NaN: the ratchet below is np.maximum.accumulate, which propagates NaN to the end
        # of the array, so a single bad print mid-trade would blank the stop for the rest
        # of the series and every open trade in that symbol would run to the last bar
        # instead of exiting. Silent, and it inflates exactly the tail this setup lives on.
        up_line = np.where((direction == 1) & np.isfinite(line), line, -np.inf)
        flip_down = np.zeros(n, dtype=bool)
        flip_down[1:] = (direction[1:] == -1) & (direction[:-1] == 1)

        for i in idx:
            entry = close[i]
            if i >= n - 1 or not np.isfinite(entry) or entry <= 0:
                continue
            # An arm that does not filter on SuperTrend can enter mid-downtrend, where
            # there is no line below price to stop against. Those signals keep the entry
            # bar's low until the line comes back under price — dropping them instead
            # would quietly delete the very trades the trend filter exists to avoid, and
            # flatter every arm that lacks one.
            stop = line[i] if (direction[i] == 1 and line[i] < entry) else low[i]
            if not np.isfinite(stop) or stop >= entry:
                continue
            trail = np.maximum.accumulate(       # stop in force at bars i+1 ... n-1
                np.maximum(up_line[i:n - 1], stop))
            after_low = low[i + 1:]
            hits = np.flatnonzero(after_low <= trail)
            flips = np.flatnonzero(flip_down[i + 1:])
            first_stop = hits[0] if hits.size else np.inf
            first_flip = flips[0] if flips.size else np.inf
            if first_stop == np.inf and first_flip == np.inf:
                j, exit_price, outcome = n - 1, close[n - 1], "open"
            elif first_stop <= first_flip:
                j = i + 1 + int(first_stop)
                level = trail[int(first_stop)]
                exit_price = open_[j] if open_[j] <= level else level
                outcome = "trail"
            else:
                j = i + 1 + int(first_flip)
                exit_price, outcome = close[j], "flip"
            rows.append({
                "symbol": symbol, "entry_time": int(times[i]), "entry": float(entry),
                "stop": float(stop), "target": float("nan"),
                "exit_time": int(times[j]), "exit": float(exit_price), "outcome": outcome,
                "bars_held": int(j - i),
                "ret": float(exit_price / entry * (1 - cost) ** 2 - 1),
                "risk_pct": float((entry - stop) / entry),
            })
    return pl.DataFrame(rows).sort("entry_time") if rows else pl.DataFrame()


def find_trades_horizon(frame: pl.DataFrame, cost: float, horizon: int) -> pl.DataFrame:
    """Hold each signal for a fixed number of bars. No stop, no target, no discretion.

    This exists because the other two exits cannot answer the question on their own. Both
    stop at a price derived from the entry bar, and the arms do not agree about what that
    price is: an arm entering in a SuperTrend uptrend stops at the line, typically far
    below, while an arm with no trend filter enters mid-downtrend and stops at the entry
    candle's low, typically just under it. The result is a median hold of 23 bars against
    4, and a difference in mean trade that is partly a difference in how much room the
    trade was given rather than in what the entry predicted.

    A fixed horizon removes all of it. Every arm is held the same number of bars from the
    same kind of fill, so what is left is the only thing being compared: whether the entry
    said anything about the next `horizon` bars.
    """
    rows = []
    for (symbol,), part in frame.group_by("symbol", maintain_order=True):
        part = part.sort("datetime")
        idx = np.flatnonzero(part["signal"].to_numpy())
        if not idx.size:
            continue
        times = part["datetime"].dt.epoch("us").to_numpy()
        close = part["close"].to_numpy()
        n = len(close)
        idx = idx[idx < n - 1]
        exits = np.minimum(idx + horizon, n - 1)
        entry, exit_price = close[idx], close[exits]
        keep = np.isfinite(entry) & (entry > 0) & np.isfinite(exit_price)
        for i, j, e, x in zip(idx[keep], exits[keep], entry[keep], exit_price[keep]):
            rows.append({
                "symbol": symbol, "entry_time": int(times[i]), "entry": float(e),
                "stop": float("nan"), "target": float("nan"),
                "exit_time": int(times[j]), "exit": float(x),
                "outcome": "horizon" if j == i + horizon else "open",
                "bars_held": int(j - i),
                "ret": float(x / e * (1 - cost) ** 2 - 1),
                "risk_pct": float("nan"),
            })
    return pl.DataFrame(rows).sort("entry_time") if rows else pl.DataFrame()


def random_signals(frame: pl.DataFrame, count: int, seed: int) -> pl.DataFrame:
    """Replace the signal column with `count` random eligible bars.

    The control the repository's own lesson demands: any entry rule scores well in a bull
    market, so the number that matters is an arm's mean trade minus this one's. Drawn only
    from bars the strategy could itself have traded — warmed up, and not the last bar — so
    the comparison is of the rule, not of the window.

    Deliberately oversampled rather than matched to an arm's trade count. Matched, the
    control's own standard error is as wide as the arm's and it stops being a yardstick:
    the same control moved from -0.018% to -0.100% mean trade between two runs purely on
    how many bars it happened to draw. A comparison is only as stable as the thing being
    compared against.
    """
    eligible = np.flatnonzero(frame["eligible"].to_numpy())
    if not eligible.size:
        return frame.with_columns(pl.lit(False).alias("signal"))
    rng = np.random.default_rng(seed)
    picks = rng.choice(eligible, size=min(count, eligible.size), replace=False)
    flag = np.zeros(frame.height, dtype=bool)
    flag[picks] = True
    return frame.with_columns(pl.Series("signal", flag))


# ---------------------------------------------------------------------------- reporting


def deployment(trades: pl.DataFrame, grid: np.ndarray, slots: int) -> float:
    """Share of capital actually at work, averaged over the window.

    A strategy that sits in cash most of the time is not low-risk, it is part-time, and
    comparing its drawdown with a fully invested benchmark without this column mistakes
    one for the other.
    """
    entry_i = np.searchsorted(grid, trades["entry_time"].to_numpy())
    exit_i = np.searchsorted(grid, trades["exit_time"].to_numpy())
    # Bucketed by entry bar rather than rescanned every bar: with 120k signals over 20k
    # bars the naive scan is 2.4 billion comparisons and dominates the whole run.
    starts: dict[int, list[int]] = {}
    for k, t in enumerate(entry_i):
        starts.setdefault(int(t), []).append(int(exit_i[k]))
    open_ct = np.zeros(len(grid))
    held: list[int] = []
    for t in range(len(grid)):
        if held:
            held = [e for e in held if e > t]
        for exit_at in starts.get(t, ()):
            if len(held) >= slots:
                break
            held.append(exit_at)
        open_ct[t] = len(held)
    return float(open_ct.mean() / slots)


def render_charts(frame: pl.DataFrame, trades: pl.DataFrame, count: int,
                  path: Path, oversold: float) -> None:
    """Draw the matched signals. Geometry passes in ways that look nothing like a W.

    The repository has been burned by exactly this once already, on the N-pattern screen:
    the conditions were satisfied and the charts showed the wrong shape entirely.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.mkdir(parents=True, exist_ok=True)
    picks = trades.head(count)
    for row in picks.iter_rows(named=True):
        part = frame.filter(pl.col("symbol") == row["symbol"]).sort("datetime")
        times = part["datetime"].dt.epoch("us").to_numpy()
        i = int(np.searchsorted(times, row["entry_time"]))
        lo, hi = max(0, i - 70), min(part.height, i + 40)
        view = part[lo:hi]
        x = np.arange(view.height)
        o, h, l, c = (view[k].to_numpy() for k in ("open", "high", "low", "close"))

        fig, (ax, rax) = plt.subplots(
            2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
        for k in range(view.height):
            colour = "#26a69a" if c[k] >= o[k] else "#ef5350"
            ax.plot([x[k], x[k]], [l[k], h[k]], color=colour, linewidth=0.8)
            ax.add_patch(plt.Rectangle((x[k] - 0.3, min(o[k], c[k])), 0.6,
                                       max(abs(c[k] - o[k]), 1e-9),
                                       facecolor=colour, edgecolor=colour))
        st = view["st_line"].to_numpy()
        direction = view["st_dir"].to_numpy()
        ax.plot(np.where(direction == 1, x, np.nan), np.where(direction == 1, st, np.nan),
                color="#2e7d32", linewidth=1.4, label="SuperTrend (up)")
        ax.plot(np.where(direction == -1, x, np.nan), np.where(direction == -1, st, np.nan),
                color="#c62828", linewidth=1.4, label="SuperTrend (down)")
        ax.axvline(i - lo, color="#1565c0", linestyle="--", linewidth=1.2, label="entry")
        ax.axhline(row["stop"], color="#b71c1c", linestyle=":", linewidth=1.0, label="stop")
        ax.set_title(f"{row['symbol']}  entry {view['datetime'][i - lo]}  "
                     f"{row['outcome']}  {row['ret'] * 100:+.1f}%  "
                     f"held {row['bars_held']} bars")
        ax.legend(loc="upper left", fontsize=8)
        ax.set_ylabel("price")

        r = view["rsi_h"].to_numpy()
        rax.plot(x, r, color="#5e35b1", linewidth=1.1)
        rax.axhline(oversold, color="#888", linestyle="--", linewidth=0.8)
        rax.axhline(70, color="#888", linestyle="--", linewidth=0.8)
        for trough, marker in ((int(view["trough1"][i - lo]), "1st"),
                               (int(view["trough2"][i - lo]), "2nd")):
            if lo <= trough < hi:
                rax.plot(trough - lo, r[trough - lo], "o", color="#5e35b1", markersize=8,
                         markerfacecolor="none")
                rax.annotate(marker, (trough - lo, r[trough - lo]),
                             textcoords="offset points", xytext=(0, -16), fontsize=8)
        rax.axvline(i - lo, color="#1565c0", linestyle="--", linewidth=1.2)
        rax.set_ylabel("RSI")
        rax.set_ylim(0, 100)
        fig.tight_layout()
        out = path / f"{row['symbol']}_{row['entry_time']}.png"
        fig.savefig(out, dpi=110)
        plt.close(fig)
    print(f"  wrote {picks.height} charts to {path}")


# ------------------------------------------------------------------------------- frame


def build_frame(panel: pl.DataFrame, args) -> pl.DataFrame:
    """Attach RSI, SuperTrend and the W state to every bar, symbol by symbol."""
    panel = panel.sort("symbol", "datetime").with_columns(
        rsi("close", args.rsi_period).over("symbol").alias("rsi_h")
    )
    settle = max(args.rsi_period * 3, args.atr_period * 3)
    parts = []
    for (symbol,), part in panel.group_by("symbol", maintain_order=True):
        part = part.sort("datetime")
        n = part.height
        if n < settle + 2 * args.confirm + 10:
            continue
        high, low, close = (part[k].to_numpy() for k in ("high", "low", "close"))
        line, direction = supertrend(high, low, close, args.atr_period, args.multiplier)
        w_ok, price_ok, pair, t1, t2 = w_state(
            part["rsi_h"].to_numpy(), low, close,
            confirm=args.confirm, oversold=args.oversold, second_band=args.second_band,
            low_tol=args.low_tol, min_bounce=args.min_bounce, min_sep=args.min_sep,
            max_sep=args.max_sep, max_age=args.max_age, price_tol=args.price_tol,
            neckline=args.neckline, settle=settle)
        seen = np.arange(n)
        eligible = (seen >= settle) & np.isfinite(line) & (seen < n - 1)
        parts.append(part.with_columns(
            pl.Series("st_line", line), pl.Series("st_dir", direction.astype(np.int64)),
            pl.Series("w_ok", w_ok), pl.Series("price_ok", price_ok),
            pl.Series("pair", pair), pl.Series("trough1", t1), pl.Series("trough2", t2),
            pl.Series("eligible", eligible),
        ))
    if not parts:
        raise SystemExit("no symbol had enough history to build indicators on")
    return pl.concat(parts)


def arm_signal(frame: pl.DataFrame, arm: str, oversold: float) -> pl.DataFrame:
    """Set the `signal` column for one entry rule, one signal per distinct setup.

    Deduplication matters more than it looks. A W stays valid for as long as RSI keeps
    rising out of it, so without collapsing each pair of troughs to its first qualifying
    bar the same setup enters ten times and the trade count — and every average built on
    it — is an artefact of how long the conditions happened to hold.
    """
    prev_rsi = pl.col("rsi_h").shift(1).over("symbol")
    prev_dir = pl.col("st_dir").shift(1).over("symbol")
    raw = {
        "naive": (prev_rsi <= oversold) & (pl.col("rsi_h") > oversold),
        "st_flip": (pl.col("st_dir") == 1) & (prev_dir == -1),
        "w": pl.col("w_ok"),
        "w_price": pl.col("w_ok") & pl.col("price_ok"),
        "full": pl.col("w_ok") & pl.col("price_ok") & (pl.col("st_dir") == 1),
    }[arm]
    frame = frame.with_columns((raw & pl.col("eligible")).alias("_raw"))
    if arm in ("w", "w_price", "full"):
        # first qualifying bar of each trough pair
        frame = frame.with_columns(
            (pl.col("_raw")
             & (pl.col("_raw").cum_sum().over("symbol", "pair") == 1)).alias("signal"))
    else:
        frame = frame.with_columns(pl.col("_raw").alias("signal"))
    return frame.drop("_raw")


def assert_point_in_time(frame: pl.DataFrame, confirm: int) -> None:
    """No signal may rest on a trough it could not yet have seen.

    A pivot low is only a pivot once `confirm` later bars have failed to undercut it, so
    the earliest bar that may act on one is trough + confirm. This is the invariant the
    whole test rests on and it is the one that would break silently: shift the pivot
    window by a bar and every number improves, with nothing to show it went wrong.
    """
    marked = frame.filter(pl.col("signal") & (pl.col("pair") >= 0))
    if not marked.height:
        return
    index = (frame.with_columns(pl.int_range(pl.len()).over("symbol").alias("_i"))
             .filter(pl.col("signal") & (pl.col("pair") >= 0)))
    early = index.filter(pl.col("_i") - pl.col("trough2") < confirm)
    if early.height:
        raise SystemExit(
            f"{early.height} signals read an RSI trough only {confirm} bars of hindsight "
            f"could have identified — the pattern search is looking ahead")


def benchmark(panel: pl.DataFrame, years: float) -> tuple[float, float, int, list[str]]:
    """Equal-weight buy-and-hold of every symbol trading at the window start.

    The MEAN of normalised prices — a rupee into each name at t0, held — never the median,
    which is the path of the median stock, is not tradeable, and reads seven points of
    CAGR low because cross-sectional returns are right-skewed.
    """
    wide = (panel.select("symbol", "datetime", "close")
            .pivot(on="symbol", index="datetime", values="close").sort("datetime"))
    wide = wide.with_columns(
        [pl.col(c).forward_fill() for c in wide.columns if c != "datetime"])
    cols = [c for c in wide.columns if c != "datetime"]
    matrix = wide.select(cols).to_numpy()
    listed = ~np.isnan(matrix[0])
    normalised = matrix[:, listed] / matrix[0, listed]
    # An unadjusted split shows up as one hourly bar moving more than 50%, which no traded
    # price does. A detectable defect, removed by name — not an outcome-based trim of the
    # terminal value, which is lookahead and deletes genuine multibaggers.
    step = normalised[1:] / np.where(normalised[:-1] == 0, np.nan, normalised[:-1])
    with np.errstate(invalid="ignore"):
        artefact = np.nanmax(np.abs(step - 1.0), axis=0) > 0.50
    curve = np.nanmean(normalised[:, ~artefact], axis=1)
    cagr, dd = performance(curve, years)
    names = [c for c, bad in zip(np.array(cols)[listed], artefact) if bad]
    return cagr, dd, int(listed.sum()), names


# ------------------------------------------------------------------------------- main


def run_arm(name: str, frame: pl.DataFrame, prices: pl.DataFrame, grid: np.ndarray,
            years: float, args, cost: float, reward_risk: float | None) -> dict | None:
    """One entry rule, from signals to a portfolio curve."""
    signals = int(frame["signal"].sum())
    if not signals:
        print(f"  {name:<9} no signals")
        return None
    if args.exit == "horizon":
        trades = find_trades_horizon(frame, cost, args.horizon)
    elif args.exit == "trail":
        trades = find_trades_trailing(frame, cost)
    else:
        stop_column = "stop_price" if args.stop == "supertrend" else None
        trades = find_trades(frame, cost, reward_risk, stop_column=stop_column)
    if trades.is_empty():
        print(f"  {name:<9} {signals:,} signals, none resolvable")
        return None
    equity, taken, skipped, _, max_stacked, unrealised = simulate(
        trades, prices, args.slots, cost, args.per_symbol)
    cagr, maxdd = performance(equity, years)
    closed = trades.filter(pl.col("outcome") != "open")
    wins = closed.filter(pl.col("ret") > 0).height
    mean_trade = float(closed["ret"].mean()) if closed.height else float("nan")
    # A difference in mean trade is worth nothing without the spread it is drawn from.
    # Trade returns here are heavily right-skewed, so the standard error is large relative
    # to the mean and a gap of a few basis points is noise however many trades produced it.
    std = float(closed["ret"].std()) if closed.height > 1 else float("nan")
    se = std / np.sqrt(closed.height) if closed.height > 1 else float("nan")
    mid = prices["datetime"][prices.height // 2].timestamp() * 1_000_000
    h1 = closed.filter(pl.col("entry_time") < mid)["ret"].mean()
    h2 = closed.filter(pl.col("entry_time") >= mid)["ret"].mean()
    ranked = closed["ret"].sort(descending=True)
    gross = float(ranked.filter(ranked > 0).sum())
    top10 = float(ranked.head(10).sum())
    return {
        "arm": name, "signals": signals, "trades": trades.height, "taken": taken,
        "win_rate_pct": round(wins / max(closed.height, 1) * 100, 1),
        "mean_trade_pct": round(mean_trade * 100, 3),
        "se_pct": round(se * 100, 3),
        "median_hold_bars": int(trades["bars_held"].median()),
        "cagr_pct": round(cagr * 100, 2), "max_drawdown_pct": round(maxdd * 100, 2),
        "deployed_pct": round(deployment(trades, grid, args.slots) * 100, 1),
        "final_equity": round(float(equity[-1]), 3),
        "h1_mean_pct": round(float(h1) * 100, 3) if h1 is not None else None,
        "h2_mean_pct": round(float(h2) * 100, 3) if h2 is not None else None,
        "top10_share_pct": round(top10 / gross * 100, 1) if gross > 0 else None,
        "unrealised": round(float(unrealised), 4),
        # Filled in once this target's random control has run; the control keeps a null.
        "vs_random_sigma": None,
        "_mean": mean_trade, "_se": se,
        "_trades": trades,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--panel", default="60minute_kite_clean",
                        help="directory under data/ohlcv/ to trade (default the adjusted "
                             "Kite Nifty 500 panel)")
    parser.add_argument("--universe", default="nifty500")
    parser.add_argument("--arms", nargs="+", default=list(ARMS), choices=ARMS)
    parser.add_argument("--exit", choices=("rr", "trail", "horizon"), default="rr")
    parser.add_argument("--horizon", type=int, default=24,
                        help="horizon exit only: bars to hold, unconditionally. 24 hourly "
                             "bars is ~3.4 sessions, the median hold of the arms that "
                             "carry a trend filter")
    parser.add_argument("--stop", choices=("low", "supertrend"), default="low",
                        help="rr exit only: the entry candle's low (default, comparable "
                             "with the rest of the repo) or the SuperTrend line, which "
                             "falls back to the low when the line sits above price")
    parser.add_argument("--reward-risk", type=float, nargs="+", default=[2.0],
                        help="rr exit only: target as a multiple of risk")
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--atr-period", type=int, default=10)
    parser.add_argument("--multiplier", type=float, default=3.0)
    parser.add_argument("--oversold", type=float, default=30.0)
    parser.add_argument("--confirm", type=int, default=3,
                        help="bars either side that must fail to undercut an RSI trough "
                             "before it counts as one (and before it is knowable)")
    parser.add_argument("--second-band", type=float, default=10.0,
                        help="how far above the oversold line the second trough may sit")
    parser.add_argument("--low-tol", type=float, default=3.0,
                        help="RSI points the second trough may undercut the first by")
    parser.add_argument("--min-bounce", type=float, default=5.0,
                        help="RSI points the middle peak must clear the troughs by, and "
                             "the current bar must have lifted off the second trough by")
    parser.add_argument("--min-sep", type=int, default=4)
    parser.add_argument("--max-sep", type=int, default=40,
                        help="bars between the two troughs; without a cap a long grind "
                             "down qualifies and the shape is not a W at all")
    parser.add_argument("--max-age", type=int, default=8,
                        help="bars since the second trough — the turn must be recent")
    parser.add_argument("--price-tol", type=float, default=0.02,
                        help="fraction the price low at the second trough may undercut "
                             "the first by and still count as price confirming")
    parser.add_argument("--neckline", action="store_true",
                        help="require RSI above the peak between the troughs, i.e. the W "
                             "fully completed rather than merely turning up")
    parser.add_argument("--slots", type=int, default=10)
    parser.add_argument("--per-symbol", type=int, default=None)
    parser.add_argument("--cost-bps", type=float, default=10.0,
                        help="one-way, in basis points (default 10 = 0.20%% round trip)")
    parser.add_argument("--random-seed", type=int, default=7)
    parser.add_argument("--random-draws", type=int, default=50_000,
                        help="size of the random-entry control. Large on purpose: it is "
                             "the yardstick every arm is measured against, so its own "
                             "standard error has to be the small one")
    parser.add_argument("--charts", type=int, default=0,
                        help="render this many matched signals of the last arm")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    cost = args.cost_bps / 10_000

    universe = pl.read_parquet(UNIVERSE)
    if args.universe != "nse_all":
        universe = universe.filter(pl.col(f"in_{args.universe}"))
    symbols = universe["symbol"].to_list()
    glob = str(REPO_ROOT / "data" / "ohlcv" / args.panel / "**" / "*.parquet")
    panel = (pl.scan_parquet(glob, hive_partitioning=True)
             .filter(pl.col("symbol").is_in(symbols))
             .select("symbol", "datetime", "open", "high", "low", "close")
             .drop_nulls("close")
             .collect())
    print(f"panel {args.panel}: {panel.height:,} bars, "
          f"{panel['symbol'].n_unique()} symbols, "
          f"{panel['datetime'].min()} -> {panel['datetime'].max()}")

    # A backtest with stops reads lows, and a broken low is not a small error — it is the
    # lowest possible low. It fills every stop in that symbol at a price that never traded
    # and, as the entry bar's stop, sizes the trade to ~100% risk. clean_kite_panel.py
    # nulls non-positive *closes* only, so three classes survive into the traded panel:
    #
    #   zero print        open/high/low <= 0 while close is fine (1,439 bars)
    #   ordering broken   high below the body, or low above it (38 bars)
    #   split break       one bar carrying both adjusted and unadjusted prices — PIIND
    #                     prints open 815.4 against a low of 81.8 (63 bars)
    #
    # The last two are found by the same test the benchmark already uses on this data: no
    # traded price moves 50% inside an hour. Together 0.02% of the panel. They are nulled,
    # not repaired — the panel's own convention for a bar that cannot be trusted, and one
    # that works because NaN compares False, so the bar can neither be entered on nor
    # resolve a trade in either direction.
    body_high = pl.max_horizontal("open", "close")
    body_low = pl.min_horizontal("open", "close")
    broken = (
        (pl.col("open") <= 0) | (pl.col("high") <= 0) | (pl.col("low") <= 0)
        | (pl.col("high") < pl.col("low")) | (pl.col("high") < body_high)
        | (pl.col("low") > body_low)
        | (((pl.col("high") - pl.col("low")) / pl.col("close")) > 0.50)
    )
    defective = panel.filter(broken)
    if defective.height:
        print(f"  {defective.height:,} bars ({defective.height / panel.height * 100:.4f}%) "
              f"across {defective['symbol'].n_unique()} symbols are defective upstream "
              f"— nulled, not repaired")
        panel = panel.with_columns([
            pl.when(broken).then(None).otherwise(pl.col(k)).alias(k)
            for k in ("open", "high", "low")
        ])

    print("\nverifying indicators")
    verify_supertrend(panel, args.atr_period, args.multiplier)

    print("building indicators and the W state")
    frame = build_frame(panel, args)
    if args.stop == "supertrend":
        frame = frame.with_columns(
            pl.when(pl.col("st_line") < pl.col("close")).then(pl.col("st_line"))
            .otherwise(pl.col("low")).alias("stop_price"))
    print(f"  {frame.height:,} bars over {frame['symbol'].n_unique()} symbols, "
          f"{int(frame['eligible'].sum()):,} eligible to signal")

    # One price grid for every arm, so the portfolio curves are directly comparable.
    prices = (frame.select("symbol", "datetime", "close")
              .pivot(on="symbol", index="datetime", values="close").sort("datetime"))
    prices = prices.with_columns(
        [pl.col(c).forward_fill().backward_fill()
         for c in prices.columns if c != "datetime"])
    grid = prices["datetime"].dt.epoch("us").to_numpy()
    years = elapsed_years(grid)
    bench_cagr, bench_dd, listed, artefacts = benchmark(frame, years)

    print(f"\nwindow {prices['datetime'][0]} -> {prices['datetime'][-1]}"
          f"  ({prices.height:,} bars, {years:.2f} years)")
    print(f"CONTROL equal-weight buy-and-hold, {listed} symbols, fully invested: "
          f"{bench_cagr * 100:+.2f}% CAGR / {bench_dd * 100:.2f}% max DD"
          + (f"  ({len(artefacts)} corporate-action artefacts excluded)" if artefacts else ""))

    targets = [None] if args.exit in ("trail", "horizon") else args.reward_risk
    summary, last = [], None
    for reward_risk in targets:
        if args.exit == "trail":
            label = "SuperTrend trailing stop, exit on the flip down"
        elif args.exit == "horizon":
            label = f"held exactly {args.horizon} bars — no stop, no target"
        else:
            label = f"stop at the entry candle's {args.stop}, target 1:{reward_risk:g}"
        print(f"\n--- {label} ---")
        for arm in args.arms:
            marked = arm_signal(frame, arm, args.oversold)
            assert_point_in_time(marked, args.confirm)
            row = run_arm(arm, marked, prices, grid, years, args, cost, reward_risk)
            if row is None:
                continue
            row["target"] = args.exit if reward_risk is None else f"1:{reward_risk:g}"
            print(f"  {arm:<9} {row['signals']:>6,} sig  {row['taken']:>5,} taken  "
                  f"win {row['win_rate_pct']:>5.1f}%  mean {row['mean_trade_pct']:>+7.3f}%  "
                  f"CAGR {row['cagr_pct']:>+7.2f}%  DD {row['max_drawdown_pct']:>7.2f}%  "
                  f"deployed {row['deployed_pct']:>5.1f}%")
            summary.append({k: v for k, v in row.items() if k != "_trades"})
            last = (arm, marked, row["_trades"])

        # Random entries through the identical exit machinery, so "mean trade" has
        # something to be a number *against*.
        control = random_signals(frame, args.random_draws, args.random_seed)
        row = run_arm("random", control, prices, grid, years, args, cost, reward_risk)
        if row is not None:
            row["target"] = args.exit if reward_risk is None else f"1:{reward_risk:g}"
            print(f"  {'random':<9} {row['signals']:>6,} sig  {row['taken']:>5,} taken  "
                  f"win {row['win_rate_pct']:>5.1f}%  mean {row['mean_trade_pct']:>+7.3f}%  "
                  f"CAGR {row['cagr_pct']:>+7.2f}%  DD {row['max_drawdown_pct']:>7.2f}%  "
                  f"deployed {row['deployed_pct']:>5.1f}%   <- control")
            summary.append({k: v for k, v in row.items() if k != "_trades"})
            group = args.exit if reward_risk is None else f"1:{reward_risk:g}"
            for entry in summary:
                if entry["target"] == group and entry["arm"] != "random":
                    spread = np.sqrt(entry["_se"] ** 2 + row["_se"] ** 2)
                    entry["vs_random_sigma"] = (
                        round((entry["_mean"] - row["_mean"]) / spread, 2)
                        if np.isfinite(spread) and spread > 0 else None)

    summary = [{k: v for k, v in row.items() if not k.startswith("_")} for row in summary]
    table = pl.DataFrame(summary)
    print(f"\n{'=' * 100}")
    print("ABLATION — every arm on the same bars, the same exit and the same benchmark")
    print(f"{'=' * 100}")
    with pl.Config(tbl_rows=60, tbl_cols=20, tbl_width_chars=200):
        print(table)
    print(f"\nbuy-and-hold control: {bench_cagr * 100:+.2f}% CAGR / "
          f"{bench_dd * 100:.2f}% max DD, fully invested throughout.")
    print("Every arm above is part-time — read its drawdown against its deployed column, "
          "not against the benchmark's.")

    if args.charts and last is not None:
        arm, marked, trades = last
        print(f"\nrendering {args.charts} '{arm}' signals")
        render_charts(marked, trades, args.charts, CHART_DIR, args.oversold)
    if args.out:
        table.write_csv(args.out)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
