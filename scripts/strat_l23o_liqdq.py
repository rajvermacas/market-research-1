"""Candidate: cross-channel composition — liquid-cohort regime x drawdown-path rank tilt.

Setup in words: the champion `strat_floorhighfresh` (fresh-print rank, breadth
tiers) with its two Loop-23 channels composed, each imported verbatim:
  - EXPOSURE from `strat_l23a_liqconfirm` (breadth over liquid names with the
    tier thresholds shifted up, lq_* keys) — acts only on the regime;
  - RANK from `strat_l23b_ddquality` (percentile tilt on the deepest
    peak-to-trough drawdown over dq_lb prior months, dq_* keys) — acts only on
    the scores.
Both delegates start from the same base scores, so this file returns
ddquality's scores with liqconfirm's regime.

Hypothesis: the two channels are different axes (when to be invested vs which
names to hold), so per the Loop-20 lesson they may add where same-axis tilts
interfere. At the Loop-23 gate, liqconfirm kept the champion's forward CAGR
at a better forward DD but changed too few months, and ddquality lifted train
but lost forward CAGR.
Falsifier: the composition's robust score does not beat the better parent
(liqconfirm 1.961) by more than its noise margin, or it fails the gate.

PIT: inherited — both delegates read closes through px[t] and daily bars dated
before months[t].
Off-switch: dq_w 0.0 and lq_min 0 → both delegates return the base → the
champion exactly.
Keys: every champion key plus the lq_* keys (liqconfirm) and dq_* keys (ddquality).
Novelty: first composition of the regime channel with a rank tilt on the
realistic base; closest rows are its two parents (tested_mechanisms.tsv, l23).
SPACE: the two parents' gated cells, plus one step on dq_lb (2, 4).
"""

from __future__ import annotations

from strat_l23a_liqconfirm import score as _regime
from strat_l23b_ddquality import score as _rank

NEEDS_DAILY = True


def score(panels, params):
    p = dict(params)
    p.setdefault("dq_w", 0.0)
    p.setdefault("lq_min", 0)
    scores, _ = _rank(panels, p)
    _, regime = _regime(panels, p)
    return scores, regime
