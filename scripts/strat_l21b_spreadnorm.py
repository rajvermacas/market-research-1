"""Candidate: spread-CHANGE normalised by the name's OWN spread level
(relative change) or as the change's own-history percentile — the robustness
sibling of strat_l21b_spreadchg (strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l20b_spread (strat_l19a_balanced
gatefail lift -> ids tilt -> cap -> age tilt -> outrank tilt -> cap, then the
Corwin-Schultz spread-LEVEL cross-sectional percentile tilt at sp_lb 4 /
sp_w -0.05 / sp_frac 0.5) is composed VERBATIM via
`from strat_l20b_spread import score as _l20` with the champion's sp keys
PINNED underneath (setdefault to 4 / -0.05 / 0.5; a caller PASSING sp_w 0.0 —
the control cell — wins, setdefault never overrides). On top of the champion's
returned scores this file applies ONE new term: a cross-sectional percentile
tilt on the spread CHANGE from strat_l21b_spreadchg, but in a NORMALISED form
so that the change is scale-free across names.

Level series (same estimator and window as the champion's level term):

    L[t, j] = nanmean(SPR[t-sp_lb : t, j]) over buckets with count >=
              ceil(sp_frac * sp_lb)          # the champion's level series
    delta[t, j] = L[t, j] - L[t - sn_lb, j]  # the ABSOLUTE change that
                # strat_l21b_spreadchg ranks (its winning cell: sn_lb 12,
                # weight -0.05 — confirmed by this loop's live deepening
                # grid in .cache/strategy_lab/l21_orch_results.tsv)

Two normalisations of that change (sn_mode), both FIRST-CLASS:

  "rel" (default) — change relative to the name's OWN prior level:
      score[t, j] = delta[t, j] / L[t - sn_lb, j]
      # requires L[t - sn_lb, j] > 0 (a zero prior level earns no score:
      # tilt 1.0, never a division artefact). A 0.20-wide name narrowing by
      # 0.02 (10%) now ranks like a 0.02-wide name narrowing by 0.002 (10%) —
      # exactly the comparability the absolute difference lacks, because the
      # cross-sectional percentile of raw deltas is dominated by the WIDEST
      # names' absolute wiggle.
  "pct" — the change's OWN-HISTORY percentile (is this month's narrowing
      unusually strong for THIS NAME'S usual wiggle?):
      hist = { delta[k, j] : k in [t - sn_plb, t - 1], finite }
      score[t, j] = (#hist < delta[t] + 0.5 * #hist == delta[t]) / n
      # requires >= max(3, ceil(0.5 * sn_plb)) finite own-history deltas

score is then percentile-ranked CROSS-SECTIONALLY among names with a finite
score (n >= 5) and applied as:

    tilt[t] = 1 + sn_w * (2 * pct - 1)     # pct in [0,1], |sn_w| < 1
    out[t]  = out[t] * tilt                # finite entries only, NaN stays NaN

Rows t < sp_lb + sn_lb (+ sn_plb in "pct" mode) are untouched; names failing
coverage keep tilt exactly 1.0 (re-ranking, never a gate); NaN stays NaN;
|sn_w| < 1 keeps the multiplier strictly positive. Both signs first-class:
sn_w < 0 favours names whose spread is narrowing RELATIVE to their own level
(or unusually strongly by their own standard), sn_w > 0 favours names widening
on the same normalised footing.

Hypothesis: strat_l21b_spreadchg showed the ABSOLUTE first difference of the
trailing mean spread can add to the champion (its (12, -0.05) cell: train
103.848 / DD -14.883 / calmar 6.978 vs the champion 102.990 / -15.506 /
6.642, smoke ledger l21dB; live-deepened in l21_orch). But a raw delta's
cross-sectional percentile is scale-contaminated: wide-spread names move in
bigger absolute increments for purely arithmetic reasons, so the absolute
change term partly re-ranks on LEVEL — information the champion's level tilt
already carries. This file asks whether the same change signal survives (or
strengthens) once normalised: if "rel" and "pct" both beat the champion while
their absolute-difference parent also does, the change term carries its own
information; if only the absolute form works, the gain was partly a level
disguise; if both normalised forms trail, the relative change is noise around
the champion. Every active cell keeps BOTH terms (champion level underneath),
and the sp_w 0.0 control cell shows the normalised change alone.

Falsifier: if ALL four active SPACE cells trail the flat base — train
+102.990% / DD -15.506% / ret-DD 6.642 / fwd +54.057% / fwd DD -10.381% —
on train CAGR with no offsetting improvement in drawdown or forward
(operationally: the harness keep rule never fires on the smoke ledger; per
the Loop-17 rule a train gain bought with wider DD or a forward collapse is an
ARTIFACT), then the scale-normalised change adds nothing and the change
finding (if any) is confined to the absolute form in strat_l21b_spreadchg.
Before ANY promotion: this tilt re-orders the capped pool (book-composition)
— count the decision months where picks differ from the champion's
(Loop-16 lesson).

NOVELTY STATEMENT (closest registry rows -> the ONE thing that changed):
- strat_l21b_spreadchg (delivered by this designer earlier in Loop-21; its
  registry row is appended at close-out) — the CLOSEST prior art and this
  file's own idea-parent: the ABSOLUTE first difference of the champion's
  trailing mean spread. ONE THING CHANGED: absolute difference -> the SAME
  difference normalised by the name's own prior spread LEVEL ("rel") or
  ranked against the name's own history of differences ("pct") — a scale-free
  statistic instead of a scale-contaminated one. Not a re-weight: the
  resulting cross-section differs whenever absolute wiggle size and relative
  wiggle strength disagree across names.
- research/tested_mechanisms.tsv line 146 strat_l20b_spread — the base's own
  level term (PROMOTED champion): ranks WHERE a name's spread sits, never a
  change and never scale-normalised.
- research/tested_mechanisms.tsv line 107 strat_l15b_rngcomp (self-normalised
  range ratio vs own history, DEAD on the ids base) and line 112
  strat_l16a_idsrng (its retest, DEAD) — the nearest SELF-NORMALISATION
  precedent: same FORM class (a quantity divided by / ranked within its own
  reference), different SIGNAL (intraday range, a volatility proxy) and a
  base that predates the spread channel. A relative change of a COST level is
  not a range ratio.
- research/tested_mechanisms.tsv line 124 strat_l17b_corrtrend (DEAD) — a
  temporal change of a different quantity (correlation), never normalised,
  never on this base.

Import chain: strat_l21b_spreadnorm -> strat_l20b_spread.score (the CURRENT
champion) -> strat_l19a_balanced -> strat_l12b_gatefail +
strat_l15b_insideday. The level series L is built exactly as in
strat_l21b_spreadchg (same formula, same coverage guard); the CS estimator is
imported from strat_l20b_spread (`_monthly_spread`), never copied.

PIT argument: bucket k of _monthly_spread contains only pairs whose CARRYING
(second) bar falls in [months[k], months[k+1]); L[t] reads buckets
[t-sp_lb, t-1] and L[t-sn_lb] reads buckets [t-sn_lb-sp_lb, t-sn_lb-1] —
both windows end strictly before months[t]. In "pct" mode the own history
reads delta rows [t - sn_plb, t - 1], each of which uses only buckets before
its own month — strictly prior information. The percentile at row t uses only
that row's cross-section; rows t < sp_lb + sn_lb (+ sn_plb) are untouched;
no row > t is read anywhere. The delegate's PIT is unchanged from
strat_l20b_spread.

Off-switch identity: sn_w = 0.0 (this file's OWN setdefault, applied to the
params copy BEFORE delegating — Loop-13/14 imported-default lesson) skips the
normalised-change block entirely and returns the delegate's scores untouched,
so `out` is bitwise strat_l20b_spread's returned scores at the PASSED keys —
with the sp keys pinned to the champion dose above, that is the champion
bit-exactly. Champion keys are ALWAYS PASSED by the caller, never defaulted
here: the delegate's parents read la_w/or_w/gw_w/ids_w via .get with 0.0
defaults, so a missing key would silently de-tune the base.

Flat-base metric (off-switch must reproduce exactly): train +102.990% /
DD -15.506% / ret-DD 6.642 / H1 +100.204% / H2 +105.682% / fwd +54.057% /
fwd DD -10.381% / full +82.001% / full DD -20.728%.

Keys consumed: this file reads sn_w, sn_lb, sn_mode, sn_plb, and (for the
level series) sp_lb, sp_frac — the sp keys pinned via setdefault. Everything
else in params-json flows through to the delegate (all SPACE champion keys
incl. sp_w, which the control cell sets to 0.0) or is read by the harness
(max_hold 3).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1, sp_lb 4, sp_w -0.05,
        sp_frac 0.5; max_hold 3 is a HARNESS key passed via params-json)
        + FOUR documented cells, one literal trial each (smoke = all four;
          both signs and the both-terms-active requirement from the brief
          are covered by cells 2-4, every one of them with the champion
          level term active underneath):
          1. OFF-SWITCH identity: canonical champion JSON (sn_w absent ->
             0.0) — must reproduce the flat-base metric bit-exactly
          2. BOTH terms active:  sn_lb 12, sn_mode "rel", sn_w -0.05
             (the winning parent cell's lag and sign, scale-normalised)
          3. BOTH terms active:  sn_lb 12, sn_mode "rel", sn_w +0.05 (other
             sign on the normalised footing)
          4. BOTH terms active:  sn_lb 12, sn_mode "pct", sn_w -0.05
             (own-history percentile of the change — second normalisation)
        + sn_lb [12] pinned (the lag that leads this loop's deepening grid;
          strat_l21b_spreadchg documents the 4-vs-12 contrast)
        + sn_plb [24] pinned ("pct" mode: own history of deltas)
        + sn_frac not a key — coverage inherits the champion's sp_frac guard
          on L and the own-history guards stated above.
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
    "sn_lb": [12],
    "sn_mode": ["rel", "pct"],
    "sn_plb": [24],
    "sn_w": [0.05, -0.05],
}


def _level_series(SPR: np.ndarray, slb: int, need: int) -> np.ndarray:
    """L[t] = nanmean(SPR[t-slb:t]) over buckets with >= need finite entries —
    the SAME trailing-mean level series the champion's level term ranks on
    (formula identical to strat_l21b_spreadchg._level_series; NaN where the
    window is thin)."""
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
    # this file's own keys default to the off-switch / pinned values; the
    # champion's sp keys are pinned to their champion dose so the composed
    # base IS the champion even if the caller omits them (a PASSED key —
    # e.g. the control cell's sp_w 0.0 — always wins over setdefault).
    p.setdefault("sn_w", 0.0)
    p.setdefault("sn_lb", 12)
    p.setdefault("sn_mode", "rel")
    p.setdefault("sn_plb", 24)
    p.setdefault("sp_lb", 4)
    p.setdefault("sp_w", -0.05)
    p.setdefault("sp_frac", 0.5)
    out, regime = _l20(panels, p)  # current champion chain + level, verbatim
    out = np.array(out, dtype=float, copy=True)

    sn_w = float(p["sn_w"])
    if sn_w == 0.0:
        return out, regime  # off-switch: bitwise copy of the champion

    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    slb = int(p["sp_lb"])
    snlb = int(p["sn_lb"])
    mode = str(p["sn_mode"])
    if mode not in ("rel", "pct"):
        raise ValueError(f"sn_mode must be 'rel' or 'pct', got {mode!r}")
    plb = int(p["sn_plb"])
    need_win = max(2, int(np.ceil(float(p["sp_frac"]) * slb)))
    need_own = max(3, int(np.ceil(0.5 * plb)))  # pct mode coverage
    SPR = _monthly_spread(daily, months, cols)  # imported estimator
    L = _level_series(SPR, slb, need_win)
    # the absolute change series (the strat_l21b_spreadchg input), materialised
    # once so both normalisations read the same delta
    D = np.full(L.shape, np.nan)
    D[snlb:] = L[snlb:] - L[:-snlb]  # NaN propagates from either endpoint
    start = slb + snlb + (plb if mode == "pct" else 0)
    for t in range(start, out.shape[0]):
        if mode == "rel":
            prior = L[t - snlb]
            cur_d = D[t]
            valid = np.isfinite(cur_d) & np.isfinite(prior) & (prior > 0.0)
            score_x = np.where(valid, cur_d / np.where(valid, prior, 1.0), np.nan)
        else:  # pct: own-history percentile of the change
            cur_d = D[t]
            hist_all = D[t - plb : t]  # strictly PRIOR change rows
            score_x = np.full(out.shape[1], np.nan)
            for j in range(out.shape[1]):
                dj = cur_d[j]
                if not np.isfinite(dj):
                    continue
                h = hist_all[:, j]
                h = h[np.isfinite(h)]
                if h.size < need_own:
                    continue
                lt = int(np.count_nonzero(h < dj))
                eq = int(np.count_nonzero(h == dj))
                score_x[j] = (lt + 0.5 * eq) / h.size
        valid = np.isfinite(score_x)
        n = int(valid.sum())
        tilt = np.ones(out.shape[1])
        if n >= 5:
            sv = score_x[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt[valid] = 1.0 + sn_w * (2.0 * pct - 1.0)
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt, np.nan)
    return out, regime
