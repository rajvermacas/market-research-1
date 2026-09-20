"""Candidate: multi-print continuity requirement (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank and
regime from strat_floorhighfastgate, eligible only with at least
`min_prints` trailing-high prints (including the current month) within the
prior sustain window — strictly stronger than sustainprint's "any single
prior print".

Rationale: sustainprint slb6 says continuity matters; this asks HOW MUCH
continuity — one prior print vs a cluster. If sponsorship persistence is
monotone, min_prints 2-3 beats slb6; if a single confirmation suffices and
further demands just shrink the book into overfit, this trails and the dose
response is mapped.

PIT-safe: print counts use imported proximity history through px[m] only.

SPACE = strat_floorhighsustainprint params + min_prints {2, 3}.
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
    "sustain_lb": [6],
    "min_prints": [2, 3],
}


def score(panels, params):
    rank, exposure = _fg_score(panels, params)
    prox, _ = _high_score(panels, params)
    slb = int(params.get("sustain_lb", 6))
    mp = int(params.get("min_prints", 2))
    out = np.array(rank, dtype=float, copy=True)
    with np.errstate(invalid="ignore"):
        printed = np.isfinite(prox) & (prox >= -0.001)
    for t in range(rank.shape[0]):
        lo = max(0, t - slb)
        cnt = printed[lo:t + 1].sum(axis=0)
        out[t] = np.where(np.isfinite(rank[t]) & (cnt >= mp), rank[t], np.nan)
    return out, exposure
