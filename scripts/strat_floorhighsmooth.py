"""Candidate: smoothness-weighted structural rank among fresh breakouts
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
eligibility and regime from strat_floorhighfresh (names printing a trailing
high under breadth tiers), but the RANK divides lift level by each name's
own trailing roughness — rank = lift / (1 + max_drawdown over the floor
window), where max_drawdown is the worst peak-to-trough on month closes
through month t.

Rationale: lift level cannot tell a smooth compounder from one that fell
50% and rebounded — both print the same distance above the floor, but the
round-trip reveals weak sponsorship and predicts the next shakeout. The DD
penalty prefers structure earned smoothly. If shakeouts don't predict,
this trails the level rank and smoothness is noise.

PIT-safe: roughness uses month closes through px[m] only (trailing window
ending at t); NaN windows propagate as ineligible, never peek. The DD
computation is primitive price plumbing, not a candidate signal.

SPACE = strat_floorhightier params (roughness window = floor_lb).
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _fresh_score

NEEDS_DAILY = False
SPACE = {"note": "strat_floorhightier params; roughness window = floor_lb"}


def score(panels, params):
    rank, exposure = _fresh_score(panels, params)
    px = panels["px"]
    flb = int(params.get("floor_lb", 19))
    out = np.full_like(rank, np.nan)
    for t in range(flb - 1, rank.shape[0]):
        w = px[t - flb + 1:t + 1]
        with np.errstate(invalid="ignore"):
            peak = np.maximum.accumulate(np.where(np.isfinite(w), w, np.nan), axis=0)
            dd = 1.0 - w / peak
            rough = np.nanmax(dd, axis=0)
        ok = np.isfinite(rank[t]) & np.isfinite(rough)
        out[t] = np.where(ok, rank[t] / (1.0 + rough), np.nan)
    return out, exposure
