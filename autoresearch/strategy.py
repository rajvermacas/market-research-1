#!/usr/bin/env python3
"""Baseline: hold the strongest names that are in an EMA uptrend, rebalanced monthly.

THIS IS THE ONLY FILE THE LOOP MAY EDIT. Read `program.md` before changing it.

    universe    every name tradable on the bar — liquid enough, listed long enough
    filter      EMA(20) above EMA(100) on the total-return close: the name is trending
    rank        trailing 126-session return, highest first
    hold        the top 25, equal weight, cash whenever fewer than 25 qualify
    rebalance   every 21 sessions; positions drift untouched in between

The ranking is not decoration — a slot cap needs some rule for which of the several hundred
qualifying names to own, and trailing return is the plainest one available. Both the crossover
and the ranking are open to replacement; the slot cap and the rebalance cadence are just
numbers.

What this deliberately does not do: no stop, no target, no sizing by volatility, no regime
overlay, no sector or correlation constraint, no short side. Those are the obvious directions,
and they are left for the loop to find and to prove on both windows.
"""

from __future__ import annotations

import numpy as np

from prepare import Panel
from toolkit import ema, equal_weight, hold_until_rebalance, pct_change, top_n

FAST = 20
SLOW = 100
SLOTS = 25
LOOKBACK = 126
REBALANCE = 21


def generate_weights(panel: Panel) -> np.ndarray:
    """Return a (bars x symbols) matrix of target weights, row `t` held from close `t`.

    Everything read here must be knowable at the close of bar `t`. The harness re-runs this
    function on truncated history and fails the run if the answer moves.
    """
    close = panel.close

    trend = ema(close, FAST) > ema(close, SLOW)
    eligible = panel.tradable & trend

    strength = pct_change(close, LOOKBACK)
    picks = top_n(strength, SLOTS, eligible)
    target = equal_weight(picks, slots=SLOTS)

    return hold_until_rebalance(target, panel.mark, REBALANCE)
