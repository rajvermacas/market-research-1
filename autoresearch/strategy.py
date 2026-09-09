#!/usr/bin/env python3
"""Blended-momentum book with a market regime switch and a trailing stop.

THIS IS THE ONLY FILE THE LOOP MAY EDIT. Read `program.md` before changing it.

Best of a 30-iteration search: SCORE 1.6464, up from 0.7677 for the plain crossover it
started as. Nine of those thirty changes were kept; `results.tsv` holds the other twenty-one.

    universe    every name tradable on the bar — liquid enough, listed long enough
    filter      EMA(20) above EMA(100) on the total-return close
    rank        the mean cross-sectional rank of the 63, 126 and 252-session returns
    hold        18 slots, equal weight, cash in any slot that cannot be filled
    stop        out of a name once it closes 20% below its own 126-session high, and out
                until the next rebalance rather than straight back in
    regime      the whole book goes to cash while an equal-weight index of the tradable
                universe is below its own 30-session average
    rebalance   every 21 sessions; positions drift untouched in between

The index is chained from the cross-sectional mean of daily returns among names tradable on
the previous bar, so it is knowable at each close and never re-based on a date chosen later.

Three things the search established that are not visible in the parameters:

  * The regime switch is worth more than everything else combined — 0.77 to 1.52 on its own —
    and its value is entirely in reacting the same session. Requiring three consecutive
    sessions before flipping gave back two thirds of it.
  * The cash the stop creates is part of the stop. Refilling an emptied slot the same session
    scored 1.53 against 1.63 for leaving it empty until the rebalance.
  * The EMA filter is nearly redundant with the ranking. Removing it costs 0.03, which is real
    but small; it is kept on that margin, not on conviction.

What was tried and rejected: inverse-volatility sizing, absolute momentum, ranking on return
per unit of volatility, skipping the most recent month, rebalancing every 10 or 42 sessions,
40 slots, and a daily exit on the trend breaking. Every one of them improved 2016-2021 while
hurting 2008-2015.
"""

from __future__ import annotations

import numpy as np

from prepare import Panel
from toolkit import (cs_rank, ema, equal_weight, hold_until_rebalance, pct_change,
                     rolling_max, sma, top_n)

FAST = 20
SLOW = 100
SLOTS = 18
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
    # Summed and divided rather than np.nanmean, which warns on the early rows where nothing
    # is tradable yet. Those sessions are simply flat for the index.
    live = np.count_nonzero(np.isfinite(day), axis=1)
    step = np.where(live > 0, np.nansum(day, axis=1) / np.maximum(live, 1), 0.0)
    return np.cumprod(1.0 + step)


def generate_weights(panel: Panel) -> np.ndarray:
    close = panel.close

    trend = ema(close, FAST) > ema(close, SLOW)
    eligible = panel.tradable & trend

    # Blend three horizons by cross-sectional rank rather than trusting one. Ranks are
    # comparable across horizons in a way raw returns are not.
    ranks = np.array([cs_rank(pct_change(close, k)) for k in LOOKBACKS])
    seen = np.count_nonzero(np.isfinite(ranks), axis=0)
    strength = np.where(seen > 0, np.nansum(ranks, axis=0) / np.maximum(seen, 1), np.nan)
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
