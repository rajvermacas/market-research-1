"""Candidate: spread-CHANGE (first difference of the champion's own trailing
mean spread) percentile tilt, level term kept underneath (strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l20b_spread (strat_l19a_balanced
gatefail lift -> ids tilt -> cap -> age tilt -> outrank tilt -> cap, then the
Corwin-Schultz spread-LEVEL percentile tilt at sp_lb 4 / sp_w -0.05 / sp_frac 0.5)
is composed VERBATIM via `from strat_l20b_spread import score as _l20` with the
champion's sp keys PINNED underneath (setdefault to 4 / -0.05 / 0.5, so a caller
omitting them still gets the champion; a caller PASSING sp_w 0.0 — the
dynamic-only control cell — wins, setdefault never overrides). On top of the
champion's returned scores this file applies ONE new term: a cross-sectional
percentile tilt on the FIRST DIFFERENCE of the same trailing mean spread the
champion already ranks on.

Level series (identical estimator and window to the champion's level term,
recomputed here only for the new term; imported, never re-implemented:

    SPR[t, j]   = _monthly_spread (strat_l20b_spread) monthly CS spread buckets
    L[t, j]     = nanmean(SPR[t-sp_lb : t, j]) over buckets with
                  count >= ceil(sp_frac * sp_lb)      # the champion's level
    delta[t, j] = L[t, j] - L[t - sc_lb, j]           # THE CHANGE: a trailing
                  # mean at t minus the same trailing mean sc_lb months earlier
                  # -> negative = spread NARROWING (improving execution),
                  #    positive = spread WIDENING

delta is percentile-ranked cross-sectionally among names with BOTH endpoints
finite (each endpoint already carries the champion's own coverage guard), and
applied as:

    tilt[t] = 1 + sc_w * (2 * pct - 1)     # pct in [0,1], |sc_w| < 1
    out[t]  = out[t] * tilt                # finite entries only, NaN stays NaN

Rows t < sp_lb + sc_lb are untouched (an endpoint does not exist yet); names
failing the endpoint coverage keep tilt exactly 1.0 (re-ranking, never a gate);
|sc_w| < 1 keeps the multiplier strictly positive. Both signs are first-class:
sc_w < 0 favours NARROWING names (liquidity quietly improving, the book enters
and exits cheaper next month than last), sc_w > 0 favours WIDENING names (the
premium-for-illiquidity story paid where execution is deteriorating).

Hypothesis: the champion ranks spread LEVEL — a name's standing cost position.
The dynamics ask a different question of the SAME channel: is this name's cost
position IMPROVING or DETERIORATING relative to itself a few months ago? The
champion's level tilt and this change term are orthogonal at the data level
(a structurally wide-spread name can be narrowing fast; a structurally tight
name can be widening), so the change may carry information the level does not.
The cell with BOTH terms active (sp_w -0.05 + sc_w != 0) is the direct test of
"beyond the level already in the champion"; the sp_w 0.0 control cell shows
what the change does alone. If every active cell trails the flat base, spread
DYNAMICS (change) adds nothing beyond the level and the axis closes.

Falsifier: if ALL four SPACE variants trail the flat base — train +102.990% /
DD -15.506% / ret-DD 6.642 / fwd +54.057% / fwd DD -10.381% — on train CAGR
with no offsetting improvement in drawdown or forward (operationally: the
harness keep rule never fires on the smoke ledger; per the Loop-17 rule a train
gain bought with wider DD or a forward collapse is an ARTIFACT), then the
spread-change axis closes on the champion base. Before ANY promotion: this
tilt re-orders the capped pool (a book-composition mechanism) — count the
decision months where its picks differ from the champion's (Loop-16 lesson;
footprint 23/139 was the champion level term's).

NOVELTY STATEMENT (closest registry rows -> the ONE thing that changed):
- research/tested_mechanisms.tsv line 146 strat_l20b_spread — the CLOSEST
  prior art and this file's own base: Corwin-Schultz spread LEVEL percentile
  tilt, PROMOTED champion (sp_lb 4 / sp_w -0.05, train +102.99). Same signal
  family, same estimator, same tilt machinery. ONE THING CHANGED: LEVEL ->
  FIRST DIFFERENCE — the champion ranks where a name's spread sits; this file
  ranks the change in that same trailing mean over sc_lb months (narrowing
  vs widening). Not a re-weight: the input series is a difference, not a
  level, and its cross-sectional order is different from the level's (a
  difference is invariant to a name's standing spread position).
- research/tested_mechanisms.tsv line 70 strat_liqtrend — the legacy liquidity
  TREND row (DEAD): its form was a hard eligibility GATE on the old
  floorhigh/sustaincond chain and its signal was VOLUME/turnover liquidity,
  not a spread estimator; a gate can only remove names. Changed base + changed
  form (positive post-chain multiplier) as in the sanctioned l20 retest.
- research/tested_mechanisms.tsv line 124 strat_l17b_corrtrend — the nearest
  temporal-derivative precedent (DEAD 72.2-87.5 on the ids base): a trend of
  a DIFFERENT quantity (average correlation), never of spread, never on this
  base. Line 119 strat_l17a_rangeac (range serial dependence, DEAD) measures
  autocorrelation of range, not the first difference of a cost level.
- No registry row has ever differenced a spread estimator; the spread channel
  itself was opened in Loop-20 and only its LEVEL was ever screened.

Import chain: strat_l21b_spreadchg -> strat_l20b_spread.score (the CURRENT
champion: CS level tilt on the l19 chain) -> strat_l19a_balanced ->
strat_l12b_gatefail + strat_l15b_insideday. This file adds only the
post-chain change tilt; the CS estimator is imported from strat_l20b_spread
(`_monthly_spread`), never copied.

PIT argument: bucket k of _monthly_spread contains only pairs whose CARRYING
(second) bar falls in [months[k], months[k+1]); L[t] reads buckets
[t-sp_lb, t-1] and L[t-sc_lb] reads buckets [t-sc_lb-sp_lb, t-sc_lb-1] —
both windows end strictly before months[t], and the older one is strictly in
the past of the newer. The percentile at row t uses only that row's backward
cross-section; rows t < sp_lb + sc_lb are untouched; no row > t is read
anywhere. The delegate's PIT is unchanged from strat_l20b_spread (ids: daily
bars strictly before months[t]; age: static listing_date; outrank:
px[t-or_lb]..px[t]; cap: month-t ranks; level: buckets t-4..t-1).

Off-switch identity: sc_w = 0.0 (this file's OWN setdefault, applied to the
params copy BEFORE delegating — Loop-13/14 imported-default lesson) skips the
change block entirely and returns the delegate's scores untouched, so `out`
is bitwise strat_l20b_spread's returned scores at the PASSED keys — with the
sp keys pinned to the champion dose above, that is the champion bit-exactly.
Champion keys are always PASSED by the caller, never defaulted here: the
delegate's parents read la_w/or_w/gw_w/ids_w via .get with 0.0 defaults, so
a missing key would silently de-tune the base.

Flat-base metric (off-switch must reproduce exactly): train +102.990% /
DD -15.506% / ret-DD 6.642 / H1 +100.204% / H2 +105.682% / fwd +54.057% /
fwd DD -10.381% / full +82.001% / full DD -20.728%.

Keys consumed: this file reads sc_w, sc_lb, and (for the level series the
change differences) sp_lb, sp_frac — both pinned to the champion dose via
setdefault. Everything else in params-json flows through to the delegate (all
SPACE champion keys incl. sp_w, which the control cell sets to 0.0) or is read
by the harness (max_hold 3).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1, sp_lb 4, sp_w -0.05,
        sp_frac 0.5; max_hold 3 is a HARNESS key passed via params-json)
        + FIVE documented cells, one literal trial each (smoke = all five):
          1. OFF-SWITCH identity: canonical champion JSON (sc_w absent ->
             0.0) — must reproduce the flat-base metric bit-exactly
          2. BOTH terms active:  sc_lb 4,  sc_w -0.05 (champion level on)
          3. BOTH terms active:  sc_lb 4,  sc_w +0.05 (other sign)
          4. BOTH terms active:  sc_lb 12, sc_w -0.05 (year-over-year change)
          5. CONTROL (change alone): sc_lb 4, sc_w -0.05, sp_w 0.0 — the
             champion level term OFF, isolating the change term; the other
             side of the "beyond the level" question
          sc_lb is the change lag in months (4 = the champion's own level
          window differenced, 12 = year-over-year); sc_w < 0 favours
          NARROWING names, sc_w > 0 favours WIDENING, 0.0 = off-switch
        + sp_frac [0.5] pinned (the level-series coverage guard, identical
          to the champion's).
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l20b_spread import _monthly_spread, score as _l20

NEEDS_DAILY = True  # the champion chain (ids term + CS spread) reads daily

SPACE = {
    # champion keys (pinned, docs only)
    "b_hi": [0.69], "b_lo": [0.45], "b_mid": [0.55], "floor_lb": [19],
    "lookback": [12], "max_dist": [0.055], "regime_ma": [18], "fast_ma": [5],
    "sustain_lo": [3], "sustain_hi": [2], "tier_lo": [0.9999],
    "tier_mid": [0.9999], "cap_weak": [11], "cap_full": [20], "gf_lb": [12],
    "gf_w": [0.0], "gw_w": [0.15], "ids_lb": [3], "ids_w": [-0.13],
    "la_min": [0], "la_w": [0.5], "or_lb": [6], "or_w": [-0.1],
    "sp_lb": [4], "sp_w": [-0.05, 0.0],  # 0.0 = the control cell only
    "sp_frac": [0.5],
    # this file's keys
    "sc_lb": [4, 12],
    "sc_w": [0.05, -0.05],
}


def _level_series(SPR: np.ndarray, slb: int, need: int) -> np.ndarray:
    """L[t] = nanmean(SPR[t-slb:t]) over buckets with >= need finite entries —
    the SAME trailing-mean level series the champion's level term ranks on
    (strat_l20b_spread score(), re-expressed here as a series so it can be
    differenced; NaN where the window is thin)."""
    L = np.full(SPR.shape, np.nan)
    for t in range(slb, SPR.shape[0]):
        win = SPR[t - slb : t]
        cnt = np.isfinite(win).sum(axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            m = np.nanmean(win, axis=0)
        L[t] = np.where(cnt >= need, m, np.nan)
    return L


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-13/14 imported-default lesson):
    # this file's own key defaults to the off-switch; the champion's sp keys
    # are pinned to their champion dose so the composed base IS the champion
    # even if the caller omits them (a PASSED key — e.g. the control cell's
    # sp_w 0.0 — always wins over setdefault).
    p.setdefault("sc_w", 0.0)
    p.setdefault("sc_lb", 4)
    p.setdefault("sp_lb", 4)
    p.setdefault("sp_w", -0.05)
    p.setdefault("sp_frac", 0.5)
    out, regime = _l20(panels, p)  # current champion chain + level, verbatim
    out = np.array(out, dtype=float, copy=True)

    sc_w = float(p["sc_w"])
    if sc_w == 0.0:
        return out, regime  # off-switch: bitwise copy of the champion

    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    slb = int(p["sp_lb"])
    sc_lb = int(p["sc_lb"])
    need = max(2, int(np.ceil(float(p["sp_frac"]) * slb)))
    SPR = _monthly_spread(daily, months, cols)  # imported estimator
    L = _level_series(SPR, slb, need)
    for t in range(slb + sc_lb, out.shape[0]):
        cur, old = L[t], L[t - sc_lb]  # both windows end strictly before t
        delta = cur - old
        valid = np.isfinite(cur) & np.isfinite(old)
        n = int(valid.sum())
        tilt = np.ones(out.shape[1])
        if n >= 5:
            dv = delta[valid]
            order = np.argsort(dv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt[valid] = 1.0 + sc_w * (2.0 * pct - 1.0)
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt, np.nan)
    return out, regime
