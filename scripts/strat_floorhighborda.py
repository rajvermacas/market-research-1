"""Candidate: Borda-consensus rank of lift and proximity under breadth tiers
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): among
floorhigh-eligible names, rank by positional BORDA consensus of the lift
order (strat_floorlift leg, structural compounders) and the proximity order
(strat_newhigh leg, fresh breakouts) — score = rankpos_lift + rankpos_prox,
lower = better, implemented as its negation so higher = better for the
harness. Regime is strat_newhigh_tier breadth tiers.

Rationale: strat_floorhighblend fused the two dimensions cardinally
(z-scores) and subtracted; positional consensus is the ordinal alternative —
robust to the heavy-tailed lift outliers that dominate z-scores (a few
10-baggers set the scale and compress everything else). If outliers drove
the blend's failure, Borda recovers the combination; if proximity truly
subtracts (partrank was decisive), this trails too and the rank question is
settled.

PIT-safe: positional ranks are purely cross-sectional within month t, both
legs use closes through px[m]; no forward information.

SPACE = strat_floorhightier params (consensus is structural, no knobs).
"""

from __future__ import annotations

import numpy as np

from strat_floorlift import score as _lift_score
from strat_newhigh import score as _high_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = False
SPACE = {"note": "strat_floorhightier params; Borda consensus is structural"}


def _rankpos(v):
    order = np.argsort(np.argsort(v, kind="stable"), kind="stable").astype(float)
    return order


def score(panels, params):
    lift, _ = _lift_score(panels, params)
    prox, _ = _high_score(panels, params)
    _, exposure = _tier_score(panels, params)
    out = np.full_like(lift, np.nan)
    for t in range(lift.shape[0]):
        ok = np.isfinite(lift[t]) & np.isfinite(prox[t])
        if ok.sum() < 2:
            continue
        borda = _rankpos(lift[t][ok]) + _rankpos(prox[t][ok])
        s = np.full(lift.shape[1], np.nan)
        s[np.flatnonzero(ok)] = -borda
        out[t] = s
    return out, exposure
