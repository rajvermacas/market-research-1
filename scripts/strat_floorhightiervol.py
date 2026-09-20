"""Candidate: floor-high tier book with volatility exclusion (strategy_lab contract).

Mutation composing three tested mechanisms (imported, never copied):
rank by strat_floorhigh (floor-lift distance among names within max_dist
of their trailing high), regime (breadth-tier exposure 1.0/0.7/0.4/0.0)
from strat_newhigh_tier, plus a volatility exclusion leg: drop names whose
trailing 3m realized monthly vol (recovered as -1 * strat_volsqueeze
score) sits above the `vol_q` cross-sectional quantile that month.

Rationale: the tier book's train DD (-18.3%) is book-level, and
position-level trailing stops did not fix it; the DD months are likely
driven by the most violent names in the book. An exclusion (rather than
a vol-scaled rank, cf. strat_volfloor) keeps the proven lift rank intact
and only removes the right tail of realized vol.

PIT-safe: rank, breadth and vol all use month-end closes through px[m]
only for the holding month starting months[m]; the quantile is computed
per month over concurrently finite vols, never peeks.

SPACE = union of strat_floorhigh / strat_newhigh_tier params + vol_q {0.75}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_newhigh_tier import score as _tier_score
from strat_volsqueeze import score as _sq_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_floorhigh/strat_newhigh_tier/volsqueeze params + vol_q"}


def score(panels, params):
    rank, _ = _fh_score(panels, params)
    _, exposure = _tier_score(panels, params)
    sq, _ = _sq_score(panels, params)
    vol = -sq  # trailing 3m realized monthly vol; NaN where ineligible
    q = float(params.get("vol_q", 0.75))
    out = rank.copy()
    for t in range(rank.shape[0]):
        v = vol[t]
        ok = np.isfinite(v)
        if ok.sum() < 4:
            continue
        cut = np.quantile(v[ok], q)
        out[t, ok & (v > cut)] = np.nan
    return out, exposure
