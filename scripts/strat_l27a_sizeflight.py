"""Candidate: size-flight (illiquid vs liquid cohort relative trend) exposure cut (Loop-27 A).

Setup in words: rank, eligibility and breadth-tier exposure are exactly
strat_l23a_liqconfirm (imported, never copied). On top, a risk-appetite gauge
from the RELATIVE RETURN of the board's illiquid tail against its liquid core:
  * liquid cohort at month t = names whose median daily traded value over the
    last sf_days sessions (date < months[t]) is >= sf_min INR
    (strat_l22b_liqbreadth.liquid_mask, imported); illiquid = every other
    name with a price;
  * each name's trailing sf_k-month return px[t]/px[t-sf_k]-1 (closes through
    px[t]; clipped to [-0.9, 3]);
  * rel_t = mean(illiquid returns) - mean(liquid returns);
  * if rel_t < -sf_thr (the small/illiquid tail is lagging the liquid core:
    flight to quality), exposure *= (1 - sf_cut). sf_mode "full" only cuts
    months where the champion is fully invested (exposure == 1, the months
    where DD legs start: Jan-Feb 2018, Oct 2024); "all" cuts any month.

Hypothesis: the champion's DD legs start in fully-invested months while
breadth is still high; the first symptom of a small-cap unwind is the illiquid
tail underperforming the liquid core, which the level-based breadth tier does
not see until prices cross their 18-month averages.
Falsifier: no cell improves train DD >= 1pp without costing more CAGR.

Novelty: registry has liquid-cohort BREADTH (l22b liqbreadth PARTIAL, l23a
liqconfirm = champion, liqrank, liqramp) and cross-universe breadth
confirmation (l26a xuniconfirm DEAD) — all read the share of names above an
average. Market-relative strength (l14b relstrength) is a per-stock rank
tilt. No row uses the RETURN SPREAD between the illiquid tail and the liquid
core as a market-level exposure signal.

Off-switch: sf_cut = 0 -> champion exactly.
SPACE: sf_k {1,2,3}, sf_thr {0.0,0.02,0.05}, sf_cut {0,0.5,1.0}, sf_mode {full,all},
sf_min 2e7, sf_days 40.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _base
from strat_l22b_liqbreadth import liquid_mask

NEEDS_DAILY = True
SPACE = {"sf_k": [1, 2, 3], "sf_thr": [0.0, 0.02, 0.05], "sf_cut": [0.0, 0.5, 1.0],
         "sf_mode": ["full", "all"], "sf_min": [2e7], "sf_days": [40]}


def size_spread(panels, params):
    k = int(params.get("sf_k", 2))
    liq = liquid_mask(panels, float(params.get("sf_min", 2e7)), int(params.get("sf_days", 40)))
    px = np.asarray(panels["px"], dtype=float)
    out = np.full(px.shape[0], np.nan)
    for t in range(k, px.shape[0]):
        with np.errstate(invalid="ignore", divide="ignore"):
            r = px[t] / px[t - k] - 1.0
        ok = np.isfinite(r)
        r = np.clip(r, -0.9, 3.0)
        a, b = ok & liq[t], ok & ~liq[t]
        if a.sum() >= 30 and b.sum() >= 30:
            out[t] = r[b].mean() - r[a].mean()
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    cut = float(params.get("sf_cut", 0.0))
    if cut <= 0:
        return scores, exposure
    thr = float(params.get("sf_thr", 0.02))
    mode = params.get("sf_mode", "full")
    rel = size_spread(panels, params)
    base = np.asarray(exposure, dtype=float)
    out = base.copy()
    for t in range(len(out)):
        if np.isfinite(rel[t]) and rel[t] < -thr and (mode == "all" or base[t] >= 1.0):
            out[t] = base[t] * (1.0 - cut)
    return scores, out
