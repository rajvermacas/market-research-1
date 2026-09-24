"""Candidate: spread-INSTABILITY (dispersion/stdev of the monthly spread over
the trailing window) percentile tilt, champion level term kept underneath.

Setup in words: the CURRENT champion chain — strat_l20b_spread (strat_l19a_balanced
gatefail lift -> ids tilt -> cap -> age tilt -> outrank tilt -> cap, then the
Corwin-Schultz spread-LEVEL cross-sectional percentile tilt at sp_lb 4 /
sp_w -0.05 / sp_frac 0.5) is composed VERBATIM via
`from strat_l20b_spread import score as _l20` with the champion's sp keys
PINNED underneath (setdefault to 4 / -0.05 / 0.5; a caller PASSING sp_w 0.0 —
the control cell — wins, setdefault never overrides). On top of the champion's
returned scores this file applies ONE new term: a cross-sectional percentile
tilt on the SECOND MOMENT of the same monthly spread series — its dispersion
(standard deviation) over the trailing sv_lb-month window, i.e. how UNSTABLE
a name's trading cost has been, independent of how wide it has been on
average:

    SPR[t, j]  = _monthly_spread (strat_l20b_spread) monthly CS spread
                 buckets — used when sv_est = "cs" (default)
    DISP[t, j] = nanstd(SPR[t - sv_lb : t, j], ddof 0) over buckets with
                 count >= ceil(sv_frac * sv_lb)     # THE DISPERSION
                 # a value of 0.0 (perfectly stable spread) is legitimate,
                 # not missing; only a thin window is NaN

sv_est = "roll" swaps the INPUT series for a Roll (1984) implied-spread panel
built below (robustness cell INSIDE this file, per the brief — it is never its
own file): per (month, name), over pairs of consecutive daily RELATIVE price
changes r_t = close_t/close_{t-1} - 1 and r_{t-1} whose three bars are each
1-7 calendar days apart (the same session-drop guard the CS estimator uses),

    cov = mean(r_t * r_{t-1}) - mean(r_t) * mean(r_{t-1})   # within bucket
    S_roll = 2 * sqrt(max(0, -cov))                         # relative units
    # cov >= 0 (out of the bid-ask-bounce model) floors to 0, mirroring the
    # CS floor-at-zero convention; buckets with < sv_rollmin (10) valid pairs
    # are NaN (a covariance needs mass — ~20 pairs/month exist at most)

Roll's estimate is in PRICE-fraction units (relative spread) rather than CS's
log-range units; the consumer is a cross-sectional PERCENTILE of a DISPERSION,
which is rank-based and unit-agnostic in level, so the swap tests estimator
dependence, not scale. Dispersion is then percentile-ranked cross-sectionally
among names with a finite value (n >= 5) and applied as:

    tilt[t] = 1 + sv_w * (2 * pct - 1)    # pct in [0,1], |sv_w| < 1
    out[t]  = out[t] * tilt               # finite entries only, NaN stays NaN

Rows t < sv_lb are untouched; names failing the coverage guard keep tilt
exactly 1.0 (re-ranking, never a gate); NaN stays NaN; |sv_w| < 1 keeps the
multiplier strictly positive. Both signs are first-class: sv_w < 0 favours
STABLE-spread names (execution risk low and PREDICTABLE — the book can enter
and exit without the cost regime shifting under it), sv_w > 0 favours
UNSTABLE-spread names (the risk-premium story: holders of erratic-cost names
are compensated for bearing the uncertainty).

Hypothesis: the champion ranks spread LEVEL — the first moment, where a name's
cost sits on average. Execution risk, however, is about the second moment: two
names can average the same spread while one is rock-stable and the other
oscillates between cheap and untradeable. If cost LEVEL is all the book needs,
the dispersion term adds nothing once the level term is present (the
BOTH-terms-active cells), and if dispersion only matters through its level
correlation, the control cell (level OFF) will show it alone while the stacked
cells show no gain beyond the champion. If every active cell trails the flat
base, spread INSTABILITY adds nothing beyond the level and the axis closes.

Falsifier: if ALL five SPACE cells trail the flat base — train +102.990% /
DD -15.506% / ret-DD 6.642 / fwd +54.057% / fwd DD -10.381% — on train CAGR
with no offsetting improvement in drawdown or forward (operationally: the
harness keep rule never fires on the smoke ledger; per the Loop-17 rule a
train gain bought with wider DD or a forward collapse is an ARTIFACT), then
the spread-dispersion axis closes on the champion base. A finding even if the
Roll-robustness cell alone survives: that would indict the CS estimator's
temporal shape rather than the dispersion idea. Before ANY promotion: this
tilt re-orders the capped pool (a book-composition mechanism) — count the
decision months where its picks differ from the champion's (Loop-16 lesson;
the champion level term's footprint was 23/139).

NOVELTY STATEMENT (closest registry rows -> the ONE thing that changed):
- research/tested_mechanisms.tsv line 146 strat_l20b_spread — the CLOSEST
  prior art and this file's own base: Corwin-Schultz spread LEVEL, the FIRST
  moment ranked cross-sectionally, PROMOTED champion. ONE THING CHANGED:
  first moment (level) -> SECOND MOMENT (within-window standard deviation /
  instability) of the same spread series. Same estimator, same tilt
  machinery; a dispersion is invariant to where the level sits, so the
  cross-sectional order differs by construction.
- research/tested_mechanisms.tsv line 149 strat_l20c_capconc — the registry's
  only other dispersion-based mechanism (stdev of the pre-cap SCORES to set
  the cap level, DEAD 64.08-98.68): a different quantity entirely (score
  dispersion as book-size information, not cost dispersion as a per-name
  rank), never a spread statistic.
- research/tested_mechanisms.tsv lines 6/96 (strat_concvolgate,
  strat_l14a_volrank — vol-LEVEL, DEAD) — dispersion of SPREAD is not
  volatility level: spread dispersion measures the stability of a
  microstructure cost, while those rows scaled exposure/rank by return
  volatility (symmetric risk). The CS floor/gap conventions and the
  level-vs-risk distinction argued in strat_l20b_spread's docstring carry
  over unchanged.
- research/tested_mechanisms.tsv line 107 strat_l15b_rngcomp (self-normalised
  range vs own history, DEAD on ids base): a level of a volatility proxy
  normalised against itself — not a second moment of a cost, not this base.
- The Roll (1984) estimator appears for the FIRST time in this repo (no
  registry row implements Roll or Abdi-Ranaldo); per the brief it lives only
  as the robustness cell inside this file, never as its own file.

Import chain: strat_l21b_spreadvol -> strat_l20b_spread.score (the CURRENT
champion: CS level tilt on the l19 chain) -> strat_l19a_balanced ->
strat_l12b_gatefail + strat_l15b_insideday. This file adds only the
post-chain dispersion tilt; the CS estimator is imported from
strat_l20b_spread (`_monthly_spread`), never copied. The Roll panel and the
bucket->month->matrix mapping block below are the only new computation; the
mapping glue is copied verbatim from strat_l20b_spread._monthly_spread (it is
pivot plumbing, not an indicator) and the estimator itself is new.

PIT argument: bucket k of _monthly_spread / _monthly_roll contains only pairs
whose CARRYING bar falls in [months[k], months[k+1]) (CS: the pair's second
daily bar; Roll: the r_t bar whose lag reaches back one more session). DISP[t]
reads buckets [t - sv_lb, t - 1], whose bars all have date < months[t]. The
percentile at row t uses only that row's backward cross-section; rows
t < sv_lb are untouched; no row > t is read anywhere. The delegate's PIT is
unchanged from strat_l20b_spread (ids: daily bars strictly before months[t];
age: static listing_date; outrank: px[t-or_lb]..px[t]; cap: month-t ranks;
level: buckets t-4..t-1).

Off-switch identity: sv_w = 0.0 (this file's OWN setdefault, applied to the
params copy BEFORE delegating — Loop-13/14 imported-default lesson) skips the
dispersion block entirely and returns the delegate's scores untouched, so
`out` is bitwise strat_l20b_spread's returned scores at the PASSED keys —
with the sp keys pinned to the champion dose above, that is the champion
bit-exactly. Champion keys are ALWAYS PASSED by the caller, never defaulted
here: the delegate's parents read la_w/or_w/gw_w/ids_w via .get with 0.0
defaults, so a missing key would silently de-tune the base.

Flat-base metric (off-switch must reproduce exactly): train +102.990% /
DD -15.506% / ret-DD 6.642 / H1 +100.204% / H2 +105.682% / fwd +54.057% /
fwd DD -10.381% / full +82.001% / full DD -20.728%.

Keys consumed: this file reads sv_w, sv_lb, sv_frac, sv_est, sv_rollmin, and
(only when sv_est = "roll" for its own coverage) nothing of the champion's;
the champion's sp keys are pinned via setdefault but only consumed by the
delegate. Everything else in params-json flows through to the delegate (all
SPACE champion keys incl. sp_w, which the control cell sets to 0.0) or is
read by the harness (max_hold 3).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1, sp_lb 4, sp_w -0.05,
        sp_frac 0.5; max_hold 3 is a HARNESS key passed via params-json)
        + FIVE documented cells, one literal trial each (smoke = all five):
          1. OFF-SWITCH identity: canonical champion JSON (sv_w absent ->
             0.0) — must reproduce the flat-base metric bit-exactly
          2. BOTH terms active:  sv_lb 6, sv_est "cs", sv_w -0.05
             (stable-spread names favoured, level term still on)
          3. BOTH terms active:  sv_lb 6, sv_est "cs", sv_w +0.05 (other
             sign: unstable-spread names favoured)
          4. BOTH terms active + ROBUSTNESS: sv_lb 6, sv_est "roll",
             sv_w -0.05 — the dispersion of a Roll (1984) implied-spread
             panel instead of the CS one; estimator-dependence check
          5. CONTROL (dispersion alone): sv_lb 6, sv_est "cs", sv_w -0.05,
             sp_w 0.0 — the champion level term OFF
        + sv_lb [6] pinned in the smoke (dispersion of a half-year of
          monthly buckets); sv_lb 12 is the documented depth axis for a
          follow-up pass
        + sv_frac [0.5] pinned (a window needs >= ceil(0.5 * sv_lb) finite
          buckets to yield a dispersion; otherwise tilt stays 1.0)
        + sv_rollmin [10] pinned (minimum valid r-pairs per bucket for the
          Roll cell; ~20 exist at most in a full month).
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl

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
    "sv_lb": [6],
    "sv_frac": [0.5],
    "sv_est": ["cs", "roll"],
    "sv_w": [0.05, -0.05],
    "sv_rollmin": [10],
}


def _monthly_roll(daily: pl.DataFrame, months, cols, min_pairs: int = 10) -> np.ndarray:
    """Per (calendar month, stock) the Roll (1984) implied spread from pairs
    of consecutive daily RELATIVE price changes: cov = E[r_t * r_{t-1}] -
    E[r_t] * E[r_{t-1}] within the bucket, S = 2*sqrt(max(0, -cov)) in
    price-fraction units. Bucket membership follows the CS convention (the
    pair's CARRYING bar r_t falls in the bucket); pairs whose three bars are
    not each 1-7 calendar days apart are dropped (session drops / holiday
    clusters); buckets with < min_pairs valid pairs are NaN; cov >= 0 floors
    to 0 (out of the bounce model), mirroring CS's floor-at-zero.

    Bucket -> (months x cols) mapping below is copied verbatim from
    strat_l20b_spread._monthly_spread — pivot plumbing, not an indicator."""
    d = daily.sort("symbol", "date")
    d = d.with_columns(
        pl.col("close").shift(1).over("symbol").alias("pdc"),
        pl.col("date").shift(1).over("symbol").alias("pdt"),
        pl.col("date").shift(2).over("symbol").alias("p2dt"))
    d = d.with_columns(
        (pl.col("close") / pl.col("pdc") - 1.0).alias("r"),
        (pl.col("date").cast(pl.Int32) - pl.col("pdt").cast(pl.Int32)).alias("gap1"),
        (pl.col("pdt").cast(pl.Int32) - pl.col("p2dt").cast(pl.Int32)).alias("gap2"))
    d = d.with_columns((pl.col("r").shift(1).over("symbol")).alias("rlag"))
    ok = (
        pl.col("r").is_finite() & pl.col("rlag").is_finite()
        & pl.col("pdt").is_not_null() & pl.col("p2dt").is_not_null()
        & (pl.col("pdc") > 0) & (pl.col("close") > 0)
        & (pl.col("gap1") >= 1) & (pl.col("gap1") <= 7)
        & (pl.col("gap2") >= 1) & (pl.col("gap2") <= 7)
    ).fill_null(False)
    d = d.with_columns(
        pl.when(ok).then(pl.col("r")).otherwise(None).cast(pl.Float64).alias("r"),
        pl.when(ok).then(pl.col("rlag")).otherwise(None).cast(pl.Float64).alias("rlag"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("r").count().alias("n"),
               pl.col("r").mean().alias("sx"),
               pl.col("rlag").mean().alias("sy"),
               (pl.col("r") * pl.col("rlag")).mean().alias("sxy"))
          .sort("symbol", "date"))
    g = g.with_columns((pl.col("sxy") - pl.col("sx") * pl.col("sy")).alias("cov"))
    g = g.with_columns(
        pl.when(pl.col("n") >= min_pairs)
          .then(2.0 * pl.max_horizontal(-pl.col("cov"), pl.lit(0.0)).sqrt())
          .otherwise(None).cast(pl.Float64).alias("spr"))
    piv = g.pivot(on="symbol", index="date", values="spr").sort("date")
    mind = {}
    for i, m in enumerate(months):
        mind[m if not hasattr(m, "date") else m.date()] = i
    out = np.full((len(months), len(cols)), np.nan)
    cidx = {s: j for j, s in enumerate(cols)}
    for row in piv.iter_rows(named=True):
        i = mind.get(row["date"])
        if i is None:
            continue
        for s, v in row.items():
            if s == "date":
                continue
            j = cidx.get(s)
            if j is not None and v is not None:
                out[i, j] = v
    return out


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-13/14 imported-default lesson):
    # this file's own keys default to the off-switch / pinned values; the
    # champion's sp keys are pinned to their champion dose so the composed
    # base IS the champion even if the caller omits them (a PASSED key —
    # e.g. the control cell's sp_w 0.0 — always wins over setdefault).
    p.setdefault("sv_w", 0.0)
    p.setdefault("sv_lb", 6)
    p.setdefault("sv_frac", 0.5)
    p.setdefault("sv_est", "cs")
    p.setdefault("sv_rollmin", 10)
    p.setdefault("sp_lb", 4)
    p.setdefault("sp_w", -0.05)
    p.setdefault("sp_frac", 0.5)
    out, regime = _l20(panels, p)  # current champion chain + level, verbatim
    out = np.array(out, dtype=float, copy=True)

    sv_w = float(p["sv_w"])
    if sv_w == 0.0:
        return out, regime  # off-switch: bitwise copy of the champion

    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    svlb = int(p["sv_lb"])
    est = str(p["sv_est"])
    if est not in ("cs", "roll"):
        raise ValueError(f"sv_est must be 'cs' or 'roll', got {est!r}")
    need = max(2, int(np.ceil(float(p["sv_frac"]) * svlb)))
    if est == "cs":
        SPR = _monthly_spread(daily, months, cols)  # imported estimator
    else:
        SPR = _monthly_roll(daily, months, cols, int(p["sv_rollmin"]))
    for t in range(svlb, out.shape[0]):
        win = SPR[t - svlb : t]
        cnt = np.isfinite(win).sum(axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            sd = np.nanstd(win, axis=0)  # ddof 0; 0.0 = perfectly stable
        valid = (cnt >= need) & np.isfinite(sd)
        n = int(valid.sum())
        tilt = np.ones(out.shape[1])
        if n >= 5:
            sv = sd[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt[valid] = 1.0 + sv_w * (2.0 * pct - 1.0)
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt, np.nan)
    return out, regime
