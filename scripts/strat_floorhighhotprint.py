"""Candidate: hottest-print rank among confirmed breakouts (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
eligibility and regime from strat_floorhighfastgate (fresh printed high +
above short trend, under breadth tiers), but the RANK is the print month's
own return (px[t]/px[t-1] - 1) — the hottest breakouts first — instead of
lift level.

Rationale: lift level holds the most-extended names; print-month return
holds the fastest-moving ones right now. liftmom (change in lift over 6/12m)
trailed, but that measured slow structural change; the 1-month print return
is the purest acceleration cut and the natural complement — if breakouts
persist month-to-month, heat ranks above extension. If 1-month heat
mean-reverts (the classic reversal finding), this trails hard and the
acceleration question is settled at every horizon.

PIT-safe: print return uses closes through px[m] only (t and t-1 month
ends); NaN months propagate as ineligible, never peek.

SPACE = strat_floorhighfastgate params (heat rank is structural, no knobs).
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfastgate import score as _fg_score

NEEDS_DAILY = False
SPACE = {"note": "strat_floorhighfastgate params; heat rank is structural"}


def score(panels, params):
    elig, exposure = _fg_score(panels, params)
    px = panels["px"]
    out = np.full_like(elig, np.nan)
    for t in range(1, elig.shape[0]):
        with np.errstate(invalid="ignore"):
            heat = px[t] / px[t - 1] - 1
        ok = np.isfinite(elig[t]) & np.isfinite(heat)
        out[t] = np.where(ok, heat, np.nan)
    return out, exposure
