#!/usr/bin/env python3
"""Baseline momentum book, held only while the market itself is above its own average.

THIS IS THE ONLY FILE THE LOOP MAY EDIT. Read `program.md` before changing it.

    universe    every name tradable on the bar — liquid enough, listed long enough
    filter      EMA(20) above EMA(100) on the total-return close
    rank        trailing 126-session return, highest first
    hold        the top 25, equal weight, cash whenever fewer than 25 qualify
    regime      the whole book goes to cash while an equal-weight index of the tradable
                universe is below its own 200-session average
    rebalance   every 21 sessions; positions drift untouched in between

The index is chained from the cross-sectional mean of daily returns among names tradable on
the previous bar, so it is knowable at each close and never re-based on a date chosen later.
"""

from __future__ import annotations

import numpy as np

from prepare import Panel
from toolkit import ema, equal_weight, hold_until_rebalance, pct_change, sma, top_n

FAST = 20
SLOW = 100
SLOTS = 25
LOOKBACK = 126
REBALANCE = 21
REGIME_MA = 50


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

    strength = pct_change(close, LOOKBACK)
    picks = top_n(strength, SLOTS, eligible)
    target = equal_weight(picks, slots=SLOTS)
    held = hold_until_rebalance(target, panel.mark, REBALANCE)

    index = market_index(panel).reshape(-1, 1)
    on = (index > sma(index, REGIME_MA)).ravel()
    return held * on.reshape(-1, 1)
