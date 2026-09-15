"""Candidate: floor-high rank under coil gate (strategy_lab contract).

Triple composition (imported, never copied): rank by strat_floorhigh
(floor-lift distance among names within max_dist of their trailing high),
gated by strat_volsqueeze eligibility (6m uptrend + real dispersion).
Regime is floorlift's float index-vs-MA exposure (supports weak_exp tiers).

Rationale: floorhigh/24/15/weak0.4 leads forward (+29.3%) but DD -28.8%
still trails the bench; the coil gate may trim blowoff entries that drive
that DD while keeping the structural-breakout rank.

PIT-safe: all legs use month-end closes through px[m] only for holding
month starting months[m].

SPACE = union of strat_floorhigh and strat_volsqueeze params.
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_volsqueeze import score as _sq_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_floorhigh and strat_volsqueeze params"}


def score(panels, params):
    fh, regime = _fh_score(panels, params)
    gate, _ = _sq_score(panels, params)
    return np.where(np.isfinite(gate), fh, np.nan), regime
