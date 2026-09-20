"""Candidate: fresh-print rank under short-trend gate (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank and
breadth-tier regime from strat_floorhighfresh, but eligible only for names
closing above their own `fast_ma`-month average in the ranking month — a
hard short-trend gate instead of the participation-fraction gate of
strat_floorhighpart (which trailed by ~1.5pp with p_min 0.5 over 6 months).

Rationale: participation counts how OFTEN a name held its long trend; the
hard gate asks whether it holds a SHORT trend right now. A fresh printed
high with the name already back below its 6m average is a failed breakout
by definition — this drops exactly those. If short wiggles are noise around
intact breakouts, the gate churns eligibility and trails.

PIT-safe: the gate uses closes through px[m] only; NaN MA rows (warm-up)
read as failing the gate (conservative, never peeks).

SPACE = strat_floorhighfresh params + fast_ma {3, 6}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _fresh_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [3, 6],
}


def score(panels, params):
    rank, exposure = _fresh_score(panels, params)
    px, months = panels["px"], panels["months"]
    fma = int(params.get("fast_ma", 6))
    ma_px = np.full_like(px, np.nan)
    for t in range(fma - 1, len(months)):
        ma_px[t] = np.nanmean(px[t - fma + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore"):
        gate = np.isfinite(px) & np.isfinite(ma_px) & (px > ma_px)
    return np.where(np.isfinite(rank) & gate, rank, np.nan), exposure
