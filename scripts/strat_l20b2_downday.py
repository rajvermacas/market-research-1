"""Candidate: DOWN-DAY-ONLY Amihud illiquidity percentile tilt (both signs)
on the L19 champion book (strategy_lab contract).

Setup in words: the CURRENT champion chain strat_l19a_balanced (gatefail
lift -> ids tilt -> cap -> listing-age tilt -> outrank tilt -> final cap;
top 15, nse_all, cost 25bps, split 2022-01-01) is composed VERBATIM via
`from strat_l19a_balanced import score as _l19`, and its returned scores are
then re-weighted POST-chain by ONE term: a cross-sectional percentile tilt
on the name's trailing DOWN-DAY Amihud illiquidity. For each daily bar with
ret = close_d / close_{d-1} - 1 < 0:

    dd_illiq_d = |ret| / (close_d * volume_d)          # DOWN DAYS ONLY

— absolute return per rupee of same-day turnover, conditioned on the session
being a down session. Per calendar-month bucket: the MEAN over that month's
down-day observations, kept ONLY IF the month has at least
max(2, ceil(dd_frac * bars_in_month)) down-day observations (dd_frac
default 0.2, pinned — a month with almost no down sessions carries no
sample of the thing being measured and gets NO bucket rather than a
one-bar mean). The bucket series is then averaged over the trailing
il_lb-month window (il_lb 6 and 12 tested), percentile-ranked
cross-sectionally among names with >= ceil(il_frac * il_lb) finite buckets
in the window (coverage guard, il_frac pinned 0.5), and applied as:

    tilt[t] = 1 + il_w * (2 * pct - 1)     # pct in [0,1], |il_w| < 1
    out[t]  = out[t] * tilt                # finite entries only, NaN stays NaN

— landing on the finite entries of the champion's RETURNED scores: rows
before the window (t < il_lb) are untouched, names failing the coverage
guard keep tilt exactly 1.0 (never NaN-ed — a thin history gets NO
percentile, it does not lose eligibility: re-ranking, not a gate), NaN
stays NaN, ties broken by stable argsort exactly as in the parent, and
|il_w| < 1 keeps the multiplier strictly positive so only ordering can
change. Both signs first-class: il_w > 0 favours HIGH down-day illiquidity,
il_w < 0 favours LOW (liquid-quality) names.

ESTIMATOR SOURCE: this is strat_l20b_illiq.py's estimator RE-EXPRESSED with
its conditioning set changed (see NOVELTY); the coverage/NaN/tie handling,
the window/percentile loop, the setdefault-before-delegate order and the
off-switch shape are line-for-line that file's conventions. Parent is
FROZEN (md5 93571a2b54042308a1c2dde5b2aa644d); this file never edits it.
Formula citation: Amihud, Y. (2001), "Illiquidity and stock returns:
cross-section and time-series effects", Journal of Financial Markets 5(1),
31-56, eq. 1 |r|/dollar volume — here evaluated only on ret < 0 bars.

Rationale / hypothesis: the SYMMETRIC Amihud estimator (parent) mixes
up-session and down-session impact into one number, but the illiquidity
premium is normally attributed to the cost of SELLING INTO WEAKNESS — the
price impact you pay precisely when you must trade on a bad day. Up-day
impact is the mirror cost of BUYING into strength, a different trade the
champion's entry never makes at the same urgency. Restricting the estimator
to down days should therefore be the SHARPER version of the signal that just
led the loop: parent (lb 12, +0.1) = train +102.350 / DD -15.979 / calmar
6.405 / fwd +54.405 / -10.403 (neighbourhood confirmed peak). If the
down-day restriction is what carried that result, this file's flagship cell
(12, +0.1) BEATS 102.350; if the parent's edge was carried by all sessions
equally (or is noise), the down-day cells tie or trail their symmetric
parents.

Falsifier (pre-registered): ALL four variants <= their same-column
symmetric parent on train CAGR — (12,+0.1) <= 102.350, (6,+0.1) <= 98.758,
(12,+0.15) <= 101.30 (parent neighbourhood), (6,-0.1) <= 97.066 — with no
compensating improvement in drawdown or forward (operationally: the harness
keep rule's result versus those parents; per the Loop-17 rule a train gain
bought with wider DD or a forward collapse is an ARTIFACT) -> the asymmetry
is NOT the source of the parent's edge and the down-day form closes.
Identity must also print the flat base exactly (below). Before ANY
promotion: count the decision months where this tilt's picks differ from
the champion's (Loop-16 book-composition lesson).

NOVELTY STATEMENT (closest prior art -> the ONE thing that changed):
- Parent, same family, same base, same form: scripts/strat_l20b_illiq.py
  (frozen md5 93571a2b54042308a1c2dde5b2aa644d; registry row pending at
  close-out) — the SYMMETRIC Amihud level tilt that produced the loop's
  strongest lead (+102.350 train at lb 12 / +0.1).
- Family context (all DEAD as HARD ELIGIBILITY GATES on the OLD
  floorhigh/sustaincond chain, cited not re-tested): registry lines 13, 29,
  30, 64, 68, 70; line 136 strat_l17d_flowdir is the changed-base retest
  precedent; line 117 strat_l16c_volpart (participation) is closed.
WHAT CHANGED — the ONE thing: the CONDITIONING SET of the estimator —
down-day bars only, versus the parent's all-bar mean. Base (L19 champion
chain), form (strictly-positive post-chain percentile multiplier), window,
coverage guard, sign space and tie handling are inherited UNCHANGED from
the parent and are not re-argued here. The research registry has NO
asymmetric-liquidity row: nothing has ever conditioned an impact/liquidity
measure on the sign of the session. This is a sharpening test of an
existing positive result, not a new axis.

Import chain: strat_l20b2_downday -> strat_l19a_balanced.score (the CURRENT
champion; it neutralises gatefail's leakable defaults itself, re-expresses
the ids tilt via _monthly_inside from strat_l15b_insideday, mirrors the cap
inline, then applies the listing-age and outrank tilts) ->
strat_l12b_gatefail.score -> strat_floorhighfastgate +
strat_floorhighsustaincond + strat_floorhightiershape (+ wobble). This file
adds only the post-chain down-day illiq tilt; it copies no other indicator.

PIT argument: bucket k contains only daily bars with date in
[months[k], months[k+1]); the window read at row t is buckets
[t-il_lb, t-1], whose bars all have date < months[t] — the parent's
bucket-t-1-and-older convention. The bar's ret uses close_{d-1}, the
previous RECORDED bar of the same symbol (shift over symbol on
date-sorted data, the parent's convention; Yahoo session drops make a rare
ratio span > 1 day, reported by validate_data.py, never patched) — for the
first bar of a bucket that is the previous bucket's last close, still a
strictly earlier date, so no future information enters. The down-day
count guard reads only the same bucket's own bars. The percentile at row t
uses only that row's cross-section of backward windows; rows t < il_lb are
untouched; no row > t is read. The delegate's PIT is unchanged from
strat_l19a_balanced (ids: daily bars strictly before months[t]; age: static
listing_date; outrank: px[t-or_lb]..px[t]; cap: month-t ranks and E[t]).

Off-switch identity: il_w = 0.0 (this file's OWN setdefault, applied to the
params copy BEFORE delegating — Loop-13/14 imported-default lesson) skips
the tilt block entirely, so `out` is bitwise a copy of
strat_l19a_balanced's returned scores at the PASSED keys — and
_monthly_downday_illiq is never called (its dd_frac argument never read).
Champion keys are always PASSED by the caller, never defaulted here: the
delegate reads la_w/or_w/gw_w/ids_w via .get with 0.0 defaults, so a
missing key would silently de-tune the base instead of reproducing it.

Flat-base metric (off-switch must reproduce exactly): train +98.682% /
DD -15.506% / calmar 6.364 / H1 +95.295% / H2 +101.966% / fwd +53.148% /
fwd DD -10.403% / full +79.237% / full DD -20.728%.

Keys consumed: this file reads il_w, il_lb, il_frac, dd_frac; everything
else in params-json flows through to the delegate (all SPACE champion keys)
or is read by the harness (max_hold 3).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1; max_hold 3 is a HARNESS
        key passed via params-json, not consumed here)
        + il_lb {6, 12}  (trailing window in calendar-month buckets)
        + il_w {+0.1, +0.15, -0.1} x {6, 12} domain, 0.0 = off-switch
        + il_frac [0.5] pinned (window coverage guard, parent's convention)
        + dd_frac [0.2] pinned (per-bucket down-day count guard: a bucket
          needs >= max(2, ceil(0.2 * bars_in_month)) down-day observations)
        Pre-registered cells (5 trials):
          1. identity   (lb 12, il_w 0.0)
          2. flagship   (lb 12, +0.1)   vs parent 102.350
          3. short      (lb 6,  +0.1)   vs parent 98.758
          4. dose-up    (lb 12, +0.15)  vs parent-neighbourhood 101.30
          5. reverse    (lb 6,  -0.1)   vs parent 97.066
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
    "il_w": [0.1, 0.15, -0.1],
    "il_frac": [0.5],
    "dd_frac": [0.2],
}


def _monthly_downday_illiq(daily: pl.DataFrame, months, cols,
                           dd_frac: float) -> np.ndarray:
    """Per (calendar month, stock) the MEAN Amihud bar over DOWN-DAY bars
    only: for each bar with ret = close/prev_close - 1 < 0 (and the parent's
    guards: prev close present, close > 0, turn = close*volume > 0), the
    value |ret| / turn. The bucket is kept only if the month has
    >= max(2, ceil(dd_frac * bars_in_month)) such observations (two-sided
    guard written as `ddn >= 2 & ddn >= ceil(dd_frac*nbars)` so no max()
    call is needed); otherwise the bucket is NaN — never a thin one-bar
    mean. Same sort/pivot/mapping skeleton as the parent's
    _monthly_illiq (source: strat_l20b_illiq.py, frozen md5 93571a2b...)."""
    d = daily.sort("symbol", "date")
    d = d.with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
    d = d.with_columns(
        (pl.col("close") / pl.col("pc") - 1.0).alias("ret"),
        (pl.col("close") * pl.col("volume").cast(pl.Float64)).alias("turn"))
    d = d.with_columns(
        pl.when(pl.col("pc").is_not_null() & (pl.col("close") > 0.0)
                & (pl.col("turn") > 0.0) & (pl.col("ret") < 0.0))
          .then(-pl.col("ret") / pl.col("turn"))          # |ret| since ret<0
          .otherwise(None)
          .cast(pl.Float64)
          .alias("dd"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("dd").mean().alias("ddm"),             # mean over down days
               pl.col("dd").is_not_null().sum().alias("ddn"),  # # down-day obs
               pl.col("close").count().alias("nbars"))         # # bars in month
          .sort("symbol", "date"))
    g = g.with_columns(
        pl.when((pl.col("ddn") >= 2)
                & (pl.col("ddn") >= (pl.col("nbars") * dd_frac).ceil()))
          .then(pl.col("ddm"))
          .otherwise(None)
          .cast(pl.Float64)
          .alias("illiq"))
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
    p.setdefault("dd_frac", 0.2)
    scores, regime = _l19(panels, p)  # current champion chain, verbatim
    out = np.array(scores, dtype=float, copy=True)

    il_w = float(p["il_w"])
    if il_w == 0.0:
        return out, regime  # off-switch: bitwise copy of the champion,
        # before the down-day estimator matrix is ever built

    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    ilb = int(p["il_lb"])
    need = max(2, int(np.ceil(float(p["il_frac"]) * ilb)))
    ILQ = _monthly_downday_illiq(daily, months, cols,
                                 float(p["dd_frac"]))
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
