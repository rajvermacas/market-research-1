"""Candidate: spread-level x idiosyncratic-momentum composition on the L23-A champion (Loop-27 B).

Setup in words: scores and exposure from strat_l27b_spread.score (imported:
the L23-A champion with the Corwin-Schultz spread percentile tilt sp_w/sp_lb),
then multiplied by the idiosyncratic-momentum percentile tilt of
strat_l27b_idiomom (imported idio_signal / _pct_tilt: intercept of each name's
last im_lb monthly returns on the equal-weight panel return, scaled by
residual vol; score *= 1 + im_w*(2*pct-1)). Point-in-time as the parents
(spread buckets < months[t]; returns through px[t]). sp_w=0 and im_w=0 is the
exact off-switch (champion arrays untouched); either weight at 0 reproduces
the other parent exactly. Regime/exposure untouched.

Hypothesis: the two parents act on different axes (execution-cost/illiquidity
premium vs beta-adjusted trend drift) so their train gains should add.
Falsifier: the composition does not beat the better parent (35.19/-15.84).

Novelty: first composition of these two Loop-27 channels; closest prior
compositions are strat_l20b2_liqcombo (illiq x spread, interference) and
strat_l20a3_divspread (dividend x spread) on the legacy L19 chain.
"""
from __future__ import annotations
import numpy as np
from strat_l27b_spread import score as _spread_score
from strat_l27b_idiomom import idio_signal, _pct_tilt

NEEDS_DAILY = True
SPACE = {"sp_w": [0.2], "sp_lb": [9], "im_w": [-0.1, -0.15], "im_lb": [12]}


def score(panels, params):
    p = dict(params)
    p.setdefault("sp_w", 0.0)
    p.setdefault("sp_lb", 9)
    p.setdefault("sp_frac", 0.5)
    scores, exposure = _spread_score(panels, p)
    w = float(p.get("im_w", 0.0))
    if w == 0.0:
        return scores, exposure
    sig = idio_signal(np.asarray(panels["px"], dtype=float), int(p.get("im_lb", 12)))
    return _pct_tilt(scores, sig, w), exposure
