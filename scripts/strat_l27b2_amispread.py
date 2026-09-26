"""Candidate: Amihud illiquidity x Corwin-Schultz spread composition on the L23-A champion (Loop-27 B2).

Setup in words: scores and exposure from strat_l27b_spread.score (imported: the
L23-A champion with the Corwin-Schultz spread-level percentile tilt sp_w/sp_lb,
round-1 best sp_w +0.2 / sp_lb 9), then multiplied by the Amihud illiquidity
percentile tilt of strat_l27b2_amihud (imported amihud_signal; strat_l27b_spread
._pct_tilt: score *= 1 + am_w*(2*pct-1)). Point-in-time as the parents: every
bucket in either window is built from daily bars dated < months[t].
sp_w=0 and am_w=0 is the exact off-switch (champion arrays untouched); either
weight at 0 reproduces the other parent exactly. Regime/exposure untouched.

Question: additivity. If the CS spread and Amihud tilts are the SAME
illiquidity premium measured twice, the product will not beat the better parent
(interference, as legacy strat_l20b2_liqcombo found); if CS carries something
Amihud lacks (range/volatility), they stack.
Falsifier: no cell beats the better parent on train CAGR without wider DD.

Novelty: closest row strat_l20b2_liqcombo (DEAD, illiq x spread, legacy L19
chain and legacy exec, and with the spread tilt signed TIGHT). One thing
changed: the base (realistic L23-A champion), on which both parents now carry
the SAME (illiquid/wide) sign.
SPACE: (sp_w, sp_lb) = (0.2, 9) x (am_w in {0.1, 0.2}, am_lb in {12, 15}); also
half doses (0.1, 9) x (0.1, 15).
"""
from __future__ import annotations
from strat_l27b_spread import score as _spread_score, _pct_tilt
from strat_l27b2_amihud import amihud_signal

NEEDS_DAILY = True
SPACE = {"sp_w": [0.1, 0.2], "sp_lb": [9], "am_w": [0.1, 0.2], "am_lb": [12, 15]}


def score(panels, params):
    p = dict(params)
    p.setdefault("sp_w", 0.0)
    p.setdefault("sp_lb", 9)
    p.setdefault("sp_frac", 0.5)
    scores, exposure = _spread_score(panels, p)
    w = float(p.get("am_w", 0.0))
    if w == 0.0:
        return scores, exposure
    return _pct_tilt(scores, amihud_signal(panels, p), w), exposure
