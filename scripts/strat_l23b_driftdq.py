"""Candidate: cross-channel composition — held-gap drift bonus x drawdown-path
tilt (strategy_lab contract; Loop-23 designer B).

Setup in words: rank exactly as strat_floorhighfresh, then apply BOTH
multiplicative tilts from this loop's two single-channel files, each imported
(never copied): the pullback-depth percentile tilt of strat_l23b_ddquality
(1 + dq_w*(2*pct-1), dq_w < 0 favours names whose recent path held a deeper
drawdown before the fresh high — the V-recovery side) and the held high-volume
gap-up bonus of strat_l23b_gapdrift ((1 + gd_w) if a held event occurred in
the gd_lb months before the decision month). Composition = base * m_dq * m_gd,
where each multiplier is recovered as the file's output / base score. Regime
untouched. PIT inherits from both parents (daily bars date < months[t]).

Hypothesis: the two channels are different axes — an information event (gap x
volume shock that held) vs the depth of the road into the high — so the
composition should be at least additive (Loop-20 lesson: compose across
channels, not within one).
Falsifier: composition no better than the better parent on the robust ruler,
or wider DD than both.

NOVELTY: composition of two Loop-23 files; closest registry rows are the
parents' (strat_l22a_gappen, strat_l17d_reldd, see their docstrings).

Keys consumed: all of strat_l23b_gapdrift (gd_*) and strat_l23b_ddquality
(dq_*). Off-switch: gd_w 0.0 and dq_w 0.0 (both defaults) = champion exactly.
SPACE:
    gd_w 0, dq_w 0                                      off-switch
    gd_w 0.15 gd_lb 2 gd_gap 0.03 gd_vm 2 + dq_w -0.15 dq_lb 4
    gd_w 0.15 gd_lb 3 gd_gap 0.03 gd_vm 2 + dq_w -0.15 dq_lb 6
    gd_w 0.1  gd_lb 2 gd_gap 0.03 gd_vm 2 + dq_w -0.1  dq_lb 4
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _base
from strat_l23b_ddquality import score as _dq
from strat_l23b_gapdrift import score as _gd

NEEDS_DAILY = True
SPACE = {"gd_w": [0.0, 0.1, 0.15], "dq_w": [0.0, -0.1, -0.15], "gd_lb": [2, 3], "dq_lb": [4, 6]}


def score(panels, params):
    s0, regime = _base(panels, params)
    gw = float(params.get("gd_w", 0.0))
    dw = float(params.get("dq_w", 0.0))
    if gw == 0.0 and dw == 0.0:
        return s0, regime
    s1, _ = _dq(panels, params)
    s2, _ = _gd(panels, params)
    with np.errstate(all="ignore"):
        m_dq = np.where(np.isfinite(s0) & (s0 != 0), s1 / s0, 1.0)
        m_gd = np.where(np.isfinite(s0) & (s0 != 0), s2 / s0, 1.0)
    return s0 * m_dq * m_gd, regime
