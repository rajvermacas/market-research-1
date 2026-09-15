"""Candidate: reversal-skipped floor-high rank under breadth-tier regime.

Triple composition (imported, never copied): rank by strat_floorhighskip
(floor-lift distance among near-high names minus the hottest last-1m
tail), regime by strat_newhigh_tier breadth tiers. Tests whether the
skip's forward pop (fwd +43.7% but train DD -38.8% breach) survives under
the tier regime that tamed the same DD on the unskipped line.

PIT-safe: both legs use closes through px[m] only.
"""

from __future__ import annotations

from strat_floorhighskip import score as _skip_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_floorhighskip and strat_newhigh_tier params"}


def score(panels, params):
    rank, _ = _skip_score(panels, params)
    _, exposure = _tier_score(panels, params)
    return rank, exposure
