"""Candidate: correlation-spike exposure cut on the Nifty 500 fresh-print book.

Setup in words: the book is strat_floorhighfresh unchanged (rank, fresh-print
eligibility, breadth-tier exposure) — imported, never copied. On top, a
market-level comovement gauge scales exposure DOWN: over the trailing `c_win`
monthly returns (closes through px[t] only), the average-correlation proxy
rho_t = var_time(equal-weight mean return) / mean_i(var_time(r_i)) (the
variance ratio, = average pairwise correlation for equal vols). When rho_t >
`c_thr`, exposure is multiplied by (1 - `c_cut`).

Hypothesis: drawdowns of a momentum/breakout book come in correlation spikes
(everything sells together, diversification vanishes); breadth tiers react to
levels late, the correlation ratio reacts to comovement early. Cutting exposure
only in high-rho months should shave DD while leaving the calm-trend months
(where the CAGR is earned) untouched.

Falsifier: if train DD does not shrink by >= 1pp at any c_thr in a monotone
neighbourhood, or CAGR falls by more than the DD improvement, the idea is dead.

Variant c_down=k: cut only when the trailing k-month equal-weight mean return
(closes through px[t]) is negative, i.e. a downward comovement spike.

Variant f_shock=x (independent key, default 0 = off): a fast exit tier that
acts only when the slow breadth regime is already weak (base exposure < 1):
exposure -> 0 in month t if the equal-weight 1-month return to px[t] < -x.

Off-switch: c_cut = 0 and f_shock = 0 reproduces strat_floorhighfresh exactly.

Novelty: registry rows strat_l17b_crowd / corrtrend / updown used comovement
as a per-stock RANK tilt on the legacy full-board harness (DEAD); none used
panel correlation as a market-level EXPOSURE control. Vol targeting
(strat_floorhighvoltarget, strat_concvoltarget) scales on book volatility, not
cross-sectional correlation; idx-dd vetoes (strat_floorhighidxdd) read index
level. Base changed too: Nifty 500 realistic harness.

PIT: r[t] = px[t]/px[t-1]-1 uses closes through px[t]; rho_t uses r[t-c_win+1..t].
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _base_score

NEEDS_DAILY = False
SPACE = {"c_win": [12], "c_thr": [0.35], "c_cut": [0.0], "c_down": [0]}


def corr_ratio(px, win):
    px = np.asarray(px, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = px[1:] / px[:-1] - 1.0
    r = np.vstack([np.full((1, px.shape[1]), np.nan), r])
    r = np.where(np.isfinite(r) & (np.abs(r) < 3.0), r, np.nan)
    out = np.full(px.shape[0], np.nan)
    for t in range(win, px.shape[0]):
        w = r[t - win + 1 : t + 1]
        ok = np.isfinite(w).all(axis=0)
        if ok.sum() < 30:
            continue
        w = w[:, ok]
        v_idx = np.var(w.mean(axis=1))
        v_mean = np.var(w, axis=0).mean()
        if v_mean > 0:
            out[t] = v_idx / v_mean
    return out


def score(panels, params):
    rank, exposure = _base_score(panels, params)
    fs = float(params.get("f_shock", 0.0))
    if fs > 0.0:
        # fast tier: only when the slow breadth regime is already weak
        # (base exposure < 1), go to cash on a 1-month equal-weight shock
        px = np.asarray(panels["px"], dtype=float)
        exposure = np.asarray(exposure, dtype=float).copy()
        with np.errstate(invalid="ignore", divide="ignore"):
            for t in range(1, px.shape[0]):
                rr = px[t] / px[t - 1] - 1.0
                rr = rr[np.isfinite(rr)]
                if rr.size >= 30 and exposure[t] < 1.0 and rr.mean() < -fs:
                    exposure[t] = 0.0
    cut = float(params.get("c_cut", 0.0))
    if cut == 0.0:
        return rank, exposure
    rho = corr_ratio(panels["px"], int(params.get("c_win", 12)))
    hot = np.isfinite(rho) & (rho > float(params.get("c_thr", 0.35)))
    if int(params.get("c_down", 0)):
        # only a DOWNWARD spike: trailing c_down-month equal-weight return < 0
        px = np.asarray(panels["px"], dtype=float)
        k = int(params.get("c_down"))
        ew = np.full(px.shape[0], np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            for t in range(k, px.shape[0]):
                rr = px[t] / px[t - k] - 1.0
                rr = rr[np.isfinite(rr)]
                if rr.size >= 30:
                    ew[t] = rr.mean()
        hot &= np.isfinite(ew) & (ew < 0.0)
    exp = np.asarray(exposure, dtype=float) * np.where(hot, 1.0 - cut, 1.0)
    return rank, exp
