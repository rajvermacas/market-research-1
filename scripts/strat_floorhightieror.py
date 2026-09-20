"""Candidate: floor-high rank under either-or breadth/index regime
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank by
strat_floorhigh; exposure = the MAX of the breadth-tier level from
strat_newhigh_tier (1.0/0.7/0.4/0.0) and the index-vs-MA gate from
strat_floorlift (1.0 above the regime_ma-month index average, else
weak_exp) — either risk-on signal suffices for size.

Rationale: the dual (product) version never bound — the index gate at ma18
agrees with breadth tiers almost always, so requiring both changed nothing.
The OR version asks the opposite question: do the RARE disagreements cost
the book months where one signal saw risk-on and the other vetoed? If vetoes
were false alarms, OR recovers them and beats the base; if vetoes were
protective, OR trails on DD and the veto question is settled from both
sides.

PIT-safe: pointwise max of two PIT-safe exposures at month t; no forward
information.

SPACE = strat_floorhightier params + weak_exp {0.0, 0.4}.
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
    "weak_exp": [0.0, 0.4],
}


def score(panels, params):
    rank, _ = _fh_score(panels, params)
    _, tier_exp = _tier_score(panels, params)
    _, idx_gate = _lift_score(panels, {**params, "weak_exp": float(params.get("weak_exp", 0.4))})
    exposure = np.maximum(np.asarray(tier_exp, dtype=float),
                          np.asarray(idx_gate, dtype=float))
    return rank, exposure
