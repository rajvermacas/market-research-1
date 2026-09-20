"""Candidate: fresh-print floorhigh under breadth tiers (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank by
strat_floorhigh, regime by strat_newhigh_tier breadth tiers — but eligible
only for names PRINTING a trailing-high close in the ranking month itself
(prox == 0 within a 0.1% tolerance), not merely sitting within max_dist of
it.

Rationale: max_dist admits names up to 5.5% OFF their high — bases that
failed, faded breakouts, drifters. The setup in words is "breakout timing on
structural compounders": demanding the print itself selects the(names the
market is confirming right now. Eligible count falls, so the harness
minimum-count rule yields cash more often; invested% arbitrates whether the
concentration pays.

PIT-safe: the print test uses closes through px[m] only (prox[t] from
strat_newhigh is month-t information), never peeks.

SPACE = strat_floorhightier params (max_dist kept for the imported legs'
mask; the print gate binds first).
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_newhigh import score as _high_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
}


def score(panels, params):
    rank, _ = _fh_score(panels, params)
    prox, _ = _high_score(panels, params)
    _, exposure = _tier_score(panels, params)
    with np.errstate(invalid="ignore"):
        fresh = np.isfinite(prox) & (prox >= -0.001)
    return np.where(np.isfinite(rank) & fresh, rank, np.nan), exposure
