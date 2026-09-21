"""Candidate: correlation-trend tilt on the champion book (strategy_lab
contract).

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
signal: whether the name is JOINING or DECOUPLING from the panel's
co-movement — the change over the window of its correlation with the
panel's equal-weight monthly return.

    R[t,j]  = px[t,j] / px[t-1,j] - 1            (monthly simple returns)
    I[t]    = equal-weight mean of R[t,:] over names with a finite return
    c_j(t)      = Pearson corr(R[:,j], I) over the ct_lb months ending at t
    c_j(t-ct_lb)= Pearson corr(R[:,j], I) over the ct_lb months ending
                  ct_lb months earlier (the prior, non-overlapping window)
    sig_j(t)    = c_j(t) - c_j(t-ct_lb)   (+ = joining the herd,
                                          - = decoupling from it)

Among names with a finite sig in the row it is percentile-ranked into pct
in [0, 1]:

    tilt = 1 + ct_w * (2 * pct - 1)   # ct_w > 0 favours names JOINING
    out  = tilted lift * tilt         # NaN sig keeps tilt 1.0

Hypothesis: the champion buys fresh 12-month-high printers without asking
whether the co-movement that produced the high is rising or falling. A
printer whose correlation with the panel is FALLING into its high is
decoupling — its late-stage upside is coming from name-specific demand,
not the market's (a fresh high that no longer needs the tape); one whose
correlation is RISING into its high has just re-coupled to a market
impulse and gives the high back when the impulse stalls. If decoupling
printers continue, ct_w < 0 lifts the top-15 cut's quality; if re-coupled
names are the durable ones, ct_w > 0 wins; if the level-of-correlation
screen (strat_l17b_crowd) already captures everything comovement knows
and the trend adds nothing, every variant ties the base and the channel
closes.

Falsification test: if every tested (ct_lb, ct_w) combination trails the
flat base — train +96.882% / DD -17.032% / calmar 5.688, fwd +48.973% /
fwd DD -12.311% — then the correlation TREND carries no information beyond
the champion's monthly-close rank, gates, wobble, ids tilt and (where the
crowd screen put them) correlation LEVELS, and the corrtrend family is
closed at this base.

Import chain: strat_l17b_corrtrend -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> the champion's inside-day tilt applied exactly as
strat_l15b_insideday applies it (helper _monthly_inside IMPORTED from that
file, ids_lb / ids_w passed at the champion values 3 / -0.13) -> THIS
file's correlation-trend tilt -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score (identical loop: cap = cap_full where exposure
>= 1.0 else cap_weak; lower ranks set NaN after a stable descending sort).
The tilt is inserted AFTER the ids tilt and BEFORE the cap, so it
re-weights the champion's fully tilted lift pre-cap and can change which
names the weak-month cap keeps.

PIT argument: the signal reads only the month-end close panel px. Both
correlation windows end at row t (the prior ends at t-ct_lb); every input
return uses px rows up to and including row t (closes through months[t],
the decision bar); nothing touches t+1 or later. Names with fewer than
cmin finite returns in either window, or zero variance in either window,
read NaN and keep tilt exactly 1.0 — eligibility and rank unmodified,
nothing dropped on missing data, nothing peeks.

Off-switch identity: ct_w = 0.0 makes tilt == 1.0 for every name and every
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
strat_l17b_crowd (this loop, same designer): the LEVEL of the name's
correlation with the panel over one window; (b) strat_l14b_relstrength
(PARTIAL): return-level difference vs the panel mean; (c) the DEAD
breadth-change/derivative regime (Loop-14): it took the DERIVATIVE of a
MARKET-WIDE scalar (breadth share) and scaled EXPOSURE with it — a
portfolio-level exposure mechanism; this file takes the derivative of a
PER-NAME co-movement coefficient and re-RANKS the cross-section, a
different variable at a different level. The one thing changed: the signal
is the first difference of the name's panel correlation across two
non-overlapping windows — the velocity of the co-movement structure. No
prior screened mechanism consumed a correlation change.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15; max_hold 3 is a HARNESS
        key passed via params-json, this file does not consume it)
        + ct_lb {6, 12} (each correlation window is ct_lb months, so the
          trend spans 2*ct_lb months of returns; the two windows do not
          overlap)
        + ct_w {-0.3, +0.3} (percentile tilt; 0.0 = off-switch;
          negative = favour decoupling, positive = favour joining).
        cmin (minimum finite returns per window, default 4) is an internal
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
    "ct_lb": [6, 12],
    "ct_w": [-0.3, 0.3],
}


def _corr_now_prior(px: np.ndarray, lb: int, min_obs: int) -> np.ndarray:
    """Row t: corr(name, panel EW return) over the lb months ending at t
    MINUS the same correlation over the lb months ending lb rows earlier.
    NaN where either window has < min_obs finite returns or zero
    variance."""
    R = np.full(px.shape, np.nan, dtype=float)
    R[1:] = px[1:] / px[:-1] - 1.0
    with np.errstate(invalid="ignore"):
        idx = np.nanmean(R, axis=1)  # panel EW monthly return, row-wise
    T = px.shape[0]
    S = np.full(px.shape, np.nan)
    for t in range(2 * lb - 1, T):
        c_now = _corr_row(R[t - lb + 1:t + 1], idx[t - lb + 1:t + 1], min_obs)
        c_pri = _corr_row(R[t - 2 * lb + 1:t - lb + 1],
                          idx[t - 2 * lb + 1:t - lb + 1], min_obs)
        S[t] = c_now - c_pri  # NaN propagates from either window
    return S


def _corr_row(W: np.ndarray, iw: np.ndarray, min_obs: int) -> np.ndarray:
    """Pearson corr of each column of W with iw; NaN where fewer than
    min_obs finite returns or zero variance."""
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

    ct_w = float(params.get("ct_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    if ct_w != 0.0:
        px = panels["px"]
        clb = int(params.get("ct_lb", 6))
        cmin = int(params.get("cmin", 4))
        S = _corr_now_prior(px, clb, cmin)
        for t in range(1, out.shape[0]):
            valid = np.isfinite(S[t])
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = S[t][valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + ct_w * (2.0 * pct - 1.0)
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
