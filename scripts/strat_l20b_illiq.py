"""Candidate: Amihud illiquidity-LEVEL percentile tilt (both signs) on the
L19 champion book (strategy_lab contract).

Setup in words: the CURRENT champion chain strat_l19a_balanced (gatefail
lift -> ids tilt -> cap -> listing-age tilt -> outrank tilt -> final cap;
top 15, nse_all, cost 25bps, split 2022-01-01) is composed VERBATIM via
`from strat_l19a_balanced import score as _l19`, and its returned scores are
then re-weighted POST-chain by ONE new term: a cross-sectional percentile
tilt on the name's trailing Amihud-style illiquidity. Per daily bar:

    illiq_d = |close_d / close_{d-1} - 1| / (close_d * volume_d)

— absolute return per rupee of SAME-day turnover (Amihud, Y. (2001),
"Illiquidity and stock returns: cross-section and time-series effects",
Journal of Financial Markets 5(1), 31-56, eq. 1 |r|/dollar volume; here
rupee turnover = close * volume, both from the daily panel the harness
passes into score()). The bar value is averaged inside each calendar-month
bucket (bars with no previous close, or close*volume <= 0, excluded), then
averaged over the trailing il_lb-month window of buckets t-il_lb .. t-1
(il_lb 6 and 12 tested), percentile-ranked cross-sectionally among names
with >= ceil(il_frac * il_lb) finite buckets in the window (coverage guard,
il_frac pinned 0.5), and applied as:

    tilt[t] = 1 + il_w * (2 * pct - 1)     # pct in [0,1], |il_w| < 1
    out[t]  = out[t] * tilt                # finite entries only, NaN stays NaN

the multiplier landing strictly on the finite entries of the champion's
RETURNED scores: rows before the window (t < il_lb) are untouched, names
failing the coverage guard keep tilt exactly 1.0 (never NaN-ed — a thin
history gets NO percentile, it does not lose eligibility: this is a
re-ranking, not a gate), NaN stays NaN, and |il_w| < 1 keeps the multiplier
strictly positive so no cap or pick decision changes eligibility — only
ordering. Both signs are first-class: il_w > 0 favours HIGH illiquidity
(the Amihud/ Pastor-Stambaugh illiquidity PREMIUM: thin names' higher
expected return per unit turned over), il_w < 0 favours LOW illiquidity
(liquidity QUALITY: names the book's own flow can trade without impact,
fewer thin-tail blowups — the drawdown story this balanced sprint weighs
against raw CAGR).

Hypothesis: the L19 transfer finding says the champion's edge lives in
small/non-index names, i.e. its book already leans toward the illiquid end
of the panel; no chain term ever reads turnover or return-per-rupee — ids
is inside-day geometry, or is lagged-return percentile, la is static age.
Two opposite priors therefore compete on genuinely new information: (a) the
premium story compounds the book's small-cap tilt with the names where
illiquidity is most compensated; (b) the quality story orders the same
capped pool away from the untradeable tail and cuts drawdown. If every
variant ties or trails the flat base, the LEVEL of illiquidity adds nothing
the gates/ids/age terms do not already encode and the axis closes.

Falsifier: if ALL four SPACE variants (6/12 x +0.1/-0.1) trail the flat
base — train +98.682% / DD -15.506% / calmar 6.364 / fwd +53.148% / fwd DD
-10.403% — on train CAGR with no offsetting improvement in drawdown or
forward (operationally: the harness keep rule never fires on the smoke
ledger; per the Loop-17 rule a train gain bought with wider DD or a forward
collapse is an ARTIFACT, not an upgrade), then the illiquidity-LEVEL axis
closes on the L19 base and the legacy family's DEAD verdict stands in tilt
form too. Before ANY promotion: this tilt re-orders the capped pool (a
book-composition mechanism) — count the decision months where its picks
differ from the champion's (Loop-16 lesson; a gain sourced from a handful
of name-months is a sample of a handful, not an edge).

NOVELTY STATEMENT (closest registry rows -> the ONE thing that changed):
- research/tested_mechanisms.tsv line 29 strat_floorhighliq, line 64
  strat_floorliq, line 68 strat_highliq, line 70 strat_liqtrend, line 13
  strat_floorhighaccum, line 23 strat_floorhighfreshpart, lines 32-34
  strat_floorhighpart/partmult/partrank — the legacy liquidity/volume
  family, ALL DEAD, and their DEAD form was a HARD ELIGIBILITY GATE on the
  OLD floorhigh/sustaincond chain (NaN below a liquidity/volume threshold,
  pre-cap, pre-wobble, pre-ids, pre-tilt era): a gate can only remove
  names. line 30 strat_floorhighliqw is the family's single rank-weight
  (additive z-score of log trailing-median rupee turnover inside the legacy
  sustaincond rank) — also DEAD, also on a legacy base, and a z-blend
  rather than a strictly positive post-chain percentile multiplier.
- research/tested_mechanisms.tsv line 136 strat_l17d_flowdir — the
  accepted changed-base retest PRECEDENT for exactly this family ("signed
  volume split - changed-base retest of the legacy accum gate; both
  signs", DEAD 71.1-86.6 on the ids champion).
- NOT re-tested (closed, cited only): line 117 strat_l16c_volpart (volume
  participation expansion/contraction, DEAD L16) and line 136 flowdir
  (signed flow) — the DIRECTION and CHANGE questions of volume are shut;
  this file asks only the LEVEL of illiquidity.
WHAT CHANGED — the two sanctioned changes: (a) the BASE: every prior row
above died on the old floorhigh/sustaincond chain or the ids champion and
none of them ever saw the current L19 champion chain (strat_l19a_balanced,
train +98.682 / -15.506 / calmar 6.364); (b) the FORM: from hard
eligibility GATE on that old chain to a strictly positive cross-sectional
percentile MULTIPLIER applied post-chain to the champion's returned scores
— it can only re-order the capped pool, never remove a name, so it cannot
reproduce the gate's exposure collapse. The signal itself (Amihud
return-per-rupee) is new to the repo: no registry row has ever ranked on it.

Import chain: strat_l20b_illiq -> strat_l19a_balanced.score (the CURRENT
champion; it neutralises gatefail's leakable defaults itself, re-expresses
the ids tilt via _monthly_inside from strat_l15b_insideday, mirrors the
cap inline, then applies the listing-age and outrank tilts) ->
strat_l12b_gatefail.score -> strat_floorhighfastgate +
strat_floorhighsustaincond + strat_floorhightiershape (+ wobble). This
file adds only the post-chain illiq tilt on top; it copies no indicator —
the Amihud bar formula above is new, everything else is delegated.

PIT argument: bucket k of _monthly_illiq contains only daily bars with
date in [months[k], months[k+1]); the window read at row t is buckets
[t-il_lb, t-1], whose bars all have date < months[t] — the same
bucket-t-1-and-older convention as the ids tilt and strat_l17d_flowdir.
The percentile at row t uses only that row's cross-section of backward
windows; rows t < il_lb are untouched; no row > t is read anywhere. The
delegate's PIT is unchanged from strat_l19a_balanced (ids: daily bars
strictly before months[t]; age: static listing_date, 0 nulls on 2,559
symbols; outrank: px[t-or_lb]..px[t]; cap: month-t ranks and E[t]). prev
close is the previous RECORDED bar of the same symbol (shift over symbol
on date-sorted data) — Yahoo session drops make a rare ratio span > 1 day,
the same shift-over-symbol convention the flowdir sign split uses;
upstream gaps are reported by validate_data.py, never silently patched.
Volume and close come from the harness-loaded daily panel, unchanged.

Off-switch identity: il_w = 0.0 (this file's OWN setdefault, applied to
the params copy BEFORE delegating — Loop-13/14 imported-default lesson)
skips the tilt block entirely, so `out` is bitwise a copy of
strat_l19a_balanced's returned scores at the PASSED keys. Champion keys
are always PASSED by the caller, never defaulted here: the delegate reads
la_w/or_w/gw_w/ids_w via .get with 0.0 defaults, so a missing key would
silently de-tune the base instead of reproducing it.

Flat-base metric (off-switch must reproduce exactly): train +98.682% /
DD -15.506% / calmar 6.364 / H1 +95.295% / H2 +101.966% / fwd +53.148% /
fwd DD -10.403% / full +79.237% / full DD -20.728%.

Keys consumed: this file reads il_w, il_lb, il_frac; everything else in
params-json flows through to the delegate (all SPACE champion keys) or is
read by the harness (max_hold 3).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1; max_hold 3 is a HARNESS
        key passed via params-json, not consumed here)
        + il_lb {6, 12}   (trailing window in calendar-month buckets)
        + il_w {+0.1, -0.1} x {6, 12} = 4 documented variants (0.0 =
          off-switch; > 0 favours HIGH illiquidity, < 0 favours liquid)
        + il_frac [0.5] pinned (coverage guard: a name needs >=
          ceil(0.5 * il_lb) finite monthly buckets in the window to earn a
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
    "il_lb": [6, 12],
    "il_w": [0.1, -0.1],
    "il_frac": [0.5],
}


def _monthly_illiq(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month, stock) the MEAN daily Amihud bar
    |close/prev_close - 1| / (close * volume); NaN where the bucket had no
    usable bar (no previous close, or close*volume <= 0)."""
    d = daily.sort("symbol", "date")
    d = d.with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
    d = d.with_columns(
        (pl.col("close") / pl.col("pc") - 1.0).abs().alias("absret"),
        (pl.col("close") * pl.col("volume").cast(pl.Float64)).alias("turn"))
    d = d.with_columns(
        pl.when(pl.col("pc").is_not_null() & (pl.col("close") > 0.0)
                & (pl.col("turn") > 0.0))
          .then(pl.col("absret") / pl.col("turn"))
          .otherwise(None)
          .cast(pl.Float64)
          .alias("illiq"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("illiq").mean())
          .sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="illiq").sort("date")
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
    p.setdefault("il_w", 0.0)
    p.setdefault("il_lb", 6)
    p.setdefault("il_frac", 0.5)
    scores, regime = _l19(panels, p)  # current champion chain, verbatim
    out = np.array(scores, dtype=float, copy=True)

    il_w = float(p["il_w"])
    if il_w == 0.0:
        return out, regime  # off-switch: bitwise copy of the champion

    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    ilb = int(p["il_lb"])
    need = max(2, int(np.ceil(float(p["il_frac"]) * ilb)))
    ILQ = _monthly_illiq(daily, months, cols)
    for t in range(ilb, out.shape[0]):
        win = ILQ[t - ilb : t]  # buckets t-ilb..t-1: all date < months[t]
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
            tilt[valid] = 1.0 + il_w * (2.0 * pct - 1.0)
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt, np.nan)
    return out, regime
