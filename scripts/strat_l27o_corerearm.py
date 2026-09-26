"""Candidate: liquid-core rebound re-arm (Loop-27 orchestrator, pre-registered).

Setup in words: rank, eligibility and breadth-tier exposure exactly as
strat_l23a_liqconfirm (imported). core_t = mean clipped cr_k-month return of
the l22b liquid_mask cohort (median traded value >= cr_min over cr_days
sessions, dates < months[t]; closes through px[t]). If core_t > +cr_thr and the
champion's exposure is below 1, exposure is raised to max(exposure, cr_to).

Hypothesis (sign fixed before any trial, no diagnostic run): the breadth tiers
compare a share against an 18-month mean and so re-arm late after a fall; a
strong return by the liquid core marks a recovery the tiers have not yet
seen. Falsifier: no cell lifts train CAGR above 30.09 without deepening DD
beyond -17.22 by more than half the gain.

Novelty: exposure hysteresis and breadth ramps (legacy, DEAD) reshaped the
breadth signal itself; liqramp (L23, KEEP-not-promoted) is a continuous ramp
on the liquid-cohort breadth. None re-arms on the liquid core's own RETURN.
Base: the L25 champion under realistic execution. Off-switch cr_to = 0.
"""
from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _base
from strat_l22b_liqbreadth import liquid_mask

NEEDS_DAILY = True
SPACE = {"cr_k": [2, 3, 6], "cr_thr": [0.08, 0.12, 0.2], "cr_to": [0.0, 0.7, 1.0],
         "cr_min": [2e7], "cr_days": [40]}


def score(panels, params):
    scores, exposure = _base(panels, params)
    to = float(params.get("cr_to", 0.0))
    if to <= 0:
        return scores, exposure
    k = int(params.get("cr_k", 3))
    thr = float(params.get("cr_thr", 0.12))
    liq = liquid_mask(panels, float(params.get("cr_min", 2e7)), int(params.get("cr_days", 40)))
    px = np.asarray(panels["px"], dtype=float)
    out = np.asarray(exposure, dtype=float).copy()
    for t in range(k, px.shape[0]):
        if out[t] >= 1.0:
            continue
        with np.errstate(invalid="ignore", divide="ignore"):
            r = px[t] / px[t - k] - 1.0
        ok = np.isfinite(r) & liq[t]
        if ok.sum() >= 30 and np.clip(r[ok], -0.9, 3.0).mean() > thr:
            out[t] = max(out[t], to)
    return scores, out
