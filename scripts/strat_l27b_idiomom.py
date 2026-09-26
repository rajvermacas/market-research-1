"""Candidate: idiosyncratic (residual) momentum rank tilt on the L23-A champion (Loop-27 B).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm
(imported, verbatim). Monthly returns r[k] = px[k]/px[k-1]-1 (closes through
px[t] only); market return mk[k] = equal-weight mean of r[k] over names with a
finite return. For each name at month t, OLS of its last im_lb monthly
returns (k = t-im_lb+1..t, all finite required) on mk gives intercept a
and residuals e; signal = a*im_lb/std(e) (the beta-adjusted return drift over
the window scaled by residual vol; Blitz-Huij-Martens idiosyncratic momentum
in t-stat form - residuals of an OLS with intercept sum to zero, so the
drift lives in a). Cross-sectional percentile pct among names with a finite score;
score multiplied by 1 + im_w*(2*pct-1). NaN scores stay NaN; im_w=0 is the
exact off-switch. Regime/exposure untouched.

Hypothesis: part of a fresh-print name's strength is market beta that a
breadth-driven book already owns through its exposure layer; the stock-
specific (residual) part of the trend is the documented, less crash-prone
momentum component (residual momentum has shallower momentum crashes), so
tilting toward it should keep CAGR while lowering DD.
Falsifier: neither sign beats +30.09/-17.22 train.

Novelty: closest rows strat_l17b_idvol (idiosyncratic VOLATILITY share
1-R^2, L17 legacy, DEAD), strat_l14b_relstrength / strat_l22b_liqrs
(raw return minus market, no beta, no volatility scaling), strat_l26b_upmonths
(sign count of raw returns). The one new thing: the rank uses the
beta-adjusted residual return scaled by its own residual volatility - never
tested in any loop.
"""
from __future__ import annotations
import numpy as np
from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"im_w": [-0.1, 0.1, 0.2], "im_lb": [12]}


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


def idio_signal(px, lb):
    T, N = px.shape
    r = np.full((T, N), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        r[1:] = px[1:] / px[:-1] - 1
    r[~np.isfinite(r)] = np.nan
    cnt = np.isfinite(r).sum(axis=1)
    mk = np.where(cnt >= 20, np.nansum(np.nan_to_num(r), axis=1) / np.maximum(cnt, 1), np.nan)
    sig = np.full((T, N), np.nan)
    for t in range(lb, T):
        y = r[t - lb + 1:t + 1]
        x = mk[t - lb + 1:t + 1]
        if not np.all(np.isfinite(x)):
            continue
        ok = np.all(np.isfinite(y), axis=0)
        if ok.sum() == 0:
            continue
        Y = y[:, ok]
        xc = x - x.mean()
        vx = (xc ** 2).sum()
        if vx <= 0:
            continue
        beta = (xc[:, None] * (Y - Y.mean(axis=0))).sum(axis=0) / vx
        alpha = Y.mean(axis=0) - beta * x.mean()
        e = Y - alpha - beta * x[:, None]
        sd = e.std(axis=0, ddof=1)
        # OLS residuals sum to zero by construction, so use alpha*lb (the
        # residual-mean drift) scaled by residual vol as the t-stat form
        s = np.where(sd > 0, alpha * lb / sd, np.nan)
        col = np.full(N, np.nan)
        col[ok] = s
        sig[t] = col
    return sig


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("im_w", 0.0))
    if w == 0.0:
        return scores, exposure
    lb = int(params.get("im_lb", 12))
    sig = idio_signal(np.asarray(panels["px"], dtype=float), lb)
    return _pct_tilt(scores, sig, w), exposure
