"""Candidate: floor-high rank under sponsorship gate (strategy_lab contract).

Triple composition (imported, never copied): rank by strat_floorhigh
(floor-lift distance among names within max_dist of their trailing high),
gated by strat_liqtrend eligibility (expanding volume sponsorship + 6m
price confirmation). Regime is floorlift's float index-vs-MA exposure
(supports weak_exp tiers).

Rationale: short-floor floorhigh variants lead forward (+55-60%) with
train DD (-45% to -54%) as the binding problem; the prior art shows
vol/squeeze/accel/breadth gates all subtract forward, but the sponsorship
gate is untested on this rank and selects a different failure mode (thin
drifts vs real accumulation) rather than a volatility cut.

PIT-safe: rank uses month-end closes through px[m]; liqtrend uses daily
bars with date < months[m] plus closes through px[m] for its price gate.

SPACE = union of strat_floorhigh and strat_liqtrend params.
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_liqtrend import score as _liq_score

NEEDS_DAILY = True
SPACE = {"note": "union of strat_floorhigh and strat_liqtrend params"}


def score(panels, params):
    fh, regime = _fh_score(panels, params)
    gate, _ = _liq_score(panels, params)
    return np.where(np.isfinite(gate), fh, np.nan), regime
