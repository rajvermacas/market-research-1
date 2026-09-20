"""Candidate: floor-high tier regime with holding-duration cap (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank and
breadth-tier exposure come from strat_floorhightier (floor-lift distance
among names within max_dist of their trailing high, exposure 1.0/0.7/0.4/0.0
from market breadth), plus a freshness cap — a name is dropped after
`max_hold` months held however it ranks.

Rationale: the tier book's winners are far-distance runners (the no-scale-out
lesson: the edge lives in the tail), but a name that has sat in the book for
a year without re-earning a top rank is a stale compounder, not a breakout.
max_hold forces rotation back into fresh breakouts while the tier regime
still governs market exposure. Unexplored cut: holding-duration x tier
regime interaction.

PIT-safe: rank/regime use closes through px[m] only; the hold clock starts
at entry month (harness machinery), never peeks.

SPACE = strat_floorhightier params + max_hold {3, 6, 9, 12}.
"""

from __future__ import annotations

from strat_floorhightier import score as _tier_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [18],
    "lookback": [15],
    "max_dist": [0.05],
    "regime_ma": [18],
    "max_hold": [3, 6, 9, 12],
}


def score(panels, params):
    rank, exposure = _tier_score(panels, params)
    max_hold = int(params.get("max_hold", 6))
    return rank, exposure, {"max_hold": max_hold}
