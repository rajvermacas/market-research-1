"""Candidate: liquid-core slump exposure cut (Loop-27 orchestrator, pre-registered).

Setup in words: rank, eligibility and breadth-tier exposure exactly as
strat_l23a_liqconfirm (imported). The liquid core is the l22b liquid_mask
cohort (median daily traded value >= cs_min over the last cs_days sessions,
dates < months[t]). core_t = mean clipped cs_k-month return of the liquid core
from month-end closes through px[t]. If core_t < -cs_thr, exposure *= (1 - cs_cut).

Hypothesis (sign fixed before any trial, no diagnostic run): the champion's
breadth tiers read the SHARE of names above an 18-month mean, which lags a
fast fall in the liquid core; a return-magnitude slump of the core flags the
first leg of a drawdown earlier. Falsifier: no cell improves train DD over
-17.22 without losing more than 1pp of CAGR.

Novelty: liqconfirm / liqbreadth / liqramp (breadth share of the liquid
cohort), sizeflight (illiquid-minus-liquid SPREAD, DEAD), dispersion (IQR,
DEAD) - none gates on the liquid core's own return level. Off-switch cs_cut = 0.
"""
from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _base
from strat_l22b_liqbreadth import liquid_mask

NEEDS_DAILY = True
SPACE = {"cs_k": [1, 2, 3], "cs_thr": [0.05, 0.08, 0.12], "cs_cut": [0.0, 0.5, 1.0],
         "cs_min": [2e7], "cs_days": [40]}


def score(panels, params):
    scores, exposure = _base(panels, params)
    cut = float(params.get("cs_cut", 0.0))
    if cut <= 0:
        return scores, exposure
    k = int(params.get("cs_k", 2))
    thr = float(params.get("cs_thr", 0.08))
    liq = liquid_mask(panels, float(params.get("cs_min", 2e7)), int(params.get("cs_days", 40)))
    px = np.asarray(panels["px"], dtype=float)
    out = np.asarray(exposure, dtype=float).copy()
    for t in range(k, px.shape[0]):
        with np.errstate(invalid="ignore", divide="ignore"):
            r = px[t] / px[t - k] - 1.0
        ok = np.isfinite(r) & liq[t]
        if ok.sum() >= 30 and np.clip(r[ok], -0.9, 3.0).mean() < -thr:
            out[t] = out[t] * (1.0 - cut)
    return scores, out
