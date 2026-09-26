"""Candidate: regime-age re-arm of a PARTIAL tier, guarded by the liquid breadth RISING over the tier's age (Loop-29 A).

Setup in words: rank, eligibility, book policy and base exposure are exactly the
L25 champion strat_l23a_liqconfirm (imported, never copied). age[t] = consecutive
month-ends (ending at t) on which the champion's exposure equals exposure[t]. If
0 < exposure[t] < 1 (a partial tier), age[t] >= ag_age, AND the champion's own
liquid-cohort breadth b[t] (strat_l23a_liqconfirm.liquid_breadth, imported) is
above b[t - ag_look] by more than ag_rise, exposure -> ag_to. Everything reads
closes through px[t] and daily bars date < months[t].

Why the guard (justified on train only, stated before screening): strat_l29a_
regimeage partrearm (same loop) and the L28 re-arm family re-arm every aged
partial tier; loop_state records that the gated member (upvolnz) paid its gain
back as forward drawdown, and requires any re-arm retest to carry a DD guard
justified on train data alone. A partial tier whose liquid breadth is still
FALLING is a slide in progress (train: 2018-03..05 partial tiers preceded the
2018 small-cap collapse); only a partial tier whose breadth is rising is a base.
The guard therefore refuses re-arm while breadth is deteriorating.

Novelty: closest rows strat_l28o_upvolnz / l27o_corerearm / l28a_thrust (re-arm
partial tiers on up-value share, core rebound, A/D thrust) and this loop's
strat_l29a_regimeage partrearm (re-arm on tier age alone). The one thing that
changed: the re-arm needs tier AGE plus the liquid breadth's own direction over
that age - no new external trigger, and a train-justified deterioration veto.
Base: L25 champion.

Off-switch: ag_age = 0 -> champion exactly.
SPACE: ag_age {1,2,3}, ag_look {1,2,3}, ag_rise {0,.02,.05}, ag_to {1.0, .85}.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _champ, liquid_breadth
from strat_l29a_breadthspread import report_firings

NEEDS_DAILY = True
SPACE = {"ag_age": [0, 1, 2, 3], "ag_look": [1, 2, 3], "ag_rise": [0.0, 0.02, 0.05],
         "ag_to": [1.0, 0.85]}


def score(panels, params):
    res = _champ(panels, params)
    scores, exposure = res[0], res[1]
    A = int(params.get("ag_age", 0))
    if A <= 0:
        return res
    look = int(params.get("ag_look", 2))
    rise = float(params.get("ag_rise", 0.0))
    to = float(params.get("ag_to", 1.0))
    b = liquid_breadth(panels, params)
    base = np.asarray(exposure, dtype=float)
    out = base.copy()
    age = 0
    for t in range(len(base)):
        age = age + 1 if t > 0 and abs(base[t] - base[t - 1]) < 1e-12 else 1
        if 0.0 < base[t] < 1.0 and age >= A and t >= look:
            if np.isfinite(b[t]) and np.isfinite(b[t - look]) and b[t] - b[t - look] > rise:
                out[t] = max(base[t], to)
    report_firings(panels["months"], base, out, "L29A-ag")
    return (scores, out) + tuple(res[2:])
