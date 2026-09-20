"""Candidate: volatility-scaled exposure over the conditional-sustain book
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): rank and
breadth tiers from strat_floorhighsustaincond, with the tier exposure
additionally scaled by realized index volatility — the equal-weight index of
names alive at test start (same construction as strat_floorlift's regime),
monthly returns through month t, annualized std over `vt_lb` months:

    E_eff = E_tier * min(1, vt_target / vol_t)

Calm markets keep the full tier exposure; turbulent ones shrink it
proportionally. No leverage (cap 1.0), so this can only ever reduce exposure
and must show up in drawdown first.

Rationale: the tier system cuts exposure when breadth falls, but breadth is a
level, not a risk measure — vol spikes arrive while breadth is still above
thresholds, and the book pays its drawdown in those months. If vol scaling
merely duplicates what the tiers already do it will trail; if it trims the
left tail it buys compounding through the geometric mean.

PIT-safe: vol_t reads the index path through month t only; the harness applies
E[t] to the return t -> t+1.

SPACE = strat_floorhighsustaincond params + vt_lb {6}, vt_target {0.12,0.15,0.20}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighsustaincond import score as _sc_score

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
    "sustain_lo": [6],
    "sustain_hi": [2],
    "vt_lb": [6],
    "vt_target": [0.12, 0.15, 0.20],
}


def score(panels, params):
    rank, exposure = _sc_score(panels, params)
    px, months = panels["px"], panels["months"]
    start_i = panels["start_i"]
    vlb = int(params.get("vt_lb", 6))
    target = float(params.get("vt_target", 0.15))

    alive = ~np.isnan(px[start_i])
    idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
    r = np.zeros(len(idx))
    r[1:] = idx[1:] / idx[:-1] - 1

    E = np.array(exposure, dtype=float, copy=True)
    for t in range(vlb, len(months)):
        w = r[t - vlb + 1:t + 1]
        with np.errstate(invalid="ignore"):
            vol = float(np.nanstd(w, ddof=1)) * np.sqrt(12)
        if np.isfinite(vol) and vol > 0:
            E[t] = E[t] * min(1.0, target / vol)
    return rank, E
