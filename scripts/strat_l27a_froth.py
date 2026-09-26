"""Candidate: illiquid-tail FROTH exposure cut (Loop-27 A).

Setup in words: rank, eligibility and breadth-tier exposure are exactly
strat_l23a_liqconfirm (imported, never copied). The size spread is
strat_l27a_sizeflight.size_spread (imported): rel_t = mean trailing fr_k-month
return of the illiquid names minus that of the liquid core (liquid = median
daily traded value over the last fr_days sessions, date < months[t], >= fr_min;
returns from closes through px[t], clipped to [-0.9, 3]).
If rel_t > +fr_thr (the illiquid tail has run far ahead of the liquid core:
speculative froth), exposure *= (1 - fr_cut) for that month.

Hypothesis: small-cap unwinds (Jan 2018, Jan 2022, early 2025) are preceded
by a burst of illiquid-tail outperformance while breadth is still at full
tier; trimming exposure in froth months pre-empts the first leg of the DD,
which the breadth tier (a level vs an 18-month average) only sees later.
Honest disclosure: the sign was chosen after strat_l27a_sizeflight (the
opposite sign, DEAD) showed the tail lagging only AFTER the falls, and a
diagnostic print showed rel spikes in Dec-2017/Jan-2018/Jan-2022 — so this is
a data-informed hypothesis; its thresholds need a plateau, not a single cell.
Falsifier: DD does not improve at any cell, or only a single knife-edge cell.

Novelty: sizeflight (L27, DEAD) = the opposite-sign flight-to-quality cut.
Liquid-cohort breadth rows (l22b liqbreadth, l23a liqconfirm/liqrank/liqramp)
read breadth levels, not a return spread. No registry row uses illiquid-minus-
liquid relative return (speculative froth) as an exposure cut.

Off-switch: fr_cut = 0 -> champion exactly.
SPACE: fr_k {1,2,3}, fr_thr {0.03,0.04,0.05,0.06}, fr_cut {0,0.3,0.5,1.0},
fr_min {1e7,2e7,4e7}, fr_days 40.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _base
from strat_l27a_sizeflight import size_spread

NEEDS_DAILY = True
SPACE = {"fr_k": [1, 2, 3], "fr_thr": [0.03, 0.04, 0.05, 0.06], "fr_cut": [0.0, 0.3, 0.5, 1.0],
         "fr_min": [1e7, 2e7, 4e7], "fr_days": [40]}


def score(panels, params):
    scores, exposure = _base(panels, params)
    cut = float(params.get("fr_cut", 0.0))
    if cut <= 0:
        return scores, exposure
    rel = size_spread(panels, {"sf_k": int(params.get("fr_k", 2)),
                               "sf_min": float(params.get("fr_min", 2e7)),
                               "sf_days": int(params.get("fr_days", 40))})
    thr = float(params.get("fr_thr", 0.04))
    out = np.asarray(exposure, dtype=float).copy()
    for t in range(len(out)):
        if np.isfinite(rel[t]) and rel[t] > thr:
            out[t] = out[t] * (1.0 - cut)
    return scores, out
