"""Candidate: cut a PARTIAL tier when the liquid breadth FELL over fc_look months (Loop-29 F).

Setup in words: rank, eligibility, book policy and base exposure are exactly the
L25 champion strat_l23a_liqconfirm (imported, never copied). b[t] is the
champion's own liquid-cohort breadth (strat_l23a_liqconfirm.liquid_breadth,
imported). If 0 < exposure[t] < 1 (a partial tier) and b[t - fc_look] - b[t] >
fc_drop, exposure -> exposure[t] * fc_cut. Full-tier and cash months are never
touched. Reads only closes through px[t] and daily bars date < months[t].

Why: mirror of strat_l29a_agerearmup. The random-rearm null (l29d) showed the
breadth-direction guard's value is a VETO on falling-breadth partial runs
(train 2018-03..05). This tests the DD side alone: de-risk those months.

Novelty: neighbours coreslump / newlows / l29a_regimeage fullcap / liqramp cut
exposure on other signals or tiers. The one thing that changed: the trigger is
the champion's own liquid breadth DIRECTION over fc_look months, applied only
inside partial tiers, no re-arm side.

Off-switch: fc_cut = 1 -> champion exactly.
SPACE: fc_look {1,2,3}, fc_cut {0,.5}, fc_drop {0,.02}.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _champ, liquid_breadth
from strat_l29a_breadthspread import report_firings

NEEDS_DAILY = True
SPACE = {"fc_look": [1, 2, 3], "fc_cut": [1.0, 0.0, 0.5], "fc_drop": [0.0, 0.02]}


def score(panels, params):
    res = _champ(panels, params)
    scores, exposure = res[0], res[1]
    cut = float(params.get("fc_cut", 1.0))
    if cut == 1.0:
        return res
    look = int(params.get("fc_look", 2))
    drop = float(params.get("fc_drop", 0.0))
    b = liquid_breadth(panels, params)
    base = np.asarray(exposure, dtype=float)
    out = base.copy()
    for t in range(look, len(base)):
        if 0.0 < base[t] < 1.0 and np.isfinite(b[t]) and np.isfinite(b[t - look]):
            if b[t - look] - b[t] > drop:
                out[t] = base[t] * cut
    report_firings(panels["months"], base, out, "L29F-fc")
    return (scores, out) + tuple(res[2:])
