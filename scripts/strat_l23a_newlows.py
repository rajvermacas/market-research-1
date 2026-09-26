"""Candidate: new-LOW share as an exposure cap on top of the breadth tiers (Loop-23 A).

Setup in words: rank, eligibility and tiered exposure come from the base
(strat_floorhighfresh, or strat_l23a_liqconfirm when nl_base == "liqconfirm";
both imported, never copied). Then, at each month-end t, count the share of
live names whose month-end close px[t] is at (or within nl_tol of) its lowest
month-end close over the trailing nl_lb months (closes px[t-nl_lb+1 .. t]).
If that new-low share exceeds nl_max, exposure is capped at nl_cap.

Breadth-above-MA (the base regime) measures participation on the UP side and
reacts slowly; the new-low share measures the DOWNSIDE tail — capitulation
spreading through the board — which can spike while a slow MA breadth still
reads healthy. PIT: uses closes through px[t] only.

Hypothesis: capping exposure in months of widespread new lows trims the
drawdown legs (2016, 2018, 2020) without cutting the invested bull months,
improving DD at little CAGR cost.
Falsifier: every cap variant lowers train CAGR by more than it improves DD
(calmar not above base), or leaves DD unchanged (overlay inert).

Novelty: registry has index-drawdown vetoes (strat_floorhighidxdd,
strat_floorhighabsveto: DEAD, legacy, index-level), breadth-above-MA variants
(tierdual/tieror/hyst/breadthlin: DEAD, legacy) and breadth delta
(strat_l14a_breadthdelta: DEAD). None uses the cross-sectional share of names
at trailing lows (the downside-tail breadth). Realistic-exec base.

Keys: nl_max (share; >= 1 or absent = off-switch -> base exactly), nl_lb (12),
nl_cap (0.4), nl_tol (0.0), nl_base ("fresh" | "liqconfirm"; liqconfirm reads
its own lq_* keys).
SPACE variants: nl_lb 12 with nl_max 0.15/0.20/0.25 x nl_cap 0.4/0.0; nl_lb 6.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _fresh
from strat_l23a_liqconfirm import score as _liqconf

NEEDS_DAILY = True
SPACE = {"nl_max": [1.0, 0.15, 0.2, 0.25], "nl_lb": [6, 12], "nl_cap": [0.0, 0.4],
         "nl_tol": [0.0], "nl_base": ["fresh", "liqconfirm"]}


def newlow_share(px, lb, tol):
    out = np.full(px.shape[0], np.nan)
    for t in range(lb - 1, px.shape[0]):
        w = px[t - lb + 1:t + 1]
        with np.errstate(invalid="ignore"):
            full = np.isfinite(w).all(axis=0)
            lo = np.nanmin(np.where(full, w, np.inf), axis=0)
            at = full & (px[t] <= lo * (1 + tol))
        n = full.sum()
        if n >= 20:
            out[t] = at.sum() / n
    return out


def score(panels, params):
    base = _liqconf if params.get("nl_base", "fresh") == "liqconfirm" else _fresh
    scores, exposure = base(panels, params)
    nl_max = float(params.get("nl_max", 1.0))
    if nl_max >= 1.0:
        return scores, exposure
    s = newlow_share(panels["px"], int(params.get("nl_lb", 12)), float(params.get("nl_tol", 0.0)))
    cap = float(params.get("nl_cap", 0.4))
    out = np.asarray(exposure, dtype=float).copy()
    hit = np.isfinite(s) & (s > nl_max)
    out[hit] = np.minimum(out[hit], cap)
    return scores, out
