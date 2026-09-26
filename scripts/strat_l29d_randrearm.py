"""Null control: RANDOM re-arm of the L25 champion's partial exposure tiers (Loop-29 D).

Setup in words: rank, eligibility, book policy and base exposure are exactly the
L25 champion strat_l23a_liqconfirm (imported, never copied). Among TRAIN months
only (2015-01 <= month < 2022-01, the same window report_firings counts; forward
months are never touched and the draw never looks at them) whose champion
exposure is a partial tier (0 < regime < 1), pick months uniformly at random
with numpy default_rng(rr_seed) and set exposure there to max(base, rr_to).

rr_mode "months": pick rr_n distinct partial months.
rr_mode "runs":   pick rr_eps distinct maximal runs of consecutive partial-tier
                  months (a run = consecutive months all with 0 < regime < 1)
                  and re-arm every month of each chosen run.

Purpose: exposure-side null for strat_l29a_agerearmup (8 train firings in 3
episodes). If random re-arms at the same count match its train gain, the
breadth-rising guard carries no information.

Off-switch: rr_n = 0 (months) / rr_eps = 0 (runs) -> champion exactly.
"""

from __future__ import annotations

import sys

import numpy as np

from strat_l23a_liqconfirm import score as _champ
from strat_l29a_breadthspread import report_firings

NEEDS_DAILY = True
SPACE = {"rr_mode": ["months", "runs"], "rr_n": [0, 8], "rr_eps": [0, 3],
         "rr_seed": list(range(1, 13)), "rr_to": [1.0]}

# agerearmup's reported train firings at ag_age 1, ag_look 2, ag_rise 0, ag_to 1.0
_AGE_FIRED = ["2015-10", "2015-11", "2015-12", "2016-05", "2016-06",
              "2020-08", "2020-09", "2020-10"]


def score(panels, params):
    res = _champ(panels, params)
    scores, exposure = res[0], res[1]
    mode = params.get("rr_mode", "months")
    n = int(params.get("rr_n", 0)) if mode == "months" else int(params.get("rr_eps", 0))
    if n <= 0:
        return res
    to = float(params.get("rr_to", 1.0))
    seed = int(params.get("rr_seed", 1))
    months = panels["months"]
    base = np.asarray(exposure, dtype=float)
    out = base.copy()
    ym = [str(m)[:7] for m in months]
    part = [t for t in range(len(base))
            if "2015-01" <= ym[t] < "2022-01" and 0.0 < base[t] < 1.0]
    runs = []
    for t in part:
        if runs and runs[-1][-1] == t - 1:
            runs[-1].append(t)
        else:
            runs.append([t])
    print(f"L29D partial train months: {len(part)} in {len(runs)} runs "
          f"{[ym[t] for t in part]}", file=sys.stderr)
    print(f"L29D runs: {[(ym[r[0]], ym[r[-1]], len(r)) for r in runs]}", file=sys.stderr)
    print(f"L29D agerearmup fired (ref): {_AGE_FIRED}; in partial set: "
          f"{sum(m in {ym[t] for t in part} for m in _AGE_FIRED)}/{len(_AGE_FIRED)}",
          file=sys.stderr)
    rng = np.random.default_rng(seed)
    if mode == "months":
        pick = rng.choice(len(part), size=min(n, len(part)), replace=False)
        chosen = [part[i] for i in sorted(pick)]
    else:
        pick = rng.choice(len(runs), size=min(n, len(runs)), replace=False)
        chosen = sorted(t for i in pick for t in runs[i])
    for t in chosen:
        out[t] = max(base[t], to)
    report_firings(months, base, out, f"L29D-{mode}-s{seed}")
    return (scores, out) + tuple(res[2:])
