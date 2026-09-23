"""Candidate: Amihud-illiquidity x Corwin-Schultz-spread DOUBLE tilt
composed on the L19 champion book (strategy_lab contract).

Setup in words: the CURRENT champion chain strat_l19a_balanced (gatefail
lift -> ids tilt -> cap -> listing-age tilt -> outrank tilt -> final cap;
top 15, nse_all, cost 25bps, split 2022-01-01) is composed VERBATIM via
`from strat_l19a_balanced import score as _l19`, and its returned scores
are then re-weighted POST-chain by the two Loop-20 round-1 liquidity tilts
SIMULTANEOUSLY, in one of two composition modes:

  mode "prod" (default): the two round-1 multipliers are multiplied —

      out[t] = scores[t] * tilt_il[t] * tilt_sp[t]

  mode "avg": ONE multiplier built from the tie-averaged mean of the two
      per-name percentile deviations —

      dev_il[t,j] = il_w * (2*pct_il[t,j] - 1)   (0 where the name fails
                                                  the il coverage guard)
      dev_sp[t,j] = sp_w * (2*pct_sp[t,j] - 1)   (ditto for sp)
      n_act(t)    = # of row-active signals (weight != 0 and t >= its lb)
      out[t,j]    = scores[t,j] * (1 + (dev_il + dev_sp) / n_act(t))

  When both weights are equal (il_w = sp_w = w) and both rows active, the
  avg form is EXACTLY the brief's one-parameter identity
  1 + w*(2*pct_avg - 1) with pct_avg = (pct_il + pct_sp)/2, because
  0.5*[w(2a-1) + w(2b-1)] = w*(2*(a+b)/2 - 1). The registered avg cells
  pass each cell's OWN weights (il_w = +0.1, sp_w = -0.05 / -0.1) into the
  general form so each signal keeps its round-1 tested direction; avg is
  prod's first-order term at half strength (1 + (d1+d2)/2 vs
  (1+d1)(1+d2) = 1 + d1 + d2 + d1*d2), i.e. a single multiplication
  instead of a product — the cleaner, dose-reduced form.

Both signals are the frozen round-1 estimators, IMPORTED not copied:
`from strat_l20b_illiq import _monthly_illiq` (Amihud
|close/prev_close - 1| / (close * volume), monthly mean; Amihud, Y. (2001),
"Illiquidity and stock returns", Journal of Financial Markets 5(1), 31-56,
eq. 1) and `from strat_l20b_spread import _monthly_spread`
(Corwin-Schultz two-day spread, eqs. 3-5; Corwin & Schultz (2012), JF
67(2), 719-760; negatives floored at 0, 1-7 day gap guard). For each
signal the window/coverage/percentile step is RE-EXPRESSED here, line for
line identical to its round-1 source: window = monthly matrix rows
[t-lb, t-1] (all bars date < months[t]); cnt = finite buckets; val =
nanmean; guard = isfinite(val) & (cnt >= max(2, ceil(frac*lb)));
n >= 5; stable argsort pct = arange(n)/(n-1);
tilt/dev = w*(2*pct-1); names failing the guard contribute dev 0 (tilt
1.0 — never NaN); rows t < lb are untouched BY THAT SIGNAL; NaN stays
NaN; |w| < 1 keeps every multiplier strictly positive (avg:
|dev_sum/n_act| <= max|w| < 1). Source files are FROZEN (md5:
strat_l20b_illiq.py 93571a2b54042308a1c2dde5b2aa644d,
strat_l20b_spread.py ad974a8d49bb447764ff1894093fccec) — this file
imports their estimators and cites their docstrings for the full
formula/PIT/coverage arguments; it never edits them.

Hypothesis (the stacking question): round 1 measured each tilt ALONE on
the same base — illiq lb12/+0.1 = train +102.350 / -15.979 / calmar
6.405 / fwd +54.405 / -10.403 (neighbourhood confirmed as the peak:
lb 9/15 tie just below, w 0.05 -> 99.48, w 0.15 -> 101.30); spread
lb4/-0.1 = +103.828 / -14.996 / 6.924 / fwd +52.515 / -13.082, spread
lb6/-0.1 = 103.309 / -15.00 / 6.889 / fwd 53.218 / -13.082, spread
lb6/-0.05 (risk-clean) = 101.800 / -15.506 / 6.570 / fwd +54.210 /
-10.381. Neither file measured the other's tilt present. Mechanistic
priors cut both ways: the winners point at OPPOSITE ends of the naive
liquidity axis (il +0.1 favours illiquid names, sp -0.05/-0.1 favours
TIGHT-spread names), so if the two percentiles are near-orthogonal the
combo STACKS (each re-orders what the other left), if they rank largely
the same names it SATURATES at the better parent, and if they pull the
same capped pool in conflicting directions it INTERFERES (below both).

Falsifier / verdict rule (pre-registered): the combo STACKS iff some
registered cell prints train > 103.828 + 0.05 = 103.878 with
DD >= -16.996 and both train halves > 0 (beat the BETTER parent by more
than the keep margin, without breaching the DD floor). Below that but
>= the weaker parent (102.350) = SATURATION at/between the parents;
below BOTH parents (train < 102.350) = INTERFERENCE. Per the Loop-17
rule any train gain bought with forward collapse or wider DD than the
floor is an artifact, not an upgrade; before ANY promotion count the
decision months where the combo's picks differ from the champion's
(Loop-16 book-composition lesson).

NOVELTY STATEMENT (closest prior art -> the ONE thing changed):
- Round-1 sources, same axis, measured ALONE: scripts/strat_l20b_illiq.py
  (frozen md5 93571a2b..., registry row pending at close-out) and
  scripts/strat_l20b_spread.py (frozen md5 ad974a8d..., registry row
  pending). Each already documents ITS changed-base novelty against the
  legacy family: registry line 29 strat_floorhighliq / line 64
  strat_floorliq / line 68 strat_highliq / line 70 strat_liqtrend /
  line 13 strat_floorhighaccum / line 30 strat_floorhighliqw — all DEAD,
  dead form = hard eligibility GATE on the OLD floorhigh/sustaincond
  chain; line 136 strat_l17d_flowdir — the accepted changed-base retest
  precedent; line 117 strat_l16c_volpart — participation, closed. This
  file re-states that base+form change (L19 champion chain; gate ->
  strictly-positive post-chain percentile multiplier) and does not
  re-argue it.
- Composition prior art: strat_l19a_balanced itself (L19) composed two
  independently screened tilts (la x or) into the champion — the sanctioned
  shape for "do two screened tilts stack".
WHAT CHANGED (the ONE thing): neither round-1 file ever ran with the
other tilt present; this file is the first measurement of the
illiquidity-premium x tight-spread-quality PAIR on the champion base,
plus the avg tie-averaged single-multiplier form, which neither source
defines. No new signal: both estimators are imported from the frozen
sources; the only new computation is the two-tilt composition logic.

Import chain: strat_l20b2_liqcombo -> strat_l19a_balanced.score (the
CURRENT champion; it neutralises gatefail's leakable defaults itself,
re-expresses ids via _monthly_inside from strat_l15b_insideday, mirrors
the cap, applies la and or tilts) -> strat_l12b_gatefail.score ->
floorhighfastgate + floorhighsustaincond + floorhightiershape (+ wobble);
plus strat_l20b_illiq._monthly_illiq and strat_l20b_spread._monthly_spread
(estimator helpers, imported from the frozen round-1 files).

PIT argument: each signal's window at row t is monthly-matrix rows
[t - lb, t - 1]; bucket k holds only bars with date in [months[k],
months[k+1]), so every bar read has date < months[t] — the same
bucket-t-1-and-older convention as ids, flowdir, and both round-1 files
(a CS pair is carried by its SECOND bar, so it is only visible from the
bucket containing that bar). The il window and the sp window each end at
t-1 under their OWN lb (4/6/9/12). Percentiles at row t use only that
row's backward cross-sections. Rows t < a signal's lb are untouched BY
THAT SIGNAL (harness only reads t >= start_i ~ month 180, far past every
lb here). The both-zero off-switch returns before either monthly matrix
is built. The delegate's PIT is unchanged from strat_l19a_balanced (ids:
daily bars strictly before months[t]; age: static listing_date; outrank:
px[t-or_lb..t]; cap: month-t ranks and E[t]). No row > t is read.

Off-switch identity: setdefault'ing mode/il_w/sp_w/il_lb/sp_lb/
il_frac/sp_frac to NEUTRALS on the params copy BEFORE delegating
(Loop-13/14 imported-default lesson), score() then short-circuits when
il_w == 0.0 AND sp_w == 0.0: it returns np.array(_l19 scores, copy=True)
and the delegate's regime, before _monthly_illiq/_monthly_spread are ever
called — bitwise the champion at the PASSED keys (champion keys are
always PASSED by the caller, never defaulted here: the delegate reads
la_w/or_w/gw_w/ids_w via .get with 0.0 defaults). This is the exact
off-switch path: mode is irrelevant when both weights are 0 (prod
registered); the identity cell must print train +98.682% / DD -15.506% /
calmar 6.364 / H1 +95.295% / H2 +101.966% / fwd +53.148% / fwd DD
-10.403%.

Flat-base metric (off-switch must reproduce exactly): train +98.682% /
DD -15.506% / calmar 6.364 / H1 +95.295% / H2 +101.966% / fwd +53.148% /
fwd DD -10.403%.

Keys consumed: mode, il_w, il_lb, il_frac, sp_w, sp_lb, sp_frac (this
file); everything else flows to the delegate (SPACE champion keys) or
the harness (max_hold 3).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1; max_hold 3 is harness)
        + mode {"prod", "avg"} (composition form, see above)
        + il_lb {9, 12} + il_w {0.1, 0.0} + il_frac [0.5] (from round-1
          illiq; 0.0 = that signal off)
        + sp_lb {4, 6} + sp_w {-0.05, -0.1, 0.0} + sp_frac [0.5] (from
          round-1 spread; 0.0 = that signal off)
        Registered cells (7 trials, pre-registered):
          1. identity  prod  il(12, 0.0)   x sp(6, 0.0)
          2. prod      prod  il(12, +0.1)  x sp(6, -0.05)
          3. prod      prod  il(12, +0.1)  x sp(6, -0.1)
          4. prod      prod  il(12, +0.1)  x sp(4, -0.1)
          5. prod      prod  il(9, +0.1)   x sp(4, -0.1)
          6. avg       avg   il(12, +0.1)  x sp(6, -0.05)
          7. avg       avg   il(12, +0.1)  x sp(6, -0.1)
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l19a_balanced import score as _l19
from strat_l20b_illiq import _monthly_illiq
from strat_l20b_spread import _monthly_spread

NEEDS_DAILY = True  # delegate's ids term reads daily; both estimators do too

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
    "la_min": [0],
    "la_w": [0.5],
    "or_lb": [6],
    "or_w": [-0.1],
    # this file's keys
    "mode": ["prod", "avg"],
    "il_lb": [9, 12],
    "il_w": [0.1, 0.0],
    "il_frac": [0.5],
    "sp_lb": [4, 6],
    "sp_w": [-0.05, -0.1, 0.0],
    "sp_frac": [0.5],
}


def _pcts(mat: np.ndarray, lb: int, frac: float) -> np.ndarray:
    """Cross-sectional percentile per row, RE-EXPRESSED line-for-line from
    the round-1 files' score() loops (strat_l20b_illiq / strat_l20b_spread):
    window rows [t-lb, t-1], cnt = finite buckets, val = nanmean, guard =
    isfinite(val) & cnt >= max(2, ceil(frac*lb)), n >= 5, stable argsort
    pct = arange(n)/(n-1). Returns months x stocks pct array, NaN wherever
    the row is before the window or a name fails the guard (=> dev 0 in
    score(), i.e. tilt 1.0 — never NaN on the champion score)."""
    n_rows, n_cols = mat.shape
    need = max(2, int(np.ceil(frac * lb)))
    pct = np.full((n_rows, n_cols), np.nan)
    for t in range(lb, n_rows):
        win = mat[t - lb : t]  # buckets t-lb..t-1: all date < months[t]
        cnt = np.isfinite(win).sum(axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            val = np.nanmean(win, axis=0)
        valid = np.isfinite(val) & (cnt >= need)
        n = int(valid.sum())
        if n < 5:
            continue
        sv = val[valid]
        order = np.argsort(sv, kind="stable")
        p = np.empty(n)
        p[order] = np.arange(n) / (n - 1)
        pct[t, valid] = p
    return pct


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-13/14 imported-default
    # lesson): my keys default to the off-switch / registered values
    # whatever the caller passes; the delegate neutralises ITS leakable
    # defaults inside strat_l19a_balanced.
    p.setdefault("mode", "prod")
    p.setdefault("il_w", 0.0)
    p.setdefault("il_lb", 12)
    p.setdefault("il_frac", 0.5)
    p.setdefault("sp_w", 0.0)
    p.setdefault("sp_lb", 6)
    p.setdefault("sp_frac", 0.5)
    scores, regime = _l19(panels, p)  # current champion chain, verbatim
    out = np.array(scores, dtype=float, copy=True)

    il_w = float(p["il_w"])
    sp_w = float(p["sp_w"])
    if il_w == 0.0 and sp_w == 0.0:
        return out, regime  # off-switch: bitwise copy of the champion,
        # before either monthly estimator matrix is built (mode irrelevant)

    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    ilb, slb = int(p["il_lb"]), int(p["sp_lb"])
    avg = str(p["mode"]) == "avg"
    dev_il = dev_sp = None
    if il_w != 0.0:
        dev_il = _pcts(_monthly_illiq(daily, months, cols),
                       ilb, float(p["il_frac"]))
        dev_il = np.where(np.isfinite(dev_il), il_w * (2.0 * dev_il - 1.0), 0.0)
    if sp_w != 0.0:
        dev_sp = _pcts(_monthly_spread(daily, months, cols),
                       slb, float(p["sp_frac"]))
        dev_sp = np.where(np.isfinite(dev_sp), sp_w * (2.0 * dev_sp - 1.0), 0.0)

    for t in range(out.shape[0]):
        a_il = dev_il is not None and t >= ilb  # signal active this row
        a_sp = dev_sp is not None and t >= slb
        if not (a_il or a_sp):
            continue  # row untouched by every active signal's window
        if avg:
            n_act = (1 if a_il else 0) + (1 if a_sp else 0)
            dev = ((dev_il[t] if a_il else 0.0)
                   + (dev_sp[t] if a_sp else 0.0)) / n_act
            mult = 1.0 + dev
        else:  # prod: multiply the two round-1 multipliers
            mult = 1.0
            if a_il:
                mult = mult * (1.0 + dev_il[t])
            if a_sp:
                mult = mult * (1.0 + dev_sp[t])
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * mult, np.nan)
    return out, regime
