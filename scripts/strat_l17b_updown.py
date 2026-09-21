"""Candidate: downside/upside comovement asymmetry tilt on the champion book
(strategy_lab contract).

Setup in words: the CURRENT champion chain (strat_l12b_gatefail at the
champion params: floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure with tier 0.9999,
regime-conditional book cap cap_weak/cap_full, eligibility-wobble discount
gw_w 0.15 / gf_lb 12, gf_w forced 0.0) is imported wholesale via
strat_l12b_gatefail.score, then the champion's INSIDE-DAY tilt
(strat_l15b_insideday: ids_lb 3 / ids_w -0.13, helper IMPORTED, never
copied) is applied to the imported lift exactly as that file applies it.
Before the regime-conditional cap step (mirrored inline, exactly as
strat_l15b_insideday mirrors it — a composition step, not an indicator),
the tilted lift is re-weighted by a NEW cross-sectional panel-structure
signal: the ASYMMETRY between the name's comovement with the panel in the
panel's DOWN months and in its UP months, over the ud_lb months ending at
the decision row.

    R[t,j]  = px[t,j] / px[t-1,j] - 1            (monthly simple returns)
    I[t]    = equal-weight mean of R[t,:] over names with a finite return
    c_down_j(t) = Pearson corr(R[:,j], I) over the window's months where
                  I < 0 (panel down months)
    c_up_j(t)   = Pearson corr(R[:,j], I) over the window's months where
                  I > 0 (panel up months)
    sig_j(t)    = c_down_j(t) - c_up_j(t)   (+ = co-falls harder than it
                                             co-rises; - = falls alone)

Among names with a finite sig in the row it is percentile-ranked into pct
in [0, 1]:

    tilt = 1 + ud_w * (2 * pct - 1)   # ud_w < 0 favours low down-comovement
    out  = tilted lift * tilt         # NaN sig keeps tilt 1.0

Hypothesis: the champion buys fresh 12-month-high printers and holds them
through a full month, so its realized drawdowns come from names that give
back gains with the market. A printer whose returns are UNCORRELATED from
the panel in the panel's own down months (while still riding its up
months) is a name whose move does not need the tape and does not
capitulate with it — exactly the book property the breadth-tier exposure
reacts to late. If downside-decoupled printers are the book's safer
compounders, ud_w < 0 lifts the top-15 cut's quality; if up-comovement is
what carries the 3-month hold (names that co-fall but bounce with the
next impulse), ud_w > 0 wins; if full-window comovement already captures
the conditional structure, every variant ties the base and the channel
closes.

Falsification test: if every tested (ud_lb, ud_w) combination trails the
flat base — train +96.882% / DD -17.032% / calmar 5.688, fwd +48.973% /
fwd DD -12.311% — then conditional (sign-split) comovement carries no
information beyond the champion's monthly-close rank, gates, wobble, ids
tilt and the unconditional comovement screens, and the up/down asymmetry
family is closed at this base.

Import chain: strat_l17b_updown -> strat_l12b_gatefail.score (which imports
strat_floorhighfastgate + strat_floorhighsustaincond for the gate layers and
strat_floorhightiershape for rank/exposure, and applies the wobble tilt) ->
the champion's inside-day tilt applied exactly as strat_l15b_insideday
applies it (helper _monthly_inside IMPORTED from that file, ids_lb / ids_w
passed at the champion values 3 / -0.13) -> THIS file's conditional
comovement tilt -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score (identical loop: cap = cap_full where exposure
>= 1.0 else cap_weak; lower ranks set NaN after a stable descending sort).
The tilt is inserted AFTER the ids tilt and BEFORE the cap, so it
re-weights the champion's fully tilted lift pre-cap and can change which
names the weak-month cap keeps.

PIT argument: the signal reads only the month-end close panel px. R and I
at row t use px rows up to and including row t (closes through months[t],
the decision bar); the sign split is over the window's PAST months only
and never touches t+1 or later. Names with fewer than umin finite returns
in either the down-month or up-month sub-window, or zero variance in
either, read NaN and keep tilt exactly 1.0 — eligibility and rank
unmodified, nothing dropped on missing data, nothing peeks.

Off-switch identity: ud_w = 0.0 makes tilt == 1.0 for every name and every
row (the tilt block is skipped entirely), so `out` is bitwise the
gatefail-lift-with-ids-tilt (the champion chain) and the mirrored cap
yields bitwise the champion's scores at the same params. NOTE imported
defaults leak: strat_l12b_gatefail's own default is gf_w = 0.05 — this
file setdefaults gf_w = 0.0 / gw_w = 0.0 / gf_lb = 12 BEFORE delegating,
so the off-switch is exact and the champion's gw_w 0.15 / ids_w -0.13 /
ids_lb 3 must be PASSED by the caller (champion keys, not defaults here).

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art in the inventory — (a)
strat_l17b_crowd (this loop, same designer): UNCONDITIONAL correlation
with the panel over the window; (b) strat_l17b_beta (this loop):
unconditional Cov/Var. The one thing changed: the comovement estimate is
SPLIT BY THE PANEL'S OWN SIGN and differenced — a conditional second
moment (downside vs upside beta spread). No unconditional statistic can
express it (a name with c_down 0.0 and c_up 0.8 can have the same
unconditional correlation as one with c_down 0.4 and c_up 0.4), and no
prior screened mechanism — unconditional crowd/idvol/beta included —
consumed it. This is the classic downside-beta asymmetry, untested
anywhere in the chain.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15; max_hold 3 is a HARNESS
        key passed via params-json, this file does not consume it)
        + ud_lb {12, 24} (comovement window in months; the sign split makes
          each half smaller, so the window must be longer than the crowd
          screen's)
        + ud_w {-0.3, +0.3} (percentile tilt; 0.0 = off-switch;
          negative = favour low down-comovement).
        umin (minimum finite returns per sub-window, default 4) is an
        internal guard, documented but not swept.
"""

