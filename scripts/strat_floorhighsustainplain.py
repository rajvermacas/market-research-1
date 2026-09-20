"""Candidate: sustained prints WITHOUT the fast-trend gate (strategy_lab contract).

Ablation of strat_floorhighsustainprint (imported, never copied): same print
requirements (printing now + printed within sustain_lb months) applied to
the PLAIN fresh rank from strat_floorhighfresh instead of the fast-gated
rank — i.e. no above-6m-MA requirement.

Rationale: fastgate beat fresh by only +0.1pp on the ledger and never binds
on the validation universes, so it may be decoration. If sustain carries
the effect alone, this ties sustainprint and the fast gate can be dropped
as complexity without edge; if the gate interacts (sustain only works on
short-trend names), this trails and the interaction is real.

PIT-safe: inherits both legs' discipline; print history through px[m].

SPACE = strat_floorhighsustainprint params (gate swap is structural).
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _fresh_score
from strat_newhigh import score as _high_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "sustain_lb": [6],
}


def score(panels, params):
    rank, exposure = _fresh_score(panels, params)
    prox, _ = _high_score(panels, params)
    slb = int(params.get("sustain_lb", 6))
    out = np.array(rank, dtype=float, copy=True)
    with np.errstate(invalid="ignore"):
        printed = np.isfinite(prox) & (prox >= -0.001)
    for t in range(rank.shape[0]):
        lo = max(0, t - slb)
        prior = printed[lo:t].any(axis=0) if t > lo else np.zeros(rank.shape[1], bool)
        out[t] = np.where(np.isfinite(rank[t]) & prior, rank[t], np.nan)
    return out, exposure
