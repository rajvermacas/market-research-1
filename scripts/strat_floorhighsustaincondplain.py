"""Candidate: regime-conditional print-continuity gate on PLAIN fresh rank
(strategy_lab contract).

Ablation of strat_floorhighsustaincond (imported, never copied): the same
regime-conditional continuity gate (prior print within sustain_lo months in
full-risk months, sustain_hi in scaled months) applied to the PLAIN fresh
rank from strat_floorhighfresh — no above-6m-MA fast gate.

Rationale: sustainplain showed the sustain effect needs the fast gate
(-0.3pp without it); this asks whether the CONDITIONAL form also needs it,
or whether regime-conditioning rescues the plain rank. If this ties
sustaincond, the fast gate is decoration on the final form; if it trails by
a similar margin, the gate interaction is confirmed twice and the
fastgate+sustaincond stack is the terminal book.

PIT-safe: window choice reads imported exposure at month t only; print
history through px[m], never peeks.

SPACE = strat_floorhighfresh params + sustain_lo {6}, sustain_hi {2}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _fresh_score
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
    "sustain_lo": [6],
    "sustain_hi": [2],
}


def score(panels, params):
    rank, exposure = _fresh_score(panels, params)
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
