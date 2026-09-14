"""Candidate: new-high base with pullback tilt (strategy_lab contract).

Composition of the two best-behaved ideas so far: strat_newhigh (most
balanced halves +24.8/+24.1, fwd 14.57 just shy of bench) supplies the
ranking — proximity to the trailing high — and strat_rsi_pullback supplies
a bounded timing bonus, tilt-not-filter per the T1 lesson (hard gates
starve the book; T1's tilt held 68% invested). Reuses both candidates
verbatim, no second copy of either signal.

Score per month: rank01(prox) + bonus * rec01(gate); NaN where prox is NaN
(i.e. names > max_dist from their high stay excluded — the absolute gate).
Regime: newhigh's index-vs-MA gate.

SPACE = union of strat_newhigh.SPACE and strat_rsi_pullback.SPACE + bonus.
"""

from __future__ import annotations

import numpy as np

from strat_newhigh import score as _nh_score
from strat_rsi_pullback import score as _pb_score

NEEDS_DAILY = True
SPACE = {"note": "union of strat_newhigh.SPACE and strat_rsi_pullback.SPACE plus bonus [0..1]"}


def score(panels, params):
    bonus = float(params.get("bonus", 0.3))
    prox, regime = _nh_score(panels, params)
    gate, _ = _pb_score(panels, params)
    out = np.full_like(prox, np.nan)
    for t in range(prox.shape[0]):
        m = prox[t]
        ok = np.isfinite(m)
        n = int(ok.sum())
        if n == 0:
            continue
        order = np.argsort(np.where(ok, m, -np.inf))
        ranks = np.empty_like(m)
        ranks[:] = np.nan
        ranks[order] = np.arange(m.shape[0], dtype=float)
        r01 = np.full_like(m, np.nan)
        r01[ok] = ranks[ok] / max(n - 1, 1)
        g = gate[t]
        gok = ok & np.isfinite(g)
        rec01 = np.zeros_like(m)
        if gok.sum() >= 2:
            gv = g[gok]
            lo, hi = gv.min(), gv.max()
            rec01[gok] = (gv - lo) / (hi - lo) if hi > lo else 0.5
        elif gok.sum() == 1:
            rec01[gok] = 0.5
        out[t][ok] = r01[ok] + bonus * rec01[ok]
    return out, regime
