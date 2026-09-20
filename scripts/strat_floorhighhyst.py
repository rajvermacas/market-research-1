"""Candidate: hysteresis (Schmitt-trigger) breadth exposure over the current
best's book (strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): rank, gates
and book size from strat_floorhightiershape, with the exposure replaced by a
two-threshold switch on market breadth:

    enter full risk when breadth > b_enter
    exit to cash when breadth < b_exit
    otherwise stay in the previous state

Rationale: the current best is fully invested whenever breadth clears b_lo
and in cash below, so breadth oscillating around that one line flips the book
in and out. A Schmitt trigger separates the entry and exit levels, paying a
slower exit for fewer round trips — the classic fix for a whipsawing switch.
If the best's single threshold was already positioned right, hysteresis
trials; if the whipsaw was costing round trips, it keeps the return with a
lower drawdown.

PIT-safe: the state machine reads breadth through month t only and carries
the prior state; no forward information.

SPACE = strat_floorhightiershape params + b_enter {0.50,0.55,0.60},
        b_exit {0.35,0.40,0.45}.
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
    "b_enter": [0.50, 0.55, 0.60],
    "b_exit": [0.35, 0.40, 0.45],
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
    enter = float(params.get("b_enter", 0.55))
    exit_ = float(params.get("b_exit", 0.40))

    b = _breadth(px, months, ma)
    E = np.zeros(len(months))
    state = 0.0
    for t in range(len(months)):
        if np.isfinite(b[t]):
            if b[t] > enter:
                state = 1.0
            elif b[t] < exit_:
                state = 0.0
        E[t] = state
    return rank, E
