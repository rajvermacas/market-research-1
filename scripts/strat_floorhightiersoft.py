"""Candidate: floor-high rank under soft breadth-tier exposure (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank by
strat_floorhigh (floor-lift distance among names within max_dist of their
trailing high); exposure starts from strat_newhigh_tier breadth tiers but
remaps the four hard levels {1.0, 0.7, 0.4, 0.0} to softer per-trial values
{e_hi, e_mid, e_lo, e_cash} instead of snapping to cash.

Rationale: the binary/hard-tier gates jump exposure in big steps around
arbitrary breadth lines, whipsawing the book and dumping to zero on weak
participation. If breadth timing is directionally right but overshoots, a
softer mapping (e.g. never below 0.5) keeps the book in the compounders it
ranks while still scaling with participation. Unexplored cut: exposure tier
VALUES (prior loops only moved the breadth threshold lines).

PIT-safe: inherits both legs' discipline; the remap is a pointwise lookup,
no forward information.

SPACE = strat_floorhightier params + e_hi {1.0}, e_mid {0.85},
e_lo {0.7}, e_cash {0.3, 0.5}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [15],
    "max_dist": [0.06],
    "regime_ma": [18],
    "e_hi": [1.0],
    "e_mid": [0.85],
    "e_lo": [0.7],
    "e_cash": [0.3, 0.5],
}


def score(panels, params):
    rank, _ = _fh_score(panels, params)
    _, hard = _tier_score(panels, params)
    e_hi = float(params.get("e_hi", 1.0))
    e_mid = float(params.get("e_mid", 0.85))
    e_lo = float(params.get("e_lo", 0.7))
    e_cash = float(params.get("e_cash", 0.3))
    remap = {1.0: e_hi, 0.7: e_mid, 0.4: e_lo, 0.0: e_cash}
    soft = np.array([remap.get(float(v), float(v)) for v in hard])
    return rank, soft
