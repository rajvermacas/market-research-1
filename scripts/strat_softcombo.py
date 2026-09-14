"""Candidate: soft momentum/pullback blend — tilt, not filter (strategy_lab contract).

Mutation on strat_combo: the hard gate (momentum only where pullback fires)
starved the book — strict combo managed train +10.11%/fwd +4.37% because most
months had too few eligible names and the harness sat in cash. Loosening the
gate recovered to train +20.87%/fwd +17.84%, the only dual bench-beat so far.

This file removes the gate entirely: rank by trailing momentum (the return
driver), then add a bounded bonus for names currently showing a pullback-turn
inside an intact uptrend (the timing tilt). Losers excluded by abs_mom stay
excluded; winners get reordered, never vetoed. Invested% should track plain
momentum (~60%+), not the gated book.

Score per month: rank01(mom) + bonus * rec01(gate), where rank01 is the
cross-sectional rank of momentum scaled 0..1 and rec01 is the pullback
recovery scaled 0..1 (0 where no pullback fires). NaN where mom is NaN.
Regime overlay: momentum's own index-vs-MA gate, reused verbatim.

Reuses strat_momentum.score and strat_rsi_pullback.score — no second copy of
either signal. Params are the union of both SPACEs plus `bonus`.
"""

from __future__ import annotations

import numpy as np

from strat_momentum import score as _mom_score
from strat_rsi_pullback import score as _pb_score

NEEDS_DAILY = True
SPACE = {"note": "union of strat_momentum.SPACE and strat_rsi_pullback.SPACE plus bonus [0..1]"}


def score(panels, params):
    bonus = float(params.get("bonus", 0.3))
    mom, regime = _mom_score(panels, params)
    gate, _ = _pb_score(panels, params)
    out = np.full_like(mom, np.nan)
    for t in range(mom.shape[0]):
        m = mom[t]
        ok = np.isfinite(m)
        n = int(ok.sum())
        if n == 0:
            continue
        order = np.argsort(np.where(ok, m, -np.inf))
        ranks = np.empty_like(m)
        ranks[:] = np.nan
        ranks[order] = np.arange(m.shape[0], dtype=float)
        # ranks[order[k]] = k; best (largest m) gets n-1
        r01 = np.full_like(m, np.nan)
        r01[ok] = ranks[ok] / max(n - 1, 1)
        g = gate[t]
        gok = ok & np.isfinite(g)
        rec01 = np.zeros_like(m)
        if gok.sum() >= 2:
            gv = g[gok]
            lo, hi = gv.min(), gv.max()
            if hi > lo:
                rec01[gok] = (gv - lo) / (hi - lo)
            else:
                rec01[gok] = 0.5
        elif gok.sum() == 1:
            rec01[gok] = 0.5
        out[t][ok] = r01[ok] + bonus * rec01[ok]
    return out, regime
