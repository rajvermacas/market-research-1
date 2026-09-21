"""Candidate: listing-age + cross-sectional-outrank DOUBLE tilt on the
champion book (strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l15b_insideday (floor-lift
fresh-print rank among short-trend-passing, print-continuity-passing names,
breadth-tier exposure with tier 0.9999, eligibility-wobble gw_w 0.15,
inside-day tilt ids_w -0.13 / ids_lb 3, regime-conditional cap cap_weak/
cap_full) — is composed here exactly as strat_l17c_listage composes it:
strat_l12b_gatefail.score is called with gatefail's own leakable defaults
NEUTRALISED before delegating (gf_lb 12 / gf_w 0.0 / gw_w 0.0 via setdefault;
the champion's gw_w 0.15 is PASSED by the caller so the wobble tilt fires
inside the delegate — Loop-14 lesson), the inside-day tilt is re-expressed on
the returned lift using _monthly_inside imported from strat_l15b_insideday
(same loop, same percentile math as that file's score()), and the
regime-conditional cap is mirrored inline (above the tilt: identical to the cap step in
strat_l15b_insideday / strat_l13a_concwobble / strat_l17c_listage). ORDERING:
the ids tilt lands PRE-cap (the mirrored cap runs right after it); the
listing-age and outrank tilts land POST-cap — strat_l17c_listage tilts the
capped pool returned by _ids_score (its own trailing cap is then a no-op) and
strat_l16b_outrank tilts the capped pool returned by _ids_score outright, so
faithfulness to BOTH sources requires: ids tilt -> cap -> age tilt -> outrank
tilt (-> final no-op cap pass). Between the cap and the final pass, TWO
per-name tilts are applied in sequence:

  (a) LISTING-AGE tilt, re-expressed from strat_l17c_listage.score (source:
      tilt[j] = 1 + la_w * (2 * pct[j] - 1), pct = cross-sectional percentile
      of listing age among names with a known listing_date; age_ref = days
      from listing_date to months[-1] / 365.25, clipped at 0; applied to rows
      t >= 1; NaN lift stays NaN; la_min age gate retained but PINNED 0):

      age_ref[j] = max(0, (months[-1] - listing_date_j).days) / 365.25
      pct[j]     = cross-sectional percentile of age_ref (known dates only)
      tilt_a[j]  = 1 + la_w * (2 * pct[j] - 1)   # la_w > 0 favours OLD
      out[t]     = ids-tilted lift[t] * tilt_a   # t >= 1

      Because every name ages one year per year, the percentile ORDER of
      listing age is static across rows — tilt_a is a fixed per-name
      handicap, not a time-varying signal. listing_date is a static ex-ante
      attribute (0 nulls on all 2,559 universe symbols — coverage verified in
      strat_l17c_listage before the mechanism was built), so the tilt is
      PIT-clean by construction.

  (b) CROSS-SECTIONAL OUTRANK tilt, re-expressed from strat_l16b_outrank.score
      (source: for month t and window or_lb months, ret_j(t) = px[t,j] /
      px[t-or_lb,j] - 1; pct_j(t) = cross-sectional percentile of ret among
      names with a finite ret; tilt = 1 + or_w * (2 * pct - 1); NaN entries
      keep tilt 1.0; rows with t < or_lb untouched):

      ret_j(t)          = px[t, j] / px[t - or_lb, j] - 1
      pct_j(t)          = percentile of ret_j(t) among finite rets in row t
      tilt_b[j]         = 1 + or_w * (2 * pct_j(t) - 1)  # or_w < 0 favours
                          panel laggards over the trailing window
      out[t]            = out[t] * tilt_b                # NaN stays NaN

or_lb is PINNED at 6 — the Loop-18 consistency-improving outrank window
(or_lb 6 / or_w -0.15: train +94.16% / DD -16.53%, the only outrank row that
IMPROVED drawdown on the -17.03% base; the or_lb 12 variant was also verified
bit-faithful: 95.116 / -17.046, the l16_dB ledger row). Both tilts are
strictly positive (|w| < 1)
multiplicative re-weightings of the SAME imported lift — no new eligibility,
no new indicator, no second copy of any tested term; each formula is cited
above from its tested source file.

Hypothesis (Loop-19 BALANCED sprint): the loop's ruler is Calmar with a
consistency guard (worst complete calendar year >= -15%). Loop-18 found the
two most consistency-improving per-name tilts on this champion chain: the
listing-age tilt (favours OLD, long-listed, institutionally sponsored names —
fewer young-listing blowups in the tail) and the cross-sectional outrank tilt
(favours panel LAGGARDS over the trailing 12m — printers breaking out of a
base the market has not yet chased, rather than crowded extended leaders).
Each was screened ALONE and trailed the champion on train CAGR while holding
or improving drawdown. This file tests whether they COMPOSE: the two tilts
act on different axes of the same book (a static board attribute vs the
panel's trailing-return cross-section), so their drawdown reductions have a
chance of stacking while the train cost compounds sub-additively. If the
combined tilt lands below the flat base on BOTH train CAGR and Calmar, the
two mechanisms interact destructively on the same top-15 cut and the balanced
composition closes.

Falsifier: if every tested (la_w, or_w) combination in the SPACE below trails
the flat base — train +96.882% / DD -17.032% / calmar 5.688 / fwd +48.973% /
fwd DD -12.311% / fwd bench +14.717% — on BOTH windows, then the two
consistency tilts do not compose on this champion chain and the balanced
double-tilt axis closes at this base. (Per the Loop-17 lesson, a train gain
paid for with wider DD or forward collapse is an artifact, not an upgrade:
Calmar and the forward window are checked before any keep.)

Import chain: strat_l19a_balanced -> strat_l12b_gatefail.score (which imports
strat_floorhighfastgate + strat_floorhighsustaincond + strat_floorhightiershape
for the gate layers and rank/exposure, and applies the wobble tilt) ->
strat_l15b_insideday (ids tilt re-expressed on the gatefail lift) -> mirrored
cap (pre-tilt; the sources tilt the capped pool) -> listing-age tilt
re-expressed from strat_l17c_listage.score (post-cap, as in its source) ->
outrank tilt re-expressed from strat_l16b_outrank.score (post-cap, as in its
source) -> final no-op cap pass.

PIT argument: the listing-age tilt reads only the static universe
`listing_date` (known before a name can be traded) and multiplies rows
t >= 1, which the harness reads only from start_i. The outrank tilt at row t
reads px[t] and px[t - or_lb] only — month-end closes at or before the
decision month's own month-end; the percentile at row t uses only that same
row's cross-section; rows with t < or_lb keep tilt exactly 1.0. The ids tilt
reads only daily bars strictly before months[t] (bucket t-1 and older), as
verified in strat_l15b_insideday. The cap reads month-t ranks only. No row
>t is touched anywhere.

Off-switch identity: la_w = 0.0 (with la_min 0) skips tilt_a entirely and
or_w = 0.0 skips tilt_b entirely, so `out` is bitwise the ids-tilted gatefail
lift and the mirrored cap yields bitwise the champion's scores at the same
params. Champion keys are PASSED by the caller, never defaulted here (the
delegate's gf_w 0.05 leak is neutralised by setdefault before delegating,
exactly as strat_l15b_insideday / strat_l16b_outrank / strat_l17c_listage do).

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: this file introduces NO new signal. It is a pure
composition of two independently screened, documented tilts — the listing-age
percentile (strat_l17c_listage, Loop-17 attributes family) and the
cross-sectional trailing-rank percentile (strat_l16b_outrank, Loop-16
mechanism screens) — onto the current champion chain, in the order
ids -> age -> outrank -> cap. Neither prior file measured the other's tilt
present; the only new question is whether the two consistency tilts stack.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key passed via params-json, not consumed
        here)
        + or_lb [12] (pinned: the champion lookback window)
        + la_w {0.2, 0.3, 0.4} (listing-age percentile tilt; positive favours
          OLD listings; 0.0 = off)
        + or_w {-0.1, -0.15, -0.2} (outrank percentile tilt; negative favours
          panel laggards; 0.0 = off)
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside

NEEDS_DAILY = True  # the delegate's ids term reads the daily panel (ids_w -0.13)

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
    "or_lb": [6],
    "la_w": [0.2, 0.3, 0.4],
    "or_w": [-0.1, -0.15, -0.2],
}

_UNI_CACHE: dict = {}


def _listing_dates() -> dict:
    """symbol -> listing_date from the universe snapshot (static ex-ante
    attribute; coverage 0 nulls / 2,559 verified in strat_l17c_listage)."""
    if "ld" not in _UNI_CACHE:
        root = Path(__file__).resolve().parents[1]
        u = pl.read_parquet(root / "data" / "universe" / "nse_universe.parquet")
        _UNI_CACHE["ld"] = dict(zip(u["symbol"].to_list(), u["listing_date"].to_list()))
    return _UNI_CACHE["ld"]


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (gatefail's own gf_w 0.05 default
    # would leak — Loop-14 lesson); the champion's gw_w 0.15 / ids_w -0.13
    # / ids_lb 3 must be PASSED by the caller.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, exposure = _gf_score(panels, p)  # champion lift (wobble tilt inside)
    out = np.array(lift, dtype=float, copy=True)

    # ---- ids tilt, re-expressed from strat_l15b_insideday.score (its inline
    # loop: tilt = 1 + ids_w * (2 * pct - 1) on the trailing ids_lb monthly
    # inside-day shares, percentile-ranked among finite shares) ----
    ids_w = float(params.get("ids_w", 0.0))
    if ids_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        ilb = int(params.get("ids_lb", 3))
        IDS = _monthly_inside(daily, months, cols)
        for t in range(1, out.shape[0]):
            lo = t - ilb
            if lo < 0:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                share = np.nanmean(IDS[lo:t], axis=0)
            valid = np.isfinite(share)
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = share[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + ids_w * (2.0 * pct - 1.0)
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt, np.nan)

    # cap step mirrored inline from strat_floorhightiershapeconc.score /
    # strat_l13a_concwobble.score / strat_l15b_insideday.score (book-size
    # composition, not an indicator): cap = cap_full where exposure >= 1.0
    # else cap_weak; lower ranks set NaN after a stable descending sort.
    # POSITION: strat_l17c_listage and strat_l16b_outrank both apply their
    # tilt to the POST-cap champion pool (_ids_score returns capped scores;
    # listage's trailing cap and outrank's absent cap are no-ops on the
    # strictly-positive-tilted finite set), so the cap sits HERE — between
    # the ids tilt and the two tilts — for the composition to be faithful.
    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    E = np.asarray(exposure, dtype=float)

    def _cap(scores: np.ndarray) -> np.ndarray:
        for t in range(scores.shape[0]):
            r = scores[t]
            fin = np.flatnonzero(np.isfinite(r))
            if fin.size == 0:
                continue
            cap = cf if E[t] >= 1.0 else cw
            if fin.size <= cap:
                continue
            order = fin[np.argsort(-r[fin], kind="stable")]
            scores[t, order[cap:]] = np.nan
        return scores

    out = _cap(out)

    # ---- (a) listing-age tilt, re-expressed from strat_l17c_listage.score
    # (source formula, cited in the docstring above:
    #   age_ref = max(0, (months[-1] - listing_date).days) / 365.25;
    #   tilt_a = 1 + la_w * (2 * pct - 1), pct = cross-sectional percentile
    #   of age_ref among names with a known listing date; rows t >= 1) ----
    la_w = float(params.get("la_w", 0.0))
    la_min = float(params.get("la_min", 0.0) or 0.0)  # retained, PINNED 0
    if la_w != 0.0 or la_min > 0.0:
        ld = _listing_dates()
        months, cols = panels["months"], panels["cols"]
        # static age percentile (order is row-independent; reference date is
        # the last month, negatives clipped at 0 — order unchanged)
        age_ref = np.full(len(cols), np.nan)
        for j, s in enumerate(cols):
            d0 = ld.get(s)
            if d0 is not None:
                age_ref[j] = max(0, (months[-1] - d0).days) / 365.25
        tilt_a = np.ones(len(cols))
        valid = np.flatnonzero(np.isfinite(age_ref))
        if valid.size >= 5:
            order = valid[np.argsort(age_ref[valid], kind="stable")]
            pct = np.empty(valid.size)
            pct[order] = np.arange(valid.size) / (valid.size - 1)
            tilt_a[valid] = 1.0 + la_w * (2.0 * pct - 1.0)
        for t in range(1, out.shape[0]):
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt_a, np.nan)
            if la_min > 0.0:
                d0s = np.array([ld.get(s) for s in cols], dtype=object)
                young = np.array(
                    [d is None or (months[t] - d).days < la_min * 365.25 for d in d0s])
                out[t] = np.where(ok & ~young, out[t], np.nan)

    # final no-op cap pass (strat_l17c_listage re-runs the mirrored cap after
    # its tilt; on the strictly positive tilt_a it removes nothing — kept so
    # the structure matches the source chain end-to-end)

    # ---- (b) cross-sectional outrank tilt, re-expressed from
    # strat_l16b_outrank.score (source formula, cited in the docstring above:
    #   ret_j(t) = px[t,j] / px[t-or_lb,j] - 1; tilt_b = 1 + or_w * (2*pct-1),
    #   pct = cross-sectional percentile of ret among finite rets in row t;
    #   rows with t < or_lb untouched) ----
    or_w = float(params.get("or_w", 0.0))
    if or_w != 0.0:
        px = panels["px"]
        olb = int(params.get("or_lb", 6))
        for t in range(olb, out.shape[0]):
            with np.errstate(invalid="ignore"):
                ret = px[t] / px[t - olb] - 1.0
            valid = np.isfinite(ret)
            n = int(valid.sum())
            if n < 5:
                continue
            rv = ret[valid]
            order = np.argsort(rv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt_b = np.ones(out.shape[1])
            tilt_b[valid] = 1.0 + or_w * (2.0 * pct - 1.0)
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt_b, np.nan)

    return _cap(out), E
