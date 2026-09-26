"""Candidate (L29 designer B): Nifty 500 fresh-print book with an EQUITY-CURVE
drawdown overlay keyed to the book's own causal proxy curve (strategy_lab contract).

Setup in words: rank and breadth-tier exposure are strat_floorhighfresh's,
imported unchanged (universe nifty500, top 25). On top, a proxy of the base
book is replayed causally: at each past month-end t the top-`top` names by the
base score are held equal-weight for one month at the base exposure, giving a
proxy monthly return r[t] = e[t] * mean(px[t+1]/px[t] - 1) over those names.
For the holding month starting months[m] only r[t] with t+1 <= m is used
(closes through px[m]). The proxy equity curve's drawdown from its running
peak, dd[m], drives the overlay:

    dd[m] <= -dd_thr  ->  exposure[m] *= dd_cut      (else unchanged)

The proxy is the UN-overlaid base book, so the overlay never feeds back into
its own trigger (no lock-in to cash).

Novelty: first equity-curve (own-book drawdown) exposure rule in the registry
(no 'equity curve'/'book drawdown' row; volatility-scaling legacy rows scale by
index or name vol, new-low share cap L23 keyed to market lows). The target was
MOTIVATED by a revealed forward number: the Nifty 500 base's L25 gate showed
forward DD -25.65. Every threshold here is chosen on train (pre-2022) months
only; no forward value is looked at, computed for display or printed.

Off-switch: dd_cut = 1.0 (or dd_thr >= 1) returns the base exposure exactly.
SPACE = strat_floorhighfresh params + dd_thr {0.06,0.08,0.10,0.12,0.15},
        dd_cut {1.0, 0.5, 0.0}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _fresh_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65], "b_mid": [0.58], "b_lo": [0.45], "floor_lb": [24],
    "lookback": [16], "max_dist": [0.055], "regime_ma": [24],
    "dd_thr": [0.06, 0.08, 0.10, 0.12, 0.15],
    "dd_cut": [1.0, 0.5, 0.0],
}


def proxy_returns(px, scores, exposure, top):
    """r[t] = e[t] * equal-weight next-month return of the top names at t.
    r[t] uses px[t+1]; callers deciding at month m may only read t <= m-1."""
    n = px.shape[0]
    r = np.zeros(n)
    for t in range(n - 1):
        s = scores[t]
        ok = np.isfinite(s) & np.isfinite(px[t]) & np.isfinite(px[t + 1]) & (px[t] > 0)
        if exposure[t] <= 0 or ok.sum() < max(top // 2, 3):
            continue
        idx = np.where(ok)[0]
        pick = idx[np.argsort(-s[idx], kind="stable")[:top]]
        r[t] = float(exposure[t]) * float(np.mean(px[t + 1, pick] / px[t, pick] - 1.0))
    return r


def proxy_dd(px, scores, exposure, top):
    """dd[m]: proxy drawdown known at the start of holding month m (uses r[:m])."""
    r = proxy_returns(px, scores, exposure, top)
    n = len(r)
    dd = np.zeros(n)
    eq, peak = 1.0, 1.0
    for m in range(n):
        if m >= 1:
            eq *= 1.0 + r[m - 1]
            peak = max(peak, eq)
        dd[m] = eq / peak - 1.0
    return dd, r


def score(panels, params):
    scores, exposure = _fresh_score(panels, params)
    exposure = np.asarray(exposure, dtype=float)
    cut = float(params.get("dd_cut", 1.0))
    thr = float(params.get("dd_thr", 1.0))
    if cut == 1.0 or thr >= 1.0:
        return scores, exposure
    top = int(params.get("top", 25))
    dd, _ = proxy_dd(panels["px"], scores, exposure, top)
    out = exposure.copy()
    fire = dd <= -thr
    out[fire] = out[fire] * cut
    return scores, out
