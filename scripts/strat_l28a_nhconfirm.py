"""Candidate: liquid-cohort NEW-HIGH share re-arm (Loop-28 A).

Setup in words: rank, eligibility, breadth-tier exposure and book are exactly
strat_l23a_liqconfirm (imported, never copied). Liquid cohort = names whose
median daily traded value over the last nh_days sessions (date < months[t])
is >= nh_min (strat_l22b_liqbreadth.liquid_mask, imported). nh_t = share of
that cohort whose close px[t] equals or exceeds its highest month-end close
over the prior nh_lb months (px[t-nh_lb..t-1]; a fresh nh_lb-month high).
When the tier exposure is below 1 and nh_t > nh_thr, exposure =
max(exposure, nh_to).

Hypothesis (theory): the tier compares prices to an 18-month average, so it
re-arms late after a correction; a surge of liquid names printing fresh
12-month highs is leadership confirmation that the correction is over, and
the book (a fresh-high book) is exactly what those names feed.
Falsifier: no cell lifts train CAGR at DD <= -17.22, or the gain is one
episode (the l27o_corerearm failure mode).

Novelty: l23a_newlows (new-LOW share, DEAD, a cut); l27o_corerearm
(liquid-core trailing RETURN re-arm, PARTIAL); breadth rows read share above
an average, not share at fresh highs. No row uses the new-HIGH share as a
re-arm. Threshold chosen from the pre-2022 distribution of nh_t only.

Off-switch: nh_to = 0 -> champion exactly.
SPACE: nh_lb {12}, nh_thr {0.10,0.15,0.20,0.25}, nh_to {0,0.7,1.0}, nh_min 5e6,
nh_days 40.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _base
from strat_l22b_liqbreadth import liquid_mask

NEEDS_DAILY = True
SPACE = {"nh_lb": [12], "nh_thr": [0.10, 0.15, 0.20, 0.25], "nh_to": [0.0, 0.7, 1.0],
         "nh_min": [5e6], "nh_days": [40]}


def nh_share(panels, lb: int, liq_min: float, liq_days: int) -> np.ndarray:
    px = np.asarray(panels["px"], dtype=float)
    liq = liquid_mask(panels, liq_min, liq_days)
    out = np.full(px.shape[0], np.nan)
    for t in range(lb, px.shape[0]):
        w = px[t - lb:t]
        full = np.isfinite(w).all(axis=0) & np.isfinite(px[t]) & liq[t]
        if full.sum() < 30:
            continue
        hi = np.where(full, np.nanmax(np.where(np.isfinite(w), w, -np.inf), axis=0), np.inf)
        out[t] = float((px[t][full] >= hi[full]).mean())
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    to = float(params.get("nh_to", 0.0))
    if to <= 0:
        return scores, exposure
    s = nh_share(panels, int(params.get("nh_lb", 12)), float(params.get("nh_min", 5e6)),
                 int(params.get("nh_days", 40)))
    thr = float(params.get("nh_thr", 0.15))
    out = np.asarray(exposure, dtype=float).copy()
    for t in range(len(out)):
        if out[t] < 1.0 and np.isfinite(s[t]) and s[t] > thr:
            out[t] = max(out[t], to)
    return scores, out
