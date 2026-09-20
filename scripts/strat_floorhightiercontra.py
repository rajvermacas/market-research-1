"""Candidate: contrarian floor sleeve in zero-breadth months (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank by
strat_floorhigh and exposure by strat_newhigh_tier breadth tiers — except in
zero-tier months (breadth below b_lo, book would sit in cash), when the book
instead holds the names CLOSEST above their trailing floor (score = -lift,
higher = tighter to the floor) at a capped `contra_e` exposure.

Rationale: the setup says cash in weak breadth, but weak breadth after a
drawdown is also when basing compounders sit tightest to their floors —
exactly the names the lift rank likes one regime later. A small contrarian
sleeve buys that basing instead of earning zero, capped so a continued slide
cannot dominate. If weak breadth only means further down, the cap plus the
floor seasoning bounds the damage and the trial trails.

PIT-safe: the sleeve switch reads the imported exposure at month t only;
lift uses closes through px[m]; no forward information.

SPACE = strat_floorhightier params + contra_e {0.25, 0.5}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_floorlift import score as _lift_score
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
    "contra_e": [0.25, 0.5],
}


def score(panels, params):
    rank, _ = _fh_score(panels, params)
    lift, _ = _lift_score(panels, params)
    _, exposure = _tier_score(panels, params)
    exposure = np.asarray(exposure, dtype=float)
    contra_e = float(params.get("contra_e", 0.25))
    out_rank = np.array(rank, dtype=float, copy=True)
    out_exp = np.array(exposure, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        if exposure[t] <= 0.0:
            elig = np.isfinite(rank[t]) & np.isfinite(lift[t])
            out_rank[t] = np.where(elig, -lift[t], np.nan)
            out_exp[t] = contra_e
    return out_rank, out_exp
