"""Candidate: the Loop-25 champion's liquid-cohort regime x the held gap-up rank bonus.

Setup in words: the champion `strat_l23a_liqconfirm` (fresh-print rank on the
floorhighfresh base; exposure from liquid-cohort breadth with shifted tier
thresholds; policy top 25 inverse-vol passed as params) with its SCORES
replaced by `strat_l23b_gapdrift`'s (the same base scores times (1 + gd_w)
for names whose high-volume gap-up in the prior gd_lb months held its gain).
Scores come from gapdrift, regime from liqconfirm — both imported verbatim.

Hypothesis: gapdrift (PARTIAL in L23, ~1 noise sd over its placebo on the old
champion) is a post-event drift channel, not the V-recovery axis that lost
forward in every L23/L24 gate; on the new champion's regime it may add CAGR.
Falsifier: no cell beats the champion's robust score (2.121) by its noise
margin.
PIT: inherited (closes through px[t], daily bars dated before months[t]).
Off-switch: gd_w 0 -> gapdrift returns the base scores -> the champion exactly.
Keys: champion keys (incl. lq_*, top, weighting) + gd_w, gd_lb, gd_gap, gd_vm.
Novelty: first composition of the event channel with the liquid-cohort regime
(closest rows: strat_l23b_gapdrift PARTIAL, strat_l23a_liqconfirm PROMOTED L25).
"""

from __future__ import annotations

from strat_l23a_liqconfirm import score as _regime
from strat_l23b_gapdrift import score as _rank

NEEDS_DAILY = True


def score(panels, params):
    p = dict(params)
    p.setdefault("gd_w", 0.0)
    scores, _ = _rank(panels, p)
    _, regime = _regime(panels, p)
    return scores, regime
