"""Candidate: lift-tightness composite rank under breadth-tier regime.

Fresh rank statistic (fifth cut) on the floor-seasoned near-high universe:
eligibility is the strat_floorhigh mask (imported, never copied), but the
rank is the INTERACTION of its two legs — log-distance above the trailing
floor divided by (1 + distance below the trailing high), so the book
prefers names that are simultaneously deep above their floor AND tight to
their high. Rank-by-lift alone crowns violent extenders that have fallen
back from their high yet remain eligible; the divisor demotes exactly
those. Regime is the breadth-tier exposure from strat_newhigh_tier.

PIT-safe: lift, proximity and breadth all use month-end closes through
px[m] only for the holding month starting months[m].

SPACE = union of strat_floorhigh / strat_newhigh_tier params (no new params).
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_newhigh import score as _high_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_floorhigh/strat_newhigh_tier params"}


def score(panels, params):
    lift, _ = _fh_score(panels, params)
    prox, _ = _high_score(panels, params)
    _, exposure = _tier_score(panels, params)
    dist = -prox  # >= 0, 0 = at the high; NaN where ineligible
    out = np.full_like(lift, np.nan)
    ok = np.isfinite(lift) & np.isfinite(prox)
    with np.errstate(invalid="ignore", divide="ignore"):
        out[ok] = lift[ok] / (1.0 + dist[ok])
    return out, exposure
