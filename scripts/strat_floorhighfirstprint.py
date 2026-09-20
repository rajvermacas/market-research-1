"""Candidate: first-print breakouts under fast gate (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank and
regime from strat_floorhighfastgate (fresh printed high + above short
trend, under breadth tiers), but eligible only if the name did NOT print a
trailing high in the prior `excl_lb` months — the FIRST breakout after a
drought, not a repeated printer.

Rationale: a name printing highs every month is already extended and
crowded; the first print after months away from the high is the moment of
maximum surprise and sponsorship arrival. strat_floorhighentrant tested
freshness to the SCREEN (trailed); this tests freshness of the PRINT
itself — repeated printers vs debut printers. If extended runners still
compound best, this trails and the tail lesson extends to entries.

PIT-safe: prior-print status uses the imported proximity history through
px[m] only; months before the lookback window read as no-print
(conservative for early history, never peeks).

SPACE = strat_floorhighfastgate params + excl_lb {3, 6}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfastgate import score as _fg_score
from strat_newhigh import score as _high_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [6],
    "excl_lb": [3, 6],
}


def score(panels, params):
    rank, exposure = _fg_score(panels, params)
    prox, _ = _high_score(panels, params)
    elb = int(params.get("excl_lb", 3))
    out = np.array(rank, dtype=float, copy=True)
    with np.errstate(invalid="ignore"):
        printed = np.isfinite(prox) & (prox >= -0.001)
    for t in range(rank.shape[0]):
        lo = max(0, t - elb)
        prior = printed[lo:t].any(axis=0) if t > lo else np.zeros(rank.shape[1], bool)
        out[t] = np.where(np.isfinite(rank[t]) & ~prior, rank[t], np.nan)
    return out, exposure
