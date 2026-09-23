"""Candidate: Corwin-Schultz spread-LEVEL percentile tilt (both signs) on
the L19 champion book (strategy_lab contract).

Setup in words: the CURRENT champion chain strat_l19a_balanced (gatefail
lift -> ids tilt -> cap -> listing-age tilt -> outrank tilt -> final cap;
top 15, nse_all, cost 25bps, split 2022-01-01) is composed VERBATIM via
`from strat_l19a_balanced import score as _l19`, and its returned scores
are then re-weighted POST-chain by ONE new term: a cross-sectional
percentile tilt on the name's trailing Corwin-Schultz bid-ask spread
proxy. For each pair of consecutive daily bars of a symbol (second bar
carries the estimate):

    beta  = (ln(H1/L1))^2 + (ln(H2/L2))^2
    gamma = (ln(max(H1,H2) / min(L1,L2)))^2
    alpha = (sqrt(2*beta) - sqrt(beta)) / (3 - 2*sqrt(2))
            - sqrt(gamma / (3 - 2*sqrt(2)))
    S     = 2*(exp(alpha) - 1) / (1 + exp(alpha)),  floored at 0

(Corwin, S. and Schultz, P. (2012), "A Simple Way to Estimate the Bid-Ask
Spread from Daily High and Low Prices", The Journal of Finance 67(2),
719-760, eqs. 3-5; negative two-day estimates — alpha < 0 iff S < 0 — are
truncated to zero as the paper prescribes). Pairs whose two bars are less
than 1 or more than 7 calendar days apart are dropped (duplicate rows;
Yahoo session drops / holiday clusters that would make a "two-day" spread
span two weeks) — the one documented deviation from the raw estimator.
Pairs with a non-positive high or low are dropped (bad ticks; validate_data
reports OHLC-order violations upstream — nothing is repaired here, and the
squared terms make an h < l violation harmless anyway). The per-pair S is
averaged inside each calendar-month bucket, then averaged over the
trailing sp_lb-month window of buckets t-sp_lb .. t-1 (sp_lb 6 and 12
tested), percentile-ranked cross-sectionally among names with >=
ceil(sp_frac * sp_lb) finite buckets (coverage guard, sp_frac pinned 0.5),
and applied as:

    tilt[t] = 1 + sp_w * (2 * pct - 1)     # pct in [0,1], |sp_w| < 1
    out[t]  = out[t] * tilt                # finite entries only, NaN stays NaN

multiplied strictly on the finite entries of the champion's RETURNED
scores: rows before the window (t < sp_lb) are untouched, names failing
the coverage guard keep tilt exactly 1.0 (never NaN-ed — a thin history
earns no percentile, it does not lose eligibility: re-ranking, not a
gate), NaN stays NaN, |sp_w| < 1 keeps the multiplier strictly positive.
Both signs are first-class: sp_w > 0 favours HIGH-spread names (the
illiquidity/noise-trader-premium story: wide-spread names compensate
holders more), sp_w < 0 favours LOW-spread names (execution-quality story:
tight spread = real depth; the book enters and exits cheaper and avoids
the names where the close is mostly bounce).

STABILITY JUDGEMENT (the brief's alternative): CS is KEPT as specified,
not replaced by a simple high-low range-to-close proxy. Why it is stable
enough here: the estimator is per-pair, then averaged over ~20 pairs per
month and over 6/12 months, and the consumer is a CROSS-SECTIONAL
PERCENTILE — rank is insensitive to the estimator's scale and heavy tail;
the floor at 0 handles CS's known negative-estimate mass; the gap guard
keeps "two-day" honest across Yahoo session drops. Why the range proxy was
rejected: it discards the two-day overlap that removes CS's high-low bias
and reduces to pure volatility, an axis the vol-LEVEL family already
falsified (research/tested_mechanisms.tsv line 6 strat_concvolgate,
line 96 strat_l14a_volrank, both DEAD — exposure/rank scaled by
volatility), whereas spread is a microstructure COST (it loads on
turnover and bounce, not symmetric risk).

Hypothesis: the champion's book is essentially small/non-index names
(L19 transfer finding), which is exactly where spreads are widest; no
chain term reads execution cost — ids is inside-day geometry, or is
lagged return, la is age. Two priors compete on new information: (a)
wide-spread names carry a premium that the small-cap tilt already partly
harvests — compounding it orders the capped pool toward it; (b) the top-15
book's realisable return is degraded exactly where spreads are widest, so
ordering toward tight spread raises quality and cuts drawdown. If every
variant ties or trails the flat base, spread LEVEL adds nothing beyond the
gates/ids/age terms and the axis closes.

Falsifier: if ALL four SPACE variants (6/12 x +0.1/-0.1) trail the flat
base — train +98.682% / DD -15.506% / calmar 6.364 / fwd +53.148% / fwd DD
-10.403% — on train CAGR with no offsetting improvement in drawdown or
forward (operationally: the harness keep rule never fires on the smoke
ledger; per the Loop-17 rule a train gain bought with wider DD or a
forward collapse is an ARTIFACT, not an upgrade), then the spread-LEVEL
axis closes on the L19 base. Before ANY promotion: this tilt re-orders the
capped pool (a book-composition mechanism) — count the decision months
where its picks differ from the champion's (Loop-16 lesson).

NOVELTY STATEMENT (closest registry rows -> the ONE thing that changed):
- research/tested_mechanisms.tsv line 29 strat_floorhighliq, line 64
  strat_floorliq, line 68 strat_highliq, line 70 strat_liqtrend, line 13
  strat_floorhighaccum, line 30 strat_floorhighliqw — the legacy
  liquidity/volume family, ALL DEAD, and their DEAD form was a HARD
  ELIGIBILITY GATE on the OLD floorhigh/sustaincond chain (NaN below a
  liquidity/volume threshold; liqw was the one additive z-blend of
  turnover, also on that legacy base): a gate can only remove names.
- research/tested_mechanisms.tsv line 136 strat_l17d_flowdir — the
  accepted changed-base retest PRECEDENT for this family ("signed volume
  split - changed-base retest of the legacy accum gate; both signs", DEAD
  71.1-86.6 on the ids champion).
- Range-derived prior art, distinct signal: line 107 strat_l15b_rngcomp
  (self-normalised range COMPRESSION vs own history, DEAD on the ids base
  69.5-75.8) and line 119 strat_l17a_rangeac (range serial dependence,
  DEAD) measure temporal shape, not a cross-sectional cost level; lines
  6/96 (vol level) were rejected above.
- NOT re-tested (closed): line 117 strat_l16c_volpart (participation
  expansion, DEAD L16) and line 136 flowdir (signed flow) — direction and
  change of volume are shut; this file asks LEVEL of spread only.
WHAT CHANGED — the two sanctioned changes: (a) the BASE: every prior row
above died on the old floorhigh/sustaincond chain or the ids champion;
none ever saw the current L19 champion chain (strat_l19a_balanced, train
+98.682 / -15.506 / calmar 6.364); (b) the FORM: from hard eligibility
GATE on that old chain to a strictly positive cross-sectional percentile
MULTIPLIER applied post-chain to the champion's returned scores — it can
only re-order the capped pool, never remove a name. The signal itself
(Corwin-Schultz spread) is new to the repo: no registry row has ever
ranked on a spread estimator.

Import chain: strat_l20b_spread -> strat_l19a_balanced.score (the CURRENT
champion; it neutralises gatefail's leakable defaults itself, re-expresses
the ids tilt via _monthly_inside from strat_l15b_insideday, mirrors the
cap inline, then applies the listing-age and outrank tilts) ->
strat_l12b_gatefail.score -> strat_floorhighfastgate +
strat_floorhighsustaincond + strat_floorhightiershape (+ wobble). This
file adds only the post-chain spread tilt; everything else is delegated —
the CS estimator above is the only new computation.

PIT argument: bucket k of _monthly_spread contains only pairs whose
CARRYING (second) bar falls in [months[k], months[k+1]); the window read
at row t is buckets [t-sp_lb, t-1], whose bars all have date < months[t] —
the same bucket-t-1-and-older convention as the ids tilt and
strat_l17d_flowdir (a pair is only used once its second bar is inside the
bucket, so the estimate never reaches row t before both its bars do). The
percentile at row t uses only that row's backward cross-section; rows
t < sp_lb are untouched; no row > t is read anywhere. The delegate's PIT
is unchanged from strat_l19a_balanced (ids: daily bars strictly before
months[t]; age: static listing_date; outrank: px[t-or_lb]..px[t]; cap:
month-t ranks and E[t]). shift(1) over symbol on date-sorted data never
reads a future bar.

Off-switch identity: sp_w = 0.0 (this file's OWN setdefault, applied to
the params copy BEFORE delegating — Loop-13/14 imported-default lesson)
skips the tilt block entirely, so `out` is bitwise a copy of
strat_l19a_balanced's returned scores at the PASSED keys. Champion keys
are always PASSED by the caller, never defaulted here: the delegate reads
la_w/or_w/gw_w/ids_w via .get with 0.0 defaults, so a missing key would
silently de-tune the base instead of reproducing it.

Flat-base metric (off-switch must reproduce exactly): train +98.682% /
DD -15.506% / calmar 6.364 / H1 +95.295% / H2 +101.966% / fwd +53.148% /
fwd DD -10.403% / full +79.237% / full DD -20.728%.

Keys consumed: this file reads sp_w, sp_lb, sp_frac; everything else in
params-json flows through to the delegate (all SPACE champion keys) or is
read by the harness (max_hold 3).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1; max_hold 3 is a HARNESS
        key passed via params-json, not consumed here)
        + sp_lb {6, 12}   (trailing window in calendar-month buckets)
        + sp_w {+0.1, -0.1} x {6, 12} = 4 documented variants (0.0 =
          off-switch; > 0 favours HIGH spread, < 0 favours tight spread)
        + sp_frac [0.5] pinned (coverage guard: a name needs >=
          ceil(0.5 * sp_lb) finite monthly buckets in the window to earn a
          percentile; otherwise tilt stays 1.0 — never NaN).
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl

from strat_l19a_balanced import score as _l19

NEEDS_DAILY = True  # the delegate's ids term reads daily; this file reads it too

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
    "sp_lb": [6, 12],
    "sp_w": [0.1, -0.1],
    "sp_frac": [0.5],
}


def _monthly_spread(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month, stock) the MEAN Corwin-Schultz two-day spread
    of pairs whose second bar falls in the bucket; NaN where the bucket had
    no usable pair. Negative pair estimates floored at 0; pairs < 1 or > 7
    calendar days apart dropped."""
    d = daily.sort("symbol", "date")
    d = d.with_columns(
        pl.col("high").shift(1).over("symbol").alias("ph"),
        pl.col("low").shift(1).over("symbol").alias("plow"),
        pl.col("date").shift(1).over("symbol").alias("pdt"))
    d = d.with_columns(
        (pl.col("date").cast(pl.Int32) - pl.col("pdt").cast(pl.Int32))
        .alias("gap"))  # calendar-day distance between the pair's bars
    c = 3.0 - 2.0 * float(np.sqrt(2.0))  # CS denominator, eq. 5
    d = d.with_columns(
        (((pl.col("ph").log() - pl.col("plow").log()) ** 2)
         + ((pl.col("high").log() - pl.col("low").log()) ** 2))
        .alias("beta"),
        ((pl.max_horizontal("ph", "high").log()
          - pl.min_horizontal("plow", "low").log()) ** 2)
        .alias("gamma"))
    d = d.with_columns(
        ((((2.0 * pl.col("beta")).sqrt() - pl.col("beta").sqrt()) / c)
         - (pl.col("gamma") / c).sqrt())
        .alias("alpha"))
    d = d.with_columns(
        (2.0 * (pl.col("alpha").exp() - 1.0)
         / (1.0 + pl.col("alpha").exp()))
        .alias("spr"))
    ok = (pl.col("ph").is_not_null() & pl.col("pdt").is_not_null()
          & (pl.col("ph") > 0) & (pl.col("plow") > 0)
          & (pl.col("high") > 0) & (pl.col("low") > 0)
          & (pl.col("gap") >= 1) & (pl.col("gap") <= 7))
    d = d.with_columns(
        pl.when(ok)
          .then(pl.max_horizontal(pl.col("spr"), pl.lit(0.0)))
          .otherwise(None)
          .cast(pl.Float64)
          .alias("spr"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("spr").mean())
          .sort("symbol", "date"))
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
    # neutral defaults BEFORE delegating (Loop-13/14 imported-default
    # lesson): this file's own keys default to the off-switch / pinned
    # values whatever the caller passes; the delegate neutralises ITS
    # leakable defaults (gf_w 0.05 / gw_w) inside strat_l19a_balanced.
    p.setdefault("sp_w", 0.0)
    p.setdefault("sp_lb", 6)
    p.setdefault("sp_frac", 0.5)
    scores, regime = _l19(panels, p)  # current champion chain, verbatim
    out = np.array(scores, dtype=float, copy=True)

    sp_w = float(p["sp_w"])
    if sp_w == 0.0:
        return out, regime  # off-switch: bitwise copy of the champion

    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    slb = int(p["sp_lb"])
    need = max(2, int(np.ceil(float(p["sp_frac"]) * slb)))
    SPR = _monthly_spread(daily, months, cols)
    for t in range(slb, out.shape[0]):
        win = SPR[t - slb : t]  # buckets t-slb..t-1: all date < months[t]
        cnt = np.isfinite(win).sum(axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            val = np.nanmean(win, axis=0)
        valid = np.isfinite(val) & (cnt >= need)  # coverage guard
        n = int(valid.sum())
        tilt = np.ones(out.shape[1])
        if n >= 5:
            sv = val[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt[valid] = 1.0 + sp_w * (2.0 * pct - 1.0)
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt, np.nan)
    return out, regime
