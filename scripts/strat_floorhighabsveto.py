"""Candidate: fresh-print rank under tiers + absolute index-momentum veto
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank and
breadth-tier exposure from strat_floorhighfresh, with an absolute-momentum
veto — in any month where the equal-weight index's trailing 12-month return
is negative, exposure is capped at `veto_e` regardless of what breadth
participation says.

Rationale: breadth is a participation ratio — it can read mid-tier while
the whole market grinds down (everyone below their MA but breadth hovering
near a line). The MA gate compares level to average; the absolute veto asks
the simpler question: has the market made money in the last year? If not,
risk is capped even when participation looks middling. If breadth already
captures this, the veto never binds and the trial ties.

PIT-safe: the 12m index return uses closes through px[m] only; the veto is
pointwise per month, no forward information.

SPACE = strat_floorhighfresh params + veto_e {0.0, 0.4}, veto_lb {12}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _fresh_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "veto_e": [0.0, 0.4],
    "veto_lb": [12],
}


def score(panels, params):
    rank, exposure = _fresh_score(panels, params)
    px, months = panels["px"], panels["months"]
    start_i = panels["start_i"]
    veto_e = float(params.get("veto_e", 0.0))
    vlb = int(params.get("veto_lb", 12))
    exposure = np.asarray(exposure, dtype=float)
    alive = ~np.isnan(px[start_i])
    with np.errstate(invalid="ignore"):
        idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
    mom = np.full(len(months), np.nan)
    mom[vlb:] = idx[vlb:] / idx[:-vlb] - 1
    out = np.array(exposure, copy=True)
    for t in range(len(months)):
        if np.isfinite(mom[t]) and mom[t] < 0:
            out[t] = min(out[t], veto_e)
    return rank, out
