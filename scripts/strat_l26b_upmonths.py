"""Candidate: trend-consistency tilt on the L23-A champion (Loop-26 B).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported).
For each name at month t, uc = share of the last uc_lb monthly returns
(px[t-k]/px[t-k-1]-1, k=0..uc_lb-1, closes through px[t]) that are positive.
Cross-sectional percentile pct of uc among names with a finite score; score is
multiplied by 1 + uc_w*(2*pct-1). NaN scores stay NaN; uc_w=0 is the exact
off-switch. Regime untouched.

Hypothesis: among fresh-high names, a steady staircase (many up months) is a
more persistent trend than a single burst; uc_w>0 raises CAGR without DD.
Falsifier: neither sign beats +30.09/-17.22 train.

Novelty: trend consistency was tested only as legacy DEAD rows
(strat_floortrendq / strat_breakrec, legacy exec, "breakout recency, base
duration, trend consistency"). Declared changed-base retest: realistic
execution + the L23-A liquid-confirmed champion, applied as a percentile tilt.
"""
from __future__ import annotations
import numpy as np
from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"uc_w": [-0.2, 0.2], "uc_lb": [12]}


def _pct_tilt(scores, sig, w):
    out = np.array(scores, dtype=float, copy=True)
    for t in range(out.shape[0]):
        m = np.isfinite(out[t]) & np.isfinite(sig[t])
        if m.sum() < 2:
            continue
        v = sig[t, m]
        r = v.argsort().argsort().astype(float)
        pct = r / (len(v) - 1)
        out[t, m] = out[t, m] * (1.0 + w * (2 * pct - 1))
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("uc_w", 0.0))
    if w == 0.0:
        return scores, exposure
    lb = int(params.get("uc_lb", 12))
    px = panels["px"]
    with np.errstate(invalid="ignore", divide="ignore"):
        r = px[1:] / px[:-1] - 1
    up = np.where(np.isfinite(r), (r > 0).astype(float), np.nan)
    up = np.vstack([np.full((1, px.shape[1]), np.nan), up])
    sig = np.full_like(px, np.nan, dtype=float)
    for t in range(lb, px.shape[0]):
        win = up[t - lb + 1:t + 1]
        n = np.isfinite(win).sum(axis=0)
        s = np.nansum(win, axis=0)
        sig[t] = np.where(n >= lb, s / np.maximum(n, 1), np.nan)
    return _pct_tilt(scores, sig, w), exposure
