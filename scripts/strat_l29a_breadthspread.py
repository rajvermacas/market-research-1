"""Candidate: illiquid-tail vs liquid-core BREADTH spread as an exposure signal on the L25 champion (Loop-29 A).

Setup in words: rank, eligibility, book policy and base exposure are exactly the
L25 champion strat_l23a_liqconfirm (imported, never copied). Two breadths are
measured each month-end with the champion's own regime_ma: the liquid core
(names whose lq_days median traded value, date < months[t], is >= lq_min) and
the illiquid tail (every other alive name); breadth = share above its
regime_ma-month average close. spread[t] = tail_breadth - core_breadth and
d[t] = spread[t] - spread[t - bs_k] (a change in the breadth spread).
bs_mode:
  "cut"   -> if d[t] < -bs_thr (the tail's participation is deteriorating
             faster than the core's: speculative breadth rolling over first)
             exposure *= (1 - bs_cut)
  "rearm" -> if d[t] > +bs_thr and 0 < exposure < 1 (the tail recovering ahead
             of the core) exposure -> 1.0
Decision row t uses closes through px[t] and daily bars date < months[t].

Hypothesis: the tail leads the core at turns in PARTICIPATION even if not in
return; cutting when tail breadth rolls over relative to the core pre-empts
the 2018 small-cap slide that sets the champion's train DD.
Falsifier: no cell beats the champion on train CAGR at no deeper DD, or the
gain rests on <= 3 firing months.

Novelty: closest rows are strat_l27a_sizeflight / strat_l27a_froth (tail minus
core RETURN spread, DEAD / crown revoked) and strat_l22b_liqbreadth /
strat_l23a (liquid breadth LEVEL). The one thing that changed: the signal is the
change in the tail-minus-core BREADTH (participation) spread, not a return
spread and not a breadth level. Base: L25 champion.

Off-switch: bs_k = 0 -> champion exactly.
SPACE: bs_k {1,2,3}, bs_thr {.05,.08,.12}, bs_cut {.5,1.0}, bs_mode {cut,rearm}.
Diagnostic: prints the TRAIN-window (2015-01..2021-12) firing months to stderr
(dates only, never a 2022+ value).
"""

from __future__ import annotations

import sys

import numpy as np

from strat_l23a_liqconfirm import score as _champ
from strat_l22b_liqbreadth import liquid_mask

NEEDS_DAILY = True
SPACE = {"bs_k": [0, 1, 2, 3], "bs_thr": [0.05, 0.08, 0.12], "bs_cut": [0.5, 1.0],
         "bs_mode": ["cut", "rearm"]}


def _breadths(panels, params):
    liq = liquid_mask(panels, float(params["lq_min"]), int(params.get("lq_days", 40)))
    px, months = panels["px"], panels["months"]
    ma = int(params.get("regime_ma", 5))
    ma_px = np.full_like(px, np.nan)
    for t in range(ma - 1, len(months)):
        ma_px[t] = np.nanmean(px[t - ma + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore"):
        alive = np.isfinite(px) & np.isfinite(ma_px)
        above = alive & (px > ma_px)
    out = []
    for grp in (alive & liq, alive & ~liq):
        n = grp.sum(axis=1)
        a = (above & grp).sum(axis=1)
        out.append(np.where(n >= 20, a / np.maximum(n, 1), np.nan))
    return out[0], out[1]


def report_firings(months, base, out, tag):
    fired = [str(months[t])[:7] for t in range(len(out))
             if "2015-01" <= str(months[t])[:7] < "2022-01" and abs(out[t] - base[t]) > 1e-12]
    print(f"{tag} train firings: {len(fired)} {fired}", file=sys.stderr)


def score(panels, params):
    res = _champ(panels, params)
    scores, exposure = res[0], res[1]
    k = int(params.get("bs_k", 0))
    if k <= 0:
        return res
    core, tail = _breadths(panels, params)
    spread = tail - core
    thr = float(params.get("bs_thr", 0.08))
    cut = float(params.get("bs_cut", 0.5))
    mode = params.get("bs_mode", "cut")
    base = np.asarray(exposure, dtype=float)
    out = base.copy()
    for t in range(k, len(out)):
        d = spread[t] - spread[t - k]
        if not np.isfinite(d):
            continue
        if mode == "cut" and d < -thr:
            out[t] = base[t] * (1.0 - cut)
        elif mode == "rearm" and d > thr and 0.0 < base[t] < 1.0:
            out[t] = 1.0
    report_firings(panels["months"], base, out, "L29A-bs")
    return (scores, out) + tuple(res[2:])
