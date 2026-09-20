"""Candidate: eligibility-persistence-weighted rank at the current best's base
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): rank, gates
and shaped exposure from strat_floorhightiershape, with the score multiplied
by a persistence factor built from how often the name has been eligible
(finite rank) over the last `pers_lb` months:

    score = rank * (1 + pers_w * share_of_recent_months_eligible)

Rationale: the base rank already contains the eligibility gates, but it cannot
distinguish a name that keeps qualifying month after month from a one-month
wonder once both are eligible. A persistent qualifier (fresh prints and an
intact short trend for most of the last K months) is a different animal from a
single pop. If persistence carries no information, the weighted rank trails;
if it does, it should buy the same return from fewer marginal names.

PIT-safe: the eligibility share uses only rank rows up to month t.

SPACE = strat_floorhightiershape params + pers_lb {3,6,12}, pers_w {0.25,0.5,1.0}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhightiershape import score as _ts_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "floor_lb": [19],
    "lookback": [10],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [5],
    "sustain_lo": [3],
    "sustain_hi": [2],
    "tier_lo": [1.0],
    "tier_mid": [1.0],
    "pers_lb": [3, 6, 12],
    "pers_w": [0.25, 0.5, 1.0],
}


def score(panels, params):
    rank, exposure = _ts_score(panels, params)
    plb = int(params.get("pers_lb", 6))
    w = float(params.get("pers_w", 0.5))
    fin = np.isfinite(rank)

    out = np.array(rank, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        lo = max(0, t - plb + 1)
        n = t - lo + 1
        share = fin[lo:t + 1].sum(axis=0) / n
        out[t] = rank[t] * (1.0 + w * share)
    out = np.where(fin, out, np.nan)
    return out, exposure
