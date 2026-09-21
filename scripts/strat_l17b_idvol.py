"""Candidate: idiosyncratic-vol-share tilt on the champion book (strategy_lab
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
signal: the share of the name's monthly-return variance that is ITS OWN,
i.e. 1 - R^2 from a rolling regression of the name's monthly returns on the
panel's equal-weight monthly return over the iv_lb months ending at the
decision row.

    R[t,j]  = px[t,j] / px[t-1,j] - 1            (monthly simple returns)
    I[t]    = equal-weight mean of R[t,:] over names with a finite return
    R2_j(t) = Pearson corr(R[:,j], I)^2 over the iv_lb months ending at t
    iv_j(t) = 1 - R2_j(t)                        (idiosyncratic vol share)

Among names with a finite iv in the row it is percentile-ranked into pct in
[0, 1]:

    tilt = 1 + iv_w * (2 * pct - 1)   # iv_w > 0 favours high idio share
    out  = tilted lift * tilt         # NaN iv keeps tilt 1.0

Hypothesis: the champion buys fresh 12-month-high printers with no
reference to where their variance comes from. A printer whose 6-12 month
path is mostly market variance (low idio share) is a leveraged expression
of the index impulse and mean-reverts with the panel; a printer whose path
is mostly its own variance (high idio share) moved on name-specific
sponsorship, which is what a 3-month hold can keep harvesting after the
market impulse fades. If idio-heavy printers continue, iv_w > 0 lifts the
top-15 cut's quality; if market-coupled printers are the durable ones,
iv_w < 0 wins; if the gates already price variance composition, every
variant ties the base and the channel closes. NOTE the sign question is
genuinely open here rather than a mirror of the crowding screen
(strat_l17b_crowd): iv ranks by |corr| INVERTED — a name at corr -0.9 and
a name at corr +0.9 both read LOW idio share, while the crowd tilt's
percentile separates them by sign. The V-shaped vs signed structure is the
difference; whether it matters is what the screen answers.

Falsification test: if every tested (iv_lb, iv_w) combination trails the
flat base — train +96.882% / DD -17.032% / calmar 5.688, fwd +48.973% /
fwd DD -12.311% — then variance composition carries no information beyond
the champion's monthly-close rank, gates, wobble and ids tilt, and the
idio-share family is closed at this base.

Import chain: strat_l17b_idvol -> strat_l12b_gatefail.score (which imports
strat_floorhighfastgate + strat_floorhighsustaincond for the gate layers and
strat_floorhightiershape for rank/exposure, and applies the wobble tilt) ->
the champion's inside-day tilt applied exactly as strat_l15b_insideday
applies it (helper _monthly_inside IMPORTED from that file, ids_lb / ids_w
passed at the champion values 3 / -0.13) -> THIS file's idio-share tilt ->
cap step mirrored inline from strat_floorhightiershapeconc.score /
strat_l13a_concwobble.score / strat_l15b_insideday.score (identical loop:
cap = cap_full where exposure >= 1.0 else cap_weak; lower ranks set NaN
after a stable descending sort). The tilt is inserted AFTER the ids tilt
and BEFORE the cap, so it re-weights the champion's fully tilted lift
pre-cap and can change which names the weak-month cap keeps.

PIT argument: the signal reads only the month-end close panel px. R and I
at row t use px rows up to and including row t (closes through months[t],
the decision bar); the window ends at row t and never touches t+1 or
later. Names with fewer than iv_min finite returns in the window (or zero
index variance) read NaN and keep tilt exactly 1.0 — eligibility and rank
unmodified, nothing dropped on missing data, nothing peeks.

Off-switch identity: iv_w = 0.0 makes tilt == 1.0 for every name and every
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
vol-scaled rank / vol-rank tilt family (strat_volmom, strat_l14a_volrank):
they scale by the name's OWN realized vol LEVEL, self-referential, nothing
about the panel; (b) the DEAD vol-targeting family (exposure scaling by
book vol — a regime/exposure mechanism, not a cross-sectional rank tilt);
(c) the PARTIAL rs line (return level minus panel mean — first-moment
difference); (d) strat_l17b_crowd (this loop, same designer): signed
correlation with the panel. The one thing changed: the signal is 1 - R^2,
the share of variance NOT explained by the panel's EW path — a
second-moment DECOMPOSITION that ignores correlation SIGN entirely (it
ranks -0.9 and +0.9 together at the bottom), which no vol-level scale, no
return-level difference and no signed-correlation tilt can express.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15; max_hold 3 is a HARNESS
        key passed via params-json, this file does not consume it)
        + iv_lb {6, 12} (regression window in months)
        + iv_w {-0.3, +0.15, +0.3} (percentile tilt; 0.0 = off-switch;
          positive = favour high idiosyncratic-vol share).
        iv_min (minimum finite returns in the window, default 6) is an
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
    "iv_lb": [6, 12],
    "iv_w": [-0.3, 0.15, 0.3],
}


def _idio_share(px: np.ndarray, lb: int, min_obs: int) -> np.ndarray:
    """Row t: 1 - R^2 of each name's monthly returns vs the panel's
    equal-weight monthly return over the lb months ending at t. NaN where
    the name has fewer than min_obs finite returns in the window or either
    variance is zero."""
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
            r2 = (cov * cov) / (vj * vi)
        ok = (n >= min_obs) & (vj > 0) & (vi > 0)
        S[t] = np.where(ok, 1.0 - np.clip(r2, 0.0, 1.0), np.nan)
    return S


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

    iv_w = float(params.get("iv_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    if iv_w != 0.0:
        px = panels["px"]
        vlb = int(params.get("iv_lb", 6))
        vmin = int(params.get("iv_min", 6))
        S = _idio_share(px, vlb, vmin)
        for t in range(1, out.shape[0]):
            valid = np.isfinite(S[t])
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = S[t][valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + iv_w * (2.0 * pct - 1.0)
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
