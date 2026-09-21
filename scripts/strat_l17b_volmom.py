"""Candidate: relative-volatility-momentum tilt on the champion book
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
signal: whether the name is heating up or cooling down RELATIVE to the
panel over the recent window — the time DERIVATIVE of realized vol,
differenced against the panel's own derivative.

    R[t,j]  = px[t,j] / px[t-1,j] - 1            (monthly simple returns)
    I[t]    = equal-weight mean of R[t,:] over names with a finite return
    v_j(t)  = std of R[:,j] over the vm_lb months ending at t
    V_i(t)  = std of I over the vm_lb months ending at t
    dv_j(t) = (v_j(t) - v_j(t-vm_lb)) / v_j(t-vm_lb)   (name vol change)
    dv_i(t) = (V_i(t) - V_i(t-vm_lb)) / V_i(t-vm_lb)   (panel vol change)
    sig_j(t) = dv_j(t) - dv_i(t)         (heating up relative to the panel)

Among names with a finite sig in the row it is percentile-ranked into pct
in [0, 1]:

    tilt = 1 + vm_w * (2 * pct - 1)   # vm_w > 0 favours relative heating
    out  = tilted lift * tilt         # NaN sig keeps tilt 1.0

Hypothesis: the champion buys fresh 12-month-high printers without asking
whether the move is accelerating or settling. A printer whose vol is
expanding FASTER than the panel's is breaking out on fresh demand —
pressure building into the high — while one heating slower than the panel
(or cooling) is drifting onto its high on stale, decaying energy. If
relative acceleration predicts continuation, vm_w > 0 lifts the top-15
cut's quality; if fast-heating names are the climactic extenders that
chop, vm_w < 0 wins; if the gates' own trend/print selection already
encodes acceleration, every variant ties the base and the channel closes.

Falsification test: if every tested (vm_lb, vm_w) combination trails the
flat base — train +96.882% / DD -17.032% / calmar 5.688, fwd +48.973% /
fwd DD -12.311% — then relative vol change carries no information beyond
the champion's monthly-close rank, gates, wobble and ids tilt, and the
vol-momentum family is closed at this base.

Import chain: strat_l17b_volmom -> strat_l12b_gatefail.score (which imports
strat_floorhighfastgate + strat_floorhighsustaincond for the gate layers and
strat_floorhightiershape for rank/exposure, and applies the wobble tilt) ->
the champion's inside-day tilt applied exactly as strat_l15b_insideday
applies it (helper _monthly_inside IMPORTED from that file, ids_lb / ids_w
passed at the champion values 3 / -0.13) -> THIS file's relative-vol-change
tilt -> cap step mirrored inline from strat_floorhightiershapeconc.score /
strat_l13a_concwobble.score / strat_l15b_insideday.score (identical loop:
cap = cap_full where exposure >= 1.0 else cap_weak; lower ranks set NaN
after a stable descending sort). The tilt is inserted AFTER the ids tilt
and BEFORE the cap, so it re-weights the champion's fully tilted lift
pre-cap and can change which names the weak-month cap keeps.

PIT argument: the signal reads only the month-end close panel px. Both vol
windows end at row t (the second ends at t-vm_lb); every input return uses
px rows up to and including row t (closes through months[t], the decision
bar); nothing touches t+1 or later. Names with a non-positive or NaN prior
vol, or fewer than vmin finite returns in either window, read NaN and keep
tilt exactly 1.0 — eligibility and rank unmodified, nothing dropped on
missing data, nothing peeks.

Off-switch identity: vm_w = 0.0 makes tilt == 1.0 for every name and every
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

NOVELTY STATEMENT: closest prior art in the inventory — (a) the DEAD
vol-rank tilt (strat_l14a_volrank): ranks the name's realized vol LEVEL —
a stock, not a flow; (b) the DEAD vol-targeting family (strat_volnewhigh /
strat_floorhighvoltarget): scales BOOK EXPOSURE by vol, not a cross-
sectional rank tilt; (c) strat_l15b_rngcomp (Loop-15, dead on train): the
LEVEL of daily range compression; (d) strat_l17b_crowd / idvol / beta
(this loop): comovement with the panel — corr/R^2/beta say WHERE the name
moves with the market, this says whether its DISAGREEMENT with the market
is growing. The one thing changed: the signal is the first difference of
realized volatility RELATIVE to the panel's own first difference — a
derivative of a second moment, differenced across the cross-section; no
prior screened mechanism consumed a vol CHANGE, least of all a
panel-relative one.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15; max_hold 3 is a HARNESS
        key passed via params-json, this file does not consume it)
        + vm_lb {6, 12} (both vol windows are vm_lb months, so the signal
          spans 2*vm_lb months of returns)
        + vm_w {-0.3, +0.3} (percentile tilt; 0.0 = off-switch;
          positive = favour names heating up faster than the panel).
        vmin (minimum finite returns per window, default 4) is an internal
        guard, documented but not swept.
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
    "vm_lb": [6, 12],
    "vm_w": [-0.3, 0.3],
}


def _rel_vol_change(px: np.ndarray, lb: int, min_obs: int) -> np.ndarray:
    """Row t: name's vol change ratio over lb months MINUS the panel EW
    return's vol change ratio over the same two windows. NaN where either
    vol is non-positive/undefined or the name has fewer than min_obs
    finite returns in the recent window."""
    R = np.full(px.shape, np.nan, dtype=float)
    R[1:] = px[1:] / px[:-1] - 1.0
    with np.errstate(invalid="ignore"):
        idx = np.nanmean(R, axis=1)  # panel EW monthly return, row-wise
    T = px.shape[0]
    S = np.full(px.shape, np.nan)
    for t in range(2 * lb - 1, T):
        cur = slice(t - lb + 1, t + 1)
        pri = slice(t - 2 * lb + 1, t - lb + 1)
        vj_now = _std_nan(R[cur], min_obs)                # (N,)
        vj_pri = _std_nan(R[pri], min_obs)                # (N,)
        vi_now = _std_nan(idx[cur][:, None], 1)[0]        # scalar
        vi_pri = _std_nan(idx[pri][:, None], 1)[0]        # scalar
        if not (np.isfinite(vi_now) and np.isfinite(vi_pri) and vi_pri > 0):
            continue
        dvi = (vi_now - vi_pri) / vi_pri
        with np.errstate(invalid="ignore", divide="ignore"):
            dvj = (vj_now - vj_pri) / vj_pri
        ok = np.isfinite(vj_now) & np.isfinite(vj_pri) & (vj_pri > 0)
        S[t] = np.where(ok, dvj - dvi, np.nan)
    return S


def _std_nan(W: np.ndarray, min_obs: int) -> np.ndarray:
    """Column std of a 2-D window, NaN where fewer than min_obs finite."""
    mask = np.isfinite(W)
    n = mask.sum(axis=0)
    cnt = np.maximum(n - 1, 1)
    m = np.where(mask, W, 0.0).sum(axis=0) / np.maximum(n, 1)
    d = np.where(mask, W - m, 0.0)
    v = (d * d).sum(axis=0) / cnt
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.sqrt(v)
    return np.where(n >= min_obs, s, np.nan)


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

    vm_w = float(params.get("vm_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    if vm_w != 0.0:
        px = panels["px"]
        mlb = int(params.get("vm_lb", 6))
        vmin = int(params.get("vmin", 4))
        S = _rel_vol_change(px, mlb, vmin)
        for t in range(1, out.shape[0]):
            valid = np.isfinite(S[t])
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = S[t][valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + vm_w * (2.0 * pct - 1.0)
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
