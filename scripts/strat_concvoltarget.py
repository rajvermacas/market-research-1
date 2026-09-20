"""Candidate: volatility-targeted exposure over the concentrated-shape book
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank,
concentration and shaped exposure from strat_floorhightiershapeconc, with the
exposure additionally scaled by realized index volatility:

    E_eff = E * min(1, vt_target / vol_t)

where vol_t is the annualized std of the equal-weight index's monthly returns
over `vt_lb` months ending at t. This is the same overlay that subtracted on
the older base (strat_floorhighvoltarget: 35-43% train vs 49% base); the
retest is legitimate because the base mechanism's exposure and book
composition have both changed since — with 61-62% average invested and the
concentration lever in place, the left tail the overlay trims is a different
(and larger) object. If it still subtracts, vol targeting is closed for this
family.

PIT-safe: vol_t reads the index through month t only.

SPACE = strat_floorhightiershapeconc params + vt_lb {6}, vt_target {0.15,0.20}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhightiershapeconc import score as _base_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [9],
    "sustain_lo": [4],
    "sustain_hi": [2],
    "tier_lo": [0.55],
    "tier_mid": [1.0],
    "cap_weak": [12],
    "cap_full": [20],
    "vt_lb": [6],
    "vt_target": [0.15, 0.20],
}


def score(panels, params):
    rank, exposure = _base_score(panels, params)
    px, months, start_i = panels["px"], panels["months"], panels["start_i"]
    vlb = int(params.get("vt_lb", 6))
    target = float(params.get("vt_target", 0.15))

    alive = ~np.isnan(px[start_i])
    idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
    r = np.zeros(len(idx))
    r[1:] = idx[1:] / idx[:-1] - 1

    E = np.asarray(exposure, dtype=float).copy()
    for t in range(vlb, len(months)):
        w = r[t - vlb + 1:t + 1]
        with np.errstate(invalid="ignore"):
            vol = float(np.nanstd(w, ddof=1)) * np.sqrt(12)
        if np.isfinite(vol) and vol > 0:
            E[t] = E[t] * min(1.0, target / vol)
    return rank, np.clip(E, 0.0, 1.0)
