"""Candidate: tier-shape exposure with the print-continuity gate keyed to
the DEPLOYED exposure (strategy_lab contract).

Mutation composing tested mechanisms (imported, never copied): rank and tier
exposure from strat_floorhighfastgate, prox from strat_newhigh — the
conditional print-continuity gate of strat_floorhighsustaincond re-applied,
but the conditioning variable is the exposure the book actually runs after
the tier-shape re-valuation (tier_floor/tier_lo/tier_mid), not the original
0.4/0.7/1.0 ladder.

Rationale: strat_floorhightiershape lifts the mid tier (0.7 -> tier_mid,
often 1.0); strat_floorhighsustaincond still treats those months as scaled
risk and demands the hotter `sustain_hi` print. Once the book is fully
invested in those months, the gate's strictness should follow the money, not
the vestigial tier label. If the conditioning variable was doing real work,
this shifts eligibility in the lifted months and shows up in CAGR/DD; if it
was decoration, this ties the tiershape file.

PIT-safe: rank/eligibility logic mirrors the imported pieces; the window
choice reads only exposure at month t and print history through px[m].

SPACE = strat_floorhighfastgate params + tier_floor {0.0}, tier_lo {0.4,0.55},
        tier_mid {0.7,0.85,1.0}, sustain_lo {4,6}, sustain_hi {1,2}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfastgate import score as _fg_score
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
    "fast_ma": [9],
    "sustain_lo": [4, 6],
    "sustain_hi": [1, 2],
    "tier_floor": [0.0],
    "tier_lo": [0.4, 0.55],
    "tier_mid": [0.7, 0.85, 1.0],
}


def _shape(E, tfloor, tlo, tmid):
    return np.clip(np.where(
        E >= 1.0, np.minimum(E, 1.0),
        np.where(E >= 0.7, tmid,
                 np.where(E >= 0.4, tlo,
                          np.where(E > 0.0, tlo, tfloor)))), 0.0, 1.0)


def score(panels, params):
    rank, exposure = _fg_score(panels, params)
    prox, _ = _high_score(panels, params)
    slo = int(params.get("sustain_lo", 6))
    shi = int(params.get("sustain_hi", 2))
    E = _shape(np.asarray(exposure, dtype=float),
               float(params.get("tier_floor", 0.0)),
               float(params.get("tier_lo", 0.4)),
               float(params.get("tier_mid", 0.7)))

    with np.errstate(invalid="ignore"):
        printed = np.isfinite(prox) & (prox >= -0.001)
    out = np.array(rank, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        w = slo if E[t] >= 1.0 else shi
        lo = max(0, t - w)
        prior = printed[lo:t].any(axis=0) if t > lo else np.zeros(rank.shape[1], bool)
        out[t] = np.where(np.isfinite(rank[t]) & prior, rank[t], np.nan)
    return out, E
