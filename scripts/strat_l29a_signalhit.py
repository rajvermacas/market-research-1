"""Candidate: SIGNAL-BOOK HEALTH (trailing hit rate / excess return of the champion's own top-N signal set) as an exposure cut on the L25 champion (Loop-29 A).

Setup in words: rank, eligibility, book policy and base exposure are exactly the
L25 champion strat_l23a_liqconfirm (imported, never copied). The "signal book"
at row s is the top sh_n names by the champion's own scores[s] (finite scores
only; no fill / lock / liquidity rules, equal weight - a proxy for the held
book, not a causal replay of it). Its realized month is px[s+1]/px[s]-1.
At decision row t, over the last sh_k completed signal months (s = t-sh_k..t-1,
all realized by px[t]):
  sh_mode "hit" -> h = mean share of signal-book names that rose;
                   if h < sh_thr: exposure *= (1 - sh_cut)
  sh_mode "rel" -> x = mean(signal-book return - board mean return);
                   if x < -sh_thr: exposure *= (1 - sh_cut)
Everything uses closes through px[t]; the base regime is unchanged otherwise.

Hypothesis: momentum strategies fail in clusters (momentum crashes / rotation
months); when the ranked set itself has been losing for sh_k months, the next
month is worse than the breadth tiers alone imply.
Falsifier: no cell beats the champion on train CAGR at no deeper DD, or the
gain rests on <= 3 firings.

Novelty: closest rows are strat_l17c_eqstate (equity-curve state as a RANK
tilt on the legacy chain, DEAD), strat_l17o_consist (per-stock monthly hit rate
as a rank tilt, DEAD) and strat_l27a_dispersion (board return dispersion). The
one thing that changed: the champion's OWN signal set's trailing hit rate /
excess return drives the EXPOSURE (not a rank tilt, not the board). Base: L25
champion (realistic exec).

Off-switch: sh_k = 0 -> champion exactly.
SPACE: sh_k {1,2,3}, sh_thr hit {.35,.4} / rel {.03,.05}, sh_cut {.5,1.0},
sh_n 25.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _champ
from strat_l29a_breadthspread import report_firings

NEEDS_DAILY = True
SPACE = {"sh_k": [0, 1, 2, 3], "sh_thr": [0.03, 0.05, 0.35, 0.4], "sh_cut": [0.5, 1.0],
         "sh_mode": ["hit", "rel"], "sh_n": [25]}


def signal_stats(scores, px, n):
    T = len(px)
    hit = np.full(T, np.nan)
    rel = np.full(T, np.nan)
    for s in range(T - 1):
        sc = scores[s]
        ok = np.isfinite(sc) & np.isfinite(px[s]) & np.isfinite(px[s + 1]) & (px[s] > 0)
        if ok.sum() < n:
            continue
        idx = np.where(ok)[0]
        top = idx[np.argsort(-sc[idx])[:n]]
        r = px[s + 1] / px[s] - 1.0
        hit[s + 1] = np.mean(r[top] > 0)          # realized at row s+1
        rel[s + 1] = np.mean(r[top]) - np.mean(r[ok])
    return hit, rel


def score(panels, params):
    res = _champ(panels, params)
    scores, exposure = res[0], res[1]
    k = int(params.get("sh_k", 0))
    if k <= 0:
        return res
    thr = float(params.get("sh_thr", 0.4))
    cut = float(params.get("sh_cut", 0.5))
    mode = params.get("sh_mode", "hit")
    hit, rel = signal_stats(np.asarray(scores, dtype=float), panels["px"],
                            int(params.get("sh_n", 25)))
    base = np.asarray(exposure, dtype=float)
    out = base.copy()
    for t in range(k, len(out)):
        w = (hit if mode == "hit" else rel)[t - k + 1:t + 1]
        if not np.all(np.isfinite(w)):
            continue
        m = float(np.mean(w))
        if (mode == "hit" and m < thr) or (mode == "rel" and m < -thr):
            out[t] = base[t] * (1.0 - cut)
    report_firings(panels["months"], base, out, "L29A-sh")
    return (scores, out) + tuple(res[2:])
