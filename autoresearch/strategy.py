#!/usr/bin/env python3
"""Baseline momentum book, held only while the market itself is above its own average.

THIS IS THE ONLY FILE THE LOOP MAY EDIT. Read `program.md` before changing it.

    universe    every name tradable on the bar — liquid enough, listed long enough
    filter      EMA(20) above EMA(100) on the total-return close
    rank        the mean cross-sectional rank of the 63, 126 and 252-session returns
    hold        the top 25, equal weight, cash whenever fewer than 25 qualify
    regime      the whole book goes to cash while an equal-weight index of the tradable
                universe is below its own 200-session average
    stop        out of a name once it is 15% below its own 63-session high
    rebalance   every 21 sessions; positions drift untouched in between

The index is chained from the cross-sectional mean of daily returns among names tradable on
the previous bar, so it is knowable at each close and never re-based on a date chosen later.
"""

from __future__ import annotations

import numpy as np

from prepare import Panel
from toolkit import (cs_rank, ema, equal_weight, hold_until_rebalance, pct_change,
                     rolling_max, sma, top_n)

FAST = 20
SLOW = 100
SLOTS = 25
LOOKBACKS = (63, 126, 252)
REBALANCE = 21
REGIME_MA = 30
STOP = 0.20
STOP_WINDOW = 126


def market_index(panel: Panel) -> np.ndarray:
    """Equal-weight index of the tradable universe, chained from daily mean returns."""
    mark = panel.mark
    r = np.zeros_like(mark)
    with np.errstate(invalid="ignore", divide="ignore"):
        r[1:] = mark[1:] / mark[:-1] - 1.0
    r = np.where(np.isfinite(r), r, np.nan)
    members = np.zeros_like(panel.tradable)
    members[1:] = panel.tradable[:-1]          # held from yesterday's close into today
    day = np.where(members & np.isfinite(r), r, np.nan)
    with np.errstate(invalid="ignore"):
        step = np.nanmean(np.where(np.isnan(day), np.nan, day), axis=1)
    step = np.where(np.isfinite(step), step, 0.0)
    return np.cumprod(1.0 + step)


def generate_weights(panel: Panel) -> np.ndarray:
    close = panel.close

    trend = ema(close, FAST) > ema(close, SLOW)
    eligible = panel.tradable & trend

    # Blend three horizons by cross-sectional rank rather than trusting one. Ranks are
    # comparable across horizons in a way raw returns are not.
    strength = np.nanmean([cs_rank(pct_change(close, k)) for k in LOOKBACKS], axis=0)
    picks = top_n(strength, SLOTS, eligible)
    target = equal_weight(picks, slots=SLOTS)
    held = hold_until_rebalance(target, panel.mark, REBALANCE)

    # Trailing stop: leave a name once it is STOP below its own high of the last STOP_WINDOW
    # sessions, and stay out until the next rebalance rather than buying it straight back.
    peak = rolling_max(close, STOP_WINDOW, min_samples=STOP_WINDOW // 2)
    with np.errstate(invalid="ignore"):
        stopped = close < (1.0 - STOP) * peak
    alive = np.zeros(close.shape, dtype=bool)
    live = np.ones(close.shape[1], dtype=bool)
    for t in range(close.shape[0]):
        if t % REBALANCE == 0:
            live = np.ones(close.shape[1], dtype=bool)
        live &= ~np.nan_to_num(stopped[t], nan=False)
        alive[t] = live
    held = held * alive

    index = market_index(panel).reshape(-1, 1)
    on = (index > sma(index, REGIME_MA)).ravel()
    return held * on.reshape(-1, 1)
