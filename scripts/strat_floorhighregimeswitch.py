"""Candidate: regime-switched rank — lift in full risk, proximity in weak months
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): the RANK
itself switches with the breadth regime from strat_newhigh_tier. In full-risk
months (tier exposure 1.0) rank by strat_floorhigh lift (structural
compounders, the base book); in scaled/cash months rank by strat_newhigh
proximity (only fresh breakouts earn weak-breadth risk). Exposure leg is the
breadth tiers unchanged.

Rationale: weak-breadth months are when compounders consolidate and fresh
breakouts diverge — ranking the same lift book regardless of regime wastes
the rank on names going nowhere that month. If rank-regime fit matters, the
switch beats both single-rank versions; if not, it lands between them.

PIT-safe: the switch reads the imported exposure value at month t only,
both rank legs use closes through px[m]; no forward information.

SPACE = strat_floorhightier params (the switch is structural).
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_newhigh import score as _high_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = False
SPACE = {"note": "strat_floorhightier params; rank switch is structural"}


def score(panels, params):
    lift_rank, _ = _fh_score(panels, params)
    prox, _ = _high_score(panels, params)
    _, exposure = _tier_score(panels, params)
    exposure = np.asarray(exposure, dtype=float)
    out = np.full_like(lift_rank, np.nan)
    for t in range(lift_rank.shape[0]):
        full = exposure[t] >= 1.0
        leg = lift_rank[t] if full else prox[t]
        elig = np.isfinite(lift_rank[t]) & np.isfinite(prox[t])
        out[t] = np.where(elig, np.where(np.isfinite(leg), leg, np.nan), np.nan)
    return out, exposure
