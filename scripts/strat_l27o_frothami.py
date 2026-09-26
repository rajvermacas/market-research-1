"""Candidate: froth exposure cut x Amihud illiquidity rank tilt (Loop-27 orchestrator).

Setup in words: scores and exposure exactly as strat_l27a_froth (the L27
champion: liqconfirm rank/tiers + illiquid-tail froth exposure cut), imported.
Then the per-name rank is tilted by strat_l27b2_amihud.amihud_signal (mean
monthly Amihud illiquidity over months t-am_lb..t-1, bars dated < months[t]):
score * (1 + am_w * (2*pct - 1)). Exposure is untouched by the tilt.

Hypothesis: the two Loop-27 findings live on different channels — froth sets
HOW MUCH is invested, Amihud sets WHICH names — so they should add.
Falsifier: no am_w > 0 cell beats the froth champion's train 30.21 / -14.09
on CAGR without a DD break.

Novelty: first composition of an exposure cut (l27a_froth, PROMOTED L27) with
the illiquidity rank tilt (l27b2_amihud, screened on the pre-froth L25 base;
l27b2_amispread showed Amihud x CS spread interfere - same rank axis). The base
changed: the L27 champion. Off-switch: am_w = 0 -> strat_l27a_froth exactly.
"""
from __future__ import annotations

from strat_l27a_froth import score as _base
from strat_l27b2_amihud import amihud_signal
from strat_l27b_spread import _pct_tilt

NEEDS_DAILY = True
SPACE = {"am_w": [0.0, 0.1, 0.15, 0.2, 0.25], "am_lb": [12, 15, 18], "am_frac": [0.5]}


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("am_w", 0.0))
    if w == 0.0:
        return scores, exposure
    return _pct_tilt(scores, amihud_signal(panels, params), w), exposure