from __future__ import annotations

import numpy as np

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside

NEEDS_DAILY = True  # the champion ids tilt reads the daily panel (mirrored
                    # from strat_l15b_insideday); this file's own signal is
                    # monthly-close only
SPACE = {
    # champion keys (pinned, docs only)
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "floor_lb": [19],
    "lookback": [12],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [5],
    "sustain_lo": [3],
    "sustain_hi": [2],
    "tier_lo": [0.9999],
    "tier_mid": [0.9999],
    "cap_weak": [11],
    "cap_full": [20],
    "gf_lb": [12],
    "gf_w": [0.0],
    "gw_w": [0.15],
    # this file's keys
    "ud_lb": [12, 24],
    "ud_w": [-0.3, 0.3],
}


def _cond_comovement(px: np.ndarray, lb: int, min_obs: int) -> np.ndarray:
    """Row t: corr(name, panel EW return) over the window's DOWN months
    minus the same over the window's UP months. NaN where either sub-window
    has < min_obs finite returns or zero variance."""
    R = np.full(px.shape, np.nan, dtype=float)
    R[1:] = px[1:] / px[:-1] - 1.0
    with np.errstate(invalid="ignore"):
        idx = np.nanmean(R, axis=1)  # panel EW monthly return, row-wise
    T = px.shape[0]
    S = np.full(px.shape, np.nan)
    for t in range(lb - 1, T):
        lo = t - lb + 1
        W = R[lo:t + 1]                      # (lb, N)
        iw = idx[lo:t + 1]                   # (lb,)
        down = np.zeros(iw.shape, dtype=bool)
        up = np.zeros(iw.shape, dtype=bool)
        fin = np.isfinite(iw)
        down[fin] = iw[fin] < 0.0
        up[fin] = iw[fin] > 0.0
        with np.errstate(invalid="ignore"):
            cd = _corr_cond(W, iw, down, min_obs)
            cu = _corr_cond(W, iw, up, min_obs)
        S[t] = cd - cu  # NaN propagates from either side
    return S


def _corr_cond(W: np.ndarray, iw: np.ndarray, sel: np.ndarray,
               min_obs: int) -> np.ndarray:
    """Pearson corr of each column of W with iw over the selected rows only;
    NaN where fewer than min_obs selected rows, < min_obs finite pairs, or
    zero variance."""
    W = W[sel]
    iw = iw[sel]
    if W.shape[0] < min_obs:
        return np.full(W.shape[1], np.nan)
    mask = np.isfinite(W)
    n = mask.sum(axis=0)
    cnt = np.maximum(n - 1, 1)
    mj = np.where(mask, W, 0.0).sum(axis=0) / np.maximum(n, 1)
    mi = np.where(mask, iw[:, None], 0.0).sum(axis=0) / np.maximum(n, 1)
    dj = np.where(mask, W - mj, 0.0)
    di = np.where(mask, iw[:, None] - mi, 0.0)
    cov = (dj * di).sum(axis=0) / cnt
    vj = (dj * dj).sum(axis=0) / cnt
    vi = (di * di).sum(axis=0) / cnt
    with np.errstate(invalid="ignore", divide="ignore"):
        c = cov / np.sqrt(vj * vi)
    return np.where((n >= min_obs) & (vj > 0) & (vi > 0), c, np.nan)


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into the off-switch. Champion values are passed, not defaulted.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, exposure = _gf_score(panels, p)

    # champion's ids tilt, mirrored exactly from strat_l15b_insideday.score
    # (same loop, same percentile form, helper imported — never copied)
    ids_w = float(params.get("ids_w", 0.0))
    if ids_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        ilb = int(params.get("ids_lb", 3))
        IDS = _monthly_inside(daily, months, cols)
        for t in range(1, lift.shape[0]):
            lo = t - ilb
            if lo < 0:
                continue
            with np.errstate(invalid="ignore"):
                share = np.nanmean(IDS[lo:t], axis=0)
            valid = np.isfinite(share)
            n = int(valid.sum())
            tilt = np.ones(lift.shape[1])
            if n >= 5:
                sv = share[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + ids_w * (2.0 * pct - 1.0)
            ok = np.isfinite(lift[t])
            lift[t] = np.where(ok, lift[t] * tilt, np.nan)

    ud_w = float(params.get("ud_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    if ud_w != 0.0:
        px = panels["px"]
        ulb = int(params.get("ud_lb", 12))
        umin = int(params.get("umin", 4))
        S = _cond_comovement(px, ulb, umin)
        for t in range(1, out.shape[0]):
            valid = np.isfinite(S[t])
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = S[t][valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + ud_w * (2.0 * pct - 1.0)
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt, np.nan)

    # cap step mirrored inline from strat_floorhightiershapeconc.score /
    # strat_l13a_concwobble.score / strat_l15b_insideday.score (book-size
    # composition, not an indicator)
    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    E = np.asarray(exposure, dtype=float)
    for t in range(out.shape[0]):
        r = out[t]
        fin = np.flatnonzero(np.isfinite(r))
        if fin.size == 0:
            continue
        cap = cf if E[t] >= 1.0 else cw
        if fin.size <= cap:
            continue
        order = fin[np.argsort(-r[fin], kind="stable")]
        out[t, order[cap:]] = np.nan
    return out, E
