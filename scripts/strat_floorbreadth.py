"""Candidate: floor-lift rank under breadth-tier regime (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
rank by strat_floorlift log-distance above the trailing floor (structural
compounders) but the regime leg comes from strat_newhigh_tier breadth tiers
(fraction of live names above their own MA -> exposure 1.0/0.7/0.4/0.0)
instead of the binary/float index-vs-MA gate.

Rationale: the float index gate (weak_exp=0.4) is the loop's best forward
mechanism, but it keys off a single index-vs-MA cross; breadth moves slower
(names cross on different months) and may whipsaw less. Tests whether the
floor rank holds forward under a participation-scaled book.

PIT-safe: rank uses closes through px[m]; breadth uses closes through px[m]
only; NaN MA rows count as below-MA (conservative, never peeks).

SPACE = union of strat_floorlift.SPACE and strat_newhigh_tier.SPACE.
"""

from __future__ import annotations

from strat_floorlift import score as _floor_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_floorlift.SPACE and strat_newhigh_tier.SPACE"}


def score(panels, params):
    lift, _ = _floor_score(panels, params)
    _, exposure = _tier_score(panels, params)
    return lift, exposure
