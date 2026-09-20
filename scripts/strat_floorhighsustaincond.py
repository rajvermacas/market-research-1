"""Candidate: regime-conditional print-continuity gate (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank and
regime from strat_floorhighfastgate, with the sustainprint continuity gate
applied at STRICTNESS CONDITIONED on the breadth regime — in full-risk
months (tier exposure 1.0) any prior print within `sustain_lo` months
suffices; in scaled months the name must have printed within the tighter
`sustain_hi` window... implemented as: required print-free drought is
shorter when breadth is weak (weak months demand hotter breakouts, strong
months tolerate older ones).

Rationale: sustain_lb 6 beat 3 on the ledger, but a single window for all
regimes is crude — weak-breadth months are when stale breakouts fail, while
full-risk months can carry older printers. Conditioning gate strictness on
regime should keep sustainprint's train gain while cutting its large-cap
train cost (the standing yellow flag: every timing filter subtracts on
large/mid train). If conditioning is overfit decoration, this ties sustain
slb6 and says so.

PIT-safe: the window choice reads the imported exposure at month t only;
print history through px[m], never peeks.

SPACE = strat_floorhighfastgate params + sustain_lo {6}, sustain_hi {2}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfastgate import score as _fg_score
from strat_newhigh import score as _high_score
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
    "fast_ma": [6],
    "sustain_lo": [6],
    "sustain_hi": [2],
}


def score(panels, params):
    rank, exposure = _fg_score(panels, params)
    prox, _ = _high_score(panels, params)
    _, tier_exp = _tier_score(panels, params)
    tier_exp = np.asarray(tier_exp, dtype=float)
    slo = int(params.get("sustain_lo", 6))
    shi = int(params.get("sustain_hi", 2))
    out = np.array(rank, dtype=float, copy=True)
    with np.errstate(invalid="ignore"):
        printed = np.isfinite(prox) & (prox >= -0.001)
    for t in range(rank.shape[0]):
        w = slo if tier_exp[t] >= 1.0 else shi
        lo = max(0, t - w)
        prior = printed[lo:t].any(axis=0) if t > lo else np.zeros(rank.shape[1], bool)
        out[t] = np.where(np.isfinite(rank[t]) & prior, rank[t], np.nan)
    return out, exposure
