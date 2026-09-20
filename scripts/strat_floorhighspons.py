"""Candidate: sponsorship rank on the floor-seasoned near-high universe.

Volume-confirmation cut (imported, never copied): eligibility is the
strat_floorhigh mask (seasoned floor + positive 12m trend + within
max_dist of the trailing high), but the rank is sponsorship — the
near-vs-baseline daily-volume expansion ratio from strat_liqtrend —
instead of lift depth. Names pressing their highs on expanding volume
(real accumulation) should out-hold names drifting there on thin
turnover. Regime is the breadth-tier exposure from strat_newhigh_tier.

Rationale: the sponsorship *gate* (strat_floorhighliq) died by
subtracting too much; a sponsorship *rank* keeps the full tier book
invested and only re-orders it toward accumulated names. Uptrend-only
eligibility comes free from both legs.

PIT-safe: floorhigh uses closes through px[m]; liqtrend uses daily bars
with date < months[m] plus closes through px[m]; breadth uses closes
through px[m].

SPACE = union of strat_floorhigh / strat_liqtrend / strat_newhigh_tier params.
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_liqtrend import score as _liq_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = True
SPACE = {"note": "union of strat_floorhigh/strat_liqtrend/strat_newhigh_tier params"}


def score(panels, params):
    elig, _ = _fh_score(panels, params)
    spons, _ = _liq_score(panels, params)
    _, exposure = _tier_score(panels, params)
    out = np.full_like(elig, np.nan)
    ok = np.isfinite(elig) & np.isfinite(spons)
    out[ok] = spons[ok]
    return out, exposure
