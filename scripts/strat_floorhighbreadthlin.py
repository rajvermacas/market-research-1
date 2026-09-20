"""Candidate: linear breadth-ramp exposure over the tier-shape book
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): rank and book
size from strat_floorhightiershape, but the exposure leg is a continuous ramp
of market breadth between two searchable bounds instead of the discrete
0/lo/mid/full ladder:

    E = clip((breadth - b_lo_lin) / (b_hi_lin - b_lo_lin), 0, 1)

Breadth is the fraction of live names closing above their own `regime_ma`-month
average (the same construction strat_newhigh_tier uses). Rationale: the current
best collapsed its ladder to a switch — fully invested whenever breadth clears
b_lo, cash below — which is maximal whipsaw at the threshold. Sizing the book
with participation de-risks gradually instead. If the switch was already the
right shape, the ramp trails; if partial exposure between the bounds is worth
holding, it beats the switch at similar DD.

PIT-safe: breadth for holding month t uses month-end closes through px[t] only.

SPACE = strat_floorhightiershape params + b_lo_lin {0.40,0.45,0.50},
        b_hi_lin {0.60,0.65,0.70,0.75}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhightiershape import score as _ts_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "floor_lb": [19],
    "lookback": [10],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [5],
    "sustain_lo": [3],
    "sustain_hi": [2],
    "tier_lo": [1.0],
    "tier_mid": [1.0],
    "b_lo_lin": [0.40, 0.45, 0.50],
    "b_hi_lin": [0.60, 0.65, 0.70, 0.75],
}


def _breadth(px, months, ma):
    ma_px = np.full_like(px, np.nan)
    for t in range(ma - 1, len(months)):
        ma_px[t] = np.nanmean(px[t - ma + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore"):
        above = (px > ma_px) & np.isfinite(px) & np.isfinite(ma_px)
        alive = np.isfinite(px)
    return np.where(alive.sum(axis=1) > 0,
                    above.sum(axis=1) / np.maximum(alive.sum(axis=1), 1),
                    np.nan)


def score(panels, params):
    rank, _ = _ts_score(panels, params)
    px, months = panels["px"], panels["months"]
    ma = int(params.get("regime_ma", 18))
    lo = float(params.get("b_lo_lin", 0.45))
    hi = float(params.get("b_hi_lin", 0.70))

    b = _breadth(px, months, ma)
    with np.errstate(invalid="ignore", divide="ignore"):
        E = np.clip((b - lo) / (hi - lo), 0.0, 1.0)
    E = np.where(np.isfinite(b), E, 0.0)
    return rank, E
