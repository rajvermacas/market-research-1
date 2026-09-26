"""Null control: RANDOM cut of the L25 champion's partial exposure tiers (Loop-29 F).

Setup in words: base is exactly the L25 champion strat_l23a_liqconfirm
(imported). Among TRAIN months only (2015-01 <= month < 2022-01; forward months
never touched, the draw never looks at them) whose champion exposure is a
partial tier (0 < regime < 1), pick rc_n distinct months uniformly at random with
numpy default_rng(rc_seed) and multiply exposure there by rc_cut.

Purpose: matched-count null for strat_l29f_fallcut. If random cuts of the same
count match its train result, the falling-breadth trigger carries no information.

Off-switch: rc_n = 0 -> champion exactly.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _champ
from strat_l29a_breadthspread import report_firings

NEEDS_DAILY = True
SPACE = {"rc_n": [0, 5], "rc_seed": list(range(1, 9)), "rc_cut": [0.0, 0.5]}


def score(panels, params):
    res = _champ(panels, params)
    scores, exposure = res[0], res[1]
    n = int(params.get("rc_n", 0))
    if n <= 0:
        return res
    cut = float(params.get("rc_cut", 0.0))
    rng = np.random.default_rng(int(params.get("rc_seed", 1)))
    months = panels["months"]
    base = np.asarray(exposure, dtype=float)
    out = base.copy()
    ym = [str(m)[:7] for m in months]
    part = [t for t in range(len(base))
            if "2015-01" <= ym[t] < "2022-01" and 0.0 < base[t] < 1.0]
    pick = rng.choice(len(part), size=min(n, len(part)), replace=False)
    for i in sorted(pick):
        out[part[i]] = base[part[i]] * cut
    report_firings(months, base, out, f"L29F-rc-s{int(params.get('rc_seed', 1))}")
    return (scores, out) + tuple(res[2:])
