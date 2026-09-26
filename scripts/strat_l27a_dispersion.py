"""Candidate: cross-sectional return-dispersion exposure cut on the champion (Loop-27 A).

Setup in words: rank, eligibility and the breadth-tier exposure are exactly
strat_l23a_liqconfirm (imported, never copied; itself floorhighfresh + a
liquid-confirmed breadth tier). On top, a market-level DISPERSION gauge scales
exposure down: at month t, take every name's trailing ds_k-month return
px[t]/px[t-ds_k]-1 (closes through px[t] only), and measure the cross-sectional
spread as the inter-quartile range (robust to the fat right tail). Its
percentile against its OWN history (months ds_warm..t-1, strictly before t,
at least ds_warm months of history, else no action) is compared to ds_thr.
When the percentile exceeds ds_thr, exposure is multiplied by (1 - ds_cut).
ds_dir = -1 flips the rule (cut when dispersion is unusually LOW, i.e. a
crowded, everything-moves-together tape).

Hypothesis: momentum books crash after dispersion blow-outs (winners far
ahead of losers -> reversal risk, 2018 small-cap unwind); breadth reads the
level of participation, not the spread between winners and losers.
Falsifier: no cell cuts train DD without losing more CAGR than the DD gained.

Novelty: closest rows — strat_l20c_capconc (DEAD: dispersion of the top-K
SCORES setting the book cap), strat_l26a_corrspike (DEAD: comovement ratio =
time-variance based correlation), strat_l23a_newlows (DEAD: new-low share),
vol-targeting family (DEAD, legacy: book/index volatility). None uses the
cross-sectional dispersion of returns across the board, normalised by its own
history, as an exposure control. Base: realistic exec + L25 champion.

Off-switch: ds_cut = 0 -> champion exactly.
SPACE: ds_k {3,6}, ds_thr {0.8,0.9}, ds_cut {0,0.3,0.5}, ds_dir {1,-1}, ds_warm 36.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"ds_k": [3, 6], "ds_thr": [0.8, 0.9], "ds_cut": [0.0, 0.3, 0.5],
         "ds_dir": [1, -1], "ds_warm": [36]}


def dispersion(px, k):
    px = np.asarray(px, dtype=float)
    out = np.full(px.shape[0], np.nan)
    for t in range(k, px.shape[0]):
        with np.errstate(invalid="ignore", divide="ignore"):
            r = px[t] / px[t - k] - 1.0
        r = r[np.isfinite(r) & (np.abs(r) < 10.0)]
        if r.size >= 50:
            q75, q25 = np.percentile(r, [75, 25])
            out[t] = q75 - q25
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    cut = float(params.get("ds_cut", 0.0))
    if cut <= 0:
        return scores, exposure
    k = int(params.get("ds_k", 3))
    thr = float(params.get("ds_thr", 0.9))
    sgn = int(params.get("ds_dir", 1))
    warm = int(params.get("ds_warm", 36))
    d = dispersion(panels["px"], k)
    out = np.asarray(exposure, dtype=float).copy()
    for t in range(len(out)):
        if not np.isfinite(d[t]):
            continue
        hist = d[:t]
        hist = hist[np.isfinite(hist)]
        if hist.size < warm:
            continue
        pct = (hist < d[t]).mean()
        hit = pct > thr if sgn > 0 else pct < 1.0 - thr
        if hit:
            out[t] = out[t] * (1.0 - cut)
    return scores, out
