"""Candidate: floor-high rank under dual breadth-x-index regime
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank by
strat_floorhigh, exposure = breadth-tier level from strat_newhigh_tier
(1.0/0.7/0.4/0.0) MULTIPLIED by the index-vs-MA gate from strat_floorlift
(1.0 when the equal-weight index prints above its regime_ma-month average,
else weak_exp).

Rationale: breadth tiers scale with participation but can stay fully
invested into a narrow, index-driven drawdown where few names hold above
their MAs yet breadth hovers mid-tier; the index gate is the complementary
cut (level, not participation). Requiring BOTH for full size should cut the
left tail cheaper than tightening either threshold alone — and if they
disagree often, invested% will show it.

PIT-safe: both legs use closes through px[m] only; the product is pointwise
per month, no forward information.

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
    exposure = np.asarray(tier_exp, dtype=float) * np.asarray(idx_gate, dtype=float)
    return rank, exposure
