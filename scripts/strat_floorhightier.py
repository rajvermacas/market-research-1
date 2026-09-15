"""Candidate: floor-high rank under breadth-tier regime (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
rank by strat_floorhigh (floor-lift distance among names within max_dist
of their trailing high) but the regime leg comes from strat_newhigh_tier
breadth tiers (fraction of live names above their own MA ->
exposure 1.0/0.7/0.4/0.0) instead of the binary/float index-vs-MA gate.

Rationale: strat_floorbreadth put breadth tiers under a floorlift rank and
trailed; this puts them under the stronger floorhigh rank, where the
short-floor variants' train DD (-44% to -54%) is the binding problem and a
participation-scaled book may cut it with less forward cost than the
index-vs-MA gate.

PIT-safe: rank uses closes through px[m]; breadth uses closes through
px[m] only; NaN MA rows count as below-MA (conservative, never peeks).

SPACE = union of strat_floorhigh and strat_newhigh_tier params.
"""

from __future__ import annotations

from strat_floorhigh import score as _fh_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_floorhigh and strat_newhigh_tier params"}


def score(panels, params):
    rank, _ = _fh_score(panels, params)
    _, exposure = _tier_score(panels, params)
    return rank, exposure
