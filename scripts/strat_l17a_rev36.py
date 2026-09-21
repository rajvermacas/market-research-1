"""Candidate: long-horizon reversal tilt on the champion book
(strategy_lab contract) — Loop-17 designer A, price-path structure axis.

Setup in words: the CURRENT champion chain (strat_l13a_concwobble at
lookback 12: floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure with tier 0.9999,
regime-conditional book cap cap_weak/cap_full, eligibility-wobble discount
gw_w 0.15 / gf_lb 12) carrying the inside-day pause-share tilt ids_lb 3 /
ids_w -0.13 (strat_l15b_insideday, the live champion) is composed exactly
as the L15/L16 files compose it: strat_l12b_gatefail.score imports the
lift, the ids tilt is RE-APPLIED with `_monthly_inside` IMPORTED from the
frozen strat_l15b_insideday (identical percentile machinery, identical
pre-cap application point), then ONE NEW signal re-weights the book
BEFORE the regime-conditional cap step (mirrored inline, a composition
step, not an indicator). The new signal: the name's LONG-HORIZON trailing
return, applied as a REVERSAL weight. From the monthly panel alone, at
the decision close px[t] (row t of the month-end close matrix):

    rev_t = px[t] / px[t - rev_lb] - 1        (trailing 24- or 36-month
                                               return, rev_lb months)

Among names with a finite rev in the row it is percentile-ranked into
pct in [0, 1] (higher = bigger trailing multi-year run):

    tilt = 1 + rev_w * (2 * pct - 1)   # rev_w < 0 = REVERSAL: favour
    out  = current score * tilt        # weak long histories among the
                                       # fresh printers; NaN keeps 1.0

Hypothesis: the champion buys fresh 12-month-high printers — its rank is
built on ~12-month momentum (floor-lift on the trailing-year high) — so
the book is already selected for strong recent runs. The UNTESTED
question is the multi-year history BEHIND the fresh print. A 12-month
high printed by a name that has also tripled over three years is a
late, extended, crowded momentum entry; the same fresh high printed by a
name still below where it traded 2-3 years ago is a base-breaker whose
long holders are underwater and supply is thin. The long-horizon
reversal literature (De Bondt-Thaler) finds multi-year losers outperform
multi-year winners; on this book both arms are fresh-printers, so the
tilt asks purely: among fresh 12m-high printers, does a WEAK 2-3 year
back-history continue better than a strong one? rev_w < 0 backs the
base-breakers, rev_w > 0 the extended multi-year winners. If the
short-trend gate and the rank already encode everything the long
history carries, every variant ties the champion and the channel closes.

Falsifier: rev_w 0.0 must reproduce the champion EXACTLY (train
+96.882% / DD -17.032% / calmar 5.688, fwd +48.973% / fwd DD -12.311% /
fwd bench +14.717%). The channel falsifies if no tested (rev_lb, rev_w)
cell beats train +96.882% within the 2pp DD slack (DD >= -19.032%).
Carried warning: daily-tape and return-shape tilts on this book have
been train-destructive in both directions more often than not (rngcomp,
monpath, dskew, volpart, timesince this loop) — a both-signs-harm result
closes the channel as a double-count of what the rank already prices.

Import chain: strat_l17a_rev36 -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> ids tilt re-applied with
`strat_l15b_insideday._monthly_inside` IMPORTED (frozen file; reuse,
never reimplement; application block line-for-line its own score()) ->
long-horizon reversal term is NEW math (monthly-panel ratio at a horizon
no tested term used) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score (identical loop: cap = cap_full where exposure
>= 1.0 else cap_weak; lower ranks set NaN after a stable descending sort).

PIT argument: the signal reads ONLY month-end closes px[t] and
px[t - rev_lb]. The contract allows closes THROUGH px[t] for score row t
("a holding month ... may use ... closes through px[m]") — the base
chain's own fresh-print rank is likewise computed at px[t] (floorlift /
newhigh build the trailing-year high from px[t-lb+1..t]). No row after t
is touched, no daily bar is used by this file's own signal — NEEDS_DAILY
is True ONLY because the champion's ids tilt is re-applied on the daily
panel exactly as the champion does. Names with fewer than rev_lb months
of history, or a NaN close at either endpoint, read NaN and keep tilt
exactly 1.0 — eligibility and rank unmodified, nothing dropped on
missing data, nothing peeks. The cap reads month-t ranks only.

Off-switch identity (two levels): (1) rev_w = 0.0 leaves the ids tilt
exactly as the champion applies it and the mirrored cap bitwise
unchanged, so the flat base IS the champion at the champion params (the
ids application here is line-for-line strat_l15b_insideday's own: same
nanmean window, same stable-argsort percentile, same np.where). (2)
ids_w 0.0 AND rev_w 0.0 at otherwise champion keys reproduce the
wobble-only chain at gw_w 0.15: documented Loop-15 measurement gw 0.15
alone -> train +87.00 / DD -17.34. NOTE imported defaults leak:
strat_l12b_gatefail's own default is gf_w = 0.05 — this file setdefaults
gf_lb = 12 / gf_w = 0.0 / gw_w = 0.0 BEFORE delegating, so the off-switch
is exact and the champion's gw_w 0.15 and ids keys (ids_lb 3 / ids_w
-0.13) must be PASSED by the caller (champion keys, not defaults here).
This file's own defaults are NEUTRAL: rev_w 0.0 (rev_lb 36 is inert
while the weight is 0).

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art in the mechanism inventory — (a)
the LIVE fresh-print rank itself: momentum carried by the ~12-month-high
proximity and the trailing-year return (floor-lift), i.e. the ~12m
horizon; (b) PARTIAL market-relative strength (strat_l14b_relstrength,
Loop-14): the name's trailing return MINUS the panel mean at rs_lb 6
(6-12m horizon) — forward-positive/train-negative, kept as a documented
alternative; (c) DEAD cross-sectional outrank (Loop-16,
strat_l16b_outrank): the percentile of the name's own trailing return
within the book at the SAME horizon the rank already uses (12m). The ONE
thing changed: HORIZON and SIGN — the trailing 24-36-month return, 2-3x
the longest horizon any tested term consumed, applied as a NEGATIVE
(reversal) weight. The 2-3-year back-history is a different factor from
12-month momentum (near-orthogonal cross-sectionally once the recent year
is fixed: names with identical 12m momentum differ maximally in whether
they are above or below their 3-year-ago price), and its tested sign in
the literature is OPPOSITE to momentum. It is not seasonality (seasmom —
same-calendar-month returns, DEAD), not outrank (same-horizon percentile
of the same 12m momentum), not rs (market-relative at 6-12m): the
multi-year trailing return at a negative weight is a variable nothing in
the chain or inventory consumes.

SPACE = my keys: rev_lb {24, 36} (reversal horizon in months),
        rev_w {-0.3, -0.2, -0.1, +0.2} (percentile tilt; 0.0 =
        off-switch; negative = favour weak long histories among the
        fresh printers, positive = favour extended multi-year winners).
        Champion keys pinned (passed by the caller, docs only): b_hi
        0.69, b_lo 0.45, b_mid 0.55, floor_lb 19, lookback 12, max_dist
        0.055, regime_ma 18, fast_ma 5, sustain_lo 3, sustain_hi 2,
        tier_lo 0.9999, tier_mid 0.9999, cap_weak 11, cap_full 20,
        gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13. max_hold 3
        is a HARNESS key passed via params-json; this file does not
        consume it.

Designer smoke observations (Loop-17, pre-freeze, nse_all top 15 25bps
split 2022-01-01, isolated ledger l17_dA): off-switch reproduced the
champion EXACTLY — train +96.88 / DD -17.03 / calmar 5.688, fwd +48.97 /
-12.31 (H1 +98.3 / H2 +95.5). rev_lb 36: rev_w -0.2 (reversal, primary
hypothesis) -> train +86.63 / DD -23.19 / calmar 3.74, fwd +58.79 /
-13.17; rev_w +0.2 (extended multi-year winners) -> train +86.22 /
DD -18.40 / calmar 4.68, fwd +51.27 / -17.40. BOTH signs are ~10pp below
the champion on train — the long-horizon reversal AND its opposite both
lose, so the effect is not a mis-signed edge but no train edge at all.
The reversal arm repeats the known forward-heavy signature (fwd-calmar
4.46 vs champion 3.98, fwd DD better than the +0.2 arm) — same family
behaviour as the rs line; if a forward-geometry stack is ever assembled,
rev_lb 36 / rev_w -0.2 belongs on that list, but it cannot pass the
train ratchet. Falsifier FIRED on both signs: the long-horizon channel
is closed on this base; do not spend worker windows on rev_lb 24 or
intermediate weights (they interpolate toward the champion).
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside

NEEDS_DAILY = True  # for the champion ids tilt re-application only
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
    "ids_lb": [3],
    "ids_w": [-0.13],
    # this file's keys
    "rev_lb": [24, 36],
    "rev_w": [-0.3, -0.2, -0.1, 0.2],
}


def _tilt_rows(stat: np.ndarray, target: np.ndarray, src: np.ndarray,
               lb: int, w: float) -> None:
    """Apply the percentile tilt of backward-window means of `stat` onto
    `target` rows, reading the base values from `src` (the
    strat_l15b_insideday application block, verbatim mechanics)."""
    for t in range(1, target.shape[0]):
        lo = t - lb
        if lo < 0:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            val = np.nanmean(stat[lo:t], axis=0)
        valid = np.isfinite(val)
        n = int(valid.sum())
        tilt = np.ones(target.shape[1])
        if n >= 5:
            sv = val[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt[valid] = 1.0 + w * (2.0 * pct - 1.0)
        ok = np.isfinite(src[t])
        target[t] = np.where(ok, src[t] * tilt, np.nan)


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into the off-switch. Champion values are passed, not defaulted.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, exposure = _gf_score(panels, p)
    base = np.array(lift, dtype=float, copy=True)
    out = np.array(base, dtype=float, copy=True)

    ids_w = float(params.get("ids_w", 0.0))
    if ids_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        ilb = int(params.get("ids_lb", 3))
        IDS = _monthly_inside(daily, months, cols)
        _tilt_rows(IDS, out, base, ilb, ids_w)

    rev_w = float(params.get("rev_w", 0.0))
    if rev_w != 0.0:
        px = np.asarray(panels["px"], dtype=float)
        rlb = int(params.get("rev_lb", 36))
        REV = np.full(px.shape, np.nan)
        for t in range(rlb, px.shape[0]):
            with np.errstate(invalid="ignore"):
                r = px[t] / px[t - rlb] - 1.0
            REV[t] = np.where(np.isfinite(r), r, np.nan)
        # monthly-close signal: row t's own value IS the window (the
        # decision close px[t] is visible per the contract); the daily-
        # bucket convention of stopping at bucket t-1 does not apply.
        for t in range(1, out.shape[0]):
            val = REV[t]
            valid = np.isfinite(val)
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = val[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + rev_w * (2.0 * pct - 1.0)
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
