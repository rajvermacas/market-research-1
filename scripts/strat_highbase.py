"""Candidate: base-duration rank among floor-seasoned names (strategy_lab contract).

Fresh rank statistic — duration, not depth or freshness (imported, never
copied): among names where strat_floorlift's score is finite (full floor
window + 12m positive trend + above the floor) AND within max_dist of
their trailing `lookback`-month high per strat_newhigh eligibility, rank
by the COUNT of months (over the trailing `lookback` window) spent within
max_dist of the trailing high. Thesis: depth (floorhigh) crowns the most
extended name near its high; freshness (breakrec) crowns yesterday's
touch; duration crowns the longest-formed base pressing on resistance —
the classic accumulation-before-markup shape neither leg measures. Score
higher = longer base = better.

PIT-safe: trailing counts use closes through px[m] only for holding month
starting months[m]; needs lb bars history.

SPACE = floor_lb {18}, lookback {15}, max_dist {0.03}, regime_ma {10},
weak_exp {0.4} (the short-floor line's params; rank statistic is the variable).
"""

from __future__ import annotations

import numpy as np

from strat_floorlift import score as _floor_score

NEEDS_DAILY = False
SPACE = {
    "floor_lb": [18],
    "lookback": [15],
    "max_dist": [0.03],
    "regime_ma": [10],
    "weak_exp": [0.4],
}


def score(panels, params):
    from strat_floorlift import _regime as _fl_regime

    px, months = panels["px"], panels["months"]
    start_i = panels["start_i"]
    lb = int(params.get("lookback", 15))
    md = float(params.get("max_dist", 0.03))
    ma = int(params.get("regime_ma", 10))
    weak_exp = float(params.get("weak_exp", 0.4))

    lift, _ = _floor_score(panels, params)
    hi = np.full_like(px, np.nan)
    for t in range(lb - 1, len(months)):
        hi[t] = np.nanmax(px[t - lb + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        prox = px / hi - 1
    near = np.isfinite(prox) & (prox >= -md)
    # trailing count of near-high months over the lb window
    cnt = np.full_like(px, np.nan)
    for t in range(lb - 1, len(months)):
        w = near[t - lb + 1:t + 1]
        cnt[t] = w.sum(axis=0)
    out = np.where(np.isfinite(lift) & near, cnt, np.nan)
    return out, _fl_regime(px, months, start_i, ma, weak_exp)
