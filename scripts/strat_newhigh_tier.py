"""Candidate: newhigh ranking with float-regime exposure tiers (strategy_lab contract).

Same proximity-to-trailing-high rank as strat_newhigh (imported, not copied:
fresh breakouts over extended winners), but the regime leg is a float
exposure in {0.0, 0.4, 0.7, 1.0} keyed off market breadth — the fraction of
live names printing above their own `regime_ma`-month average — instead of
the binary index-vs-MA gate:

    breadth > b_hi  -> 1.0 (full risk)
    breadth > b_mid -> 0.7
    breadth > b_lo  -> 0.4
    else            -> 0.0 (cash)

Rationale: the binary gate jumps from full size to cash on a single
index-vs-MA cross, whipsawing exposure around the line. Breadth moves
slower than price level (names cross their MAs on different months), so
tiers scale the book with participation rather than flipping it.

PIT-safe: breadth for holding month starting months[m] uses month-end
closes through px[m] only; NaN MA rows (warm-up) count as below-MA, which
only makes early breadth conservative, never peeks.

SPACE = lookback {11}, max_dist {0.10}, regime_ma {5},
        b_hi {0.55}, b_mid {0.45}, b_lo {0.35} (tiers fixed at 1.0/0.7/0.4/0).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_newhigh import score as base_score

NEEDS_DAILY = False
SPACE = {
    "lookback": [11],
    "max_dist": [0.10],
    "regime_ma": [5],
    "b_hi": [0.55],
    "b_mid": [0.45],
    "b_lo": [0.35],
}


def score(panels, params):
    prox, _ = base_score(panels, params)  # ranking leg owned by strat_newhigh
    px, months = panels["px"], panels["months"]
    ma = int(params.get("regime_ma", 5))
    b_hi = float(params.get("b_hi", 0.55))
    b_mid = float(params.get("b_mid", 0.45))
    b_lo = float(params.get("b_lo", 0.35))

    ma_px = np.full_like(px, np.nan)
    for t in range(ma - 1, len(months)):
        ma_px[t] = np.nanmean(px[t - ma + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore"):
        above = (px > ma_px) & np.isfinite(px) & np.isfinite(ma_px)
        alive = np.isfinite(px)
    breadth = np.where(alive.sum(axis=1) > 0,
                       above.sum(axis=1) / np.maximum(alive.sum(axis=1), 1),
                       np.nan)

    exposure = np.zeros(len(months))
    for t in range(len(months)):
        b = breadth[t]
        if np.isnan(b):
            exposure[t] = 0.0
        elif b > b_hi:
            exposure[t] = 1.0
        elif b > b_mid:
            exposure[t] = 0.7
        elif b > b_lo:
            exposure[t] = 0.4
        else:
            exposure[t] = 0.0
    _ = pl.Series(breadth)  # keep polars import live (parity with tree style)
    return prox, exposure
