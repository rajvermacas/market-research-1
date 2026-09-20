"""Candidate: entrant-priority floorhigh rank under breadth tiers
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank by
strat_floorhigh, regime by strat_newhigh_tier breadth tiers — but names that
JUST entered the eligible set (finite rank this month, NaN `entry_lb` months
ago) sort ahead of long-eligible incumbents, each group ordered by lift.
Encoded as score = lift + bonus * entrant with bonus in {5, 20}, both far
above any plausible log-lift so the entrant group strictly dominates while
lift still orders within groups.

Rationale: the setup in words is breakout timing — a name screening fresh
this month IS the breakout; a name eligible for a year is a stale
compounder the rank has never Casinos out. strat_floorhighfresh demands a
printed high; this is the softer version (fresh to the SCREEN, not to the
high). If staleness is the drag, entrant priority beats the base; if
seasoning helps, it trails.

PIT-safe: entrant status uses the imported rank's own NaN history through
px[m] only, never peeks.

SPACE = strat_floorhightier params + entry_lb {3, 6}, bonus {5, 20}.
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
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "entry_lb": [3, 6],
    "bonus": [5, 20],
}


def score(panels, params):
    rank, _ = _fh_score(panels, params)
    _, exposure = _tier_score(panels, params)
    elb = int(params.get("entry_lb", 3))
    bonus = float(params.get("bonus", 5.0))
    out = np.full_like(rank, np.nan)
    for t in range(rank.shape[0]):
        ok = np.isfinite(rank[t])
        if t >= elb:
            entrant = ok & ~np.isfinite(rank[t - elb])
        else:
            entrant = np.zeros_like(ok)
        out[t] = np.where(ok, rank[t] + bonus * entrant, np.nan)
    return out, exposure
