"""Candidate: large-up-day count tilt on the champion book (strategy_lab
contract).

Setup in words: the CURRENT champion chain (strat_l12b_gatefail.score:
floor-lift fresh-print rank among short-trend-passing, print-continuity-
passing names, breadth tiers, eligibility-wobble) carrying the champion's
inside-day tilt (ids_lb 3 / ids_w -0.13, helper imported from
strat_l15b_insideday and mirrored pre-cap exactly as strat_l17b_crowd
mirrors it) is re-weighted, BEFORE the regime-conditional cap step (mirrored
inline), by a NEW daily-tape signal: the share of LARGE UP DAYS in the
name's recent tape. Per daily bar and symbol:

    ret_d  = close_d / close_{d-1} - 1
    vol_d  = std(ret over the previous vol_lb bars, ending at d-1)
    jump_d = ret_d > jc_k * vol_d          (undefined while vol_d is null/0)

vol_d uses a full vol_lb-bar rolling window (min_samples = window_size), so
a name needs vol_lb bars of history before any of its days can be
classified — the warm-up guard is structural. Per calendar-month bucket:

    jc_m   = count(jump days) / count(classified bars)

averaged over the jc_lb monthly buckets ending at the print month (the
calendar month before the holding month), percentile-ranked cross-section-
ally among names with a finite share, tilt = 1 + jc_w * (2*pct - 1); NaN
share keeps tilt 1.0.

Hypothesis: the champion buys fresh 12-month-high printers and already
rewards EXPANDING tapes (the winning ids direction favours FEWER inside
days). Jump density asks a question the range-geometry term cannot: is the
extension arriving in DISCRETE DEMAND BURSTS (days whose gain exceeds
jc_k sigma of the name's own recent tape) or in steady drift? Self-
normalisation matters: a +3% day is a jump for a 1%-vol large cap and
noise for a 6%-vol small cap, so the statistic counts exceedances relative
to the name's own regime, not absolute move size. Two opposite stories:
(a) jc_w > 0 — repeated tail up-days are the footprint of accumulation
    (institutional buying that cannot fill in one session) and of
    news-anchored repricing; fresh highs on jump-dense tape continue;
(b) jc_w < 0 — climax/attention bursts mean-revert; the champion's edge
    lives in grinders whose highs are printed without violence.
If jump density is the same information the ids term already encodes
(expanding tape), every variant ties or double-counts and the channel
closes; a different ordering within the ids-tilted book is the add.

NOVELTY STATEMENT (closest registry rows + the one thing changed):
- strat_l16a_dskew (DEAD, 74.4-78.0): skewness is the THIRD MOMENT of the
  full daily return distribution — every day contributes with its squared
  deviation, sign-asymmetry of the whole window. A jump COUNT is a tail
  FREQUENCY: non-jump days contribute nothing but denominator, magnitude
  is thresholded away, and a negatively skewed window (many small down
  days, few huge up days) can be jump-dense while dskew reads it negative.
- strat_l15b_upstreak (DEAD): streaks are ORDER statistics — consecutive
  up closes. Jump counts are order-free and magnitude-gated: one 3-sigma
  day between flat days is a jump and not a streak; five +0.5% days in a
  row are a streak and not a jump.
- strat_floorhighprintcount / hotprint / heatgate (DEAD print-quality
  family): those rank/gate on the MONTHLY PRINT (count of new-high print
  months, print-month return) — month-end statistics, no daily bars
  consumed. This file counts daily-bar tail events inside the window.
- strat_l15b_insideday / rngcomp (champion tape geometry): high/low range
  containment and range RATIOS — bar SHAPE. A tape can extend its range
  every day (zero inside days, low range ratio) with zero jumps (steady
  +0.8% drift) or print one 4-sigma day inside wide churn. Exceedance
  count is a different functional of the tape than any range geometry.
The one thing changed: the signal is a COUNT of self-normalised tail
exceedance events — no term in the chain consumes an exceedance count.

Import chain: strat_l17d_jumpcount -> strat_l12b_gatefail.score (which
imports floorhighfastgate + floorhighsustaincond + floorhightiershape and
applies the wobble) + the ids tilt mirrored via _monthly_inside imported
from strat_l15b_insideday (champion term, pre-cap) + cap step mirrored
inline from strat_floorhightiershapeconc.score / strat_l13a_concwobble.score
/ strat_l15b_insideday.score (book-size composition, not an indicator).

PIT argument: NEEDS_DAILY loads the daily long panel (full window). ret_d
uses close_d and close_{d-1} of the SAME symbol (shift within symbol over
dates sorted ascending); vol_d is a rolling window ENDING at d-1 (shift
after rolling_std, inside over(symbol)) — no future bar. Daily bars are
grouped into calendar-month buckets with group_by_dynamic("1mo"); for
score row t (holding month starting months[t]) the newest bucket read is
t-1, whose bars all have date < months[t]; buckets t and later are never
touched. The percentile at row t uses only that backward window. Rows
t < jc_lb and names with no classified bars keep tilt exactly 1.0 —
eligibility and rank unmodified, nothing dropped on missing data, nothing
peeks. `close` is split-adjusted (no fake gaps on ex-dates); ex-dividend
days can print small negative gaps that at most remove one bar from the
jump count — the up-day statistic is robust to it.

Off-switch identity: jc_w = 0.0 (default) skips the tilt block, so `out`
is bitwise the ids-tilted gatefail lift and the mirrored cap yields
bitwise the champion's scores at the same params. Imported defaults leak:
gatefail's own gf_w default (0.05) is neutralised — this file setdefaults
gf_w = 0.0 / gw_w = 0.0 BEFORE delegating, so the off-switch is exact and
the champion's gw_w 0.15 / ids_w -0.13 must be PASSED by the caller.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / fwd +48.973% /
fwd DD -12.311% / fwd bench +14.717%.

PROMOTION PRECONDITION (Loop-16 lesson): the tilt re-orders the top-15 cut
(a book-composition mechanism) — count the decision months where the
candidate's picks differ from the champion's before believing any gain.

Falsifier: if every tested (jc_k, jc_lb, jc_w) combination trails the flat
base — train +96.882% / DD -17.032% / calmar 5.688 — then tail-exceedance
counts carry no selection information beyond the champion chain (ids term
included), and the jump-count axis closes at this base. A train gain that
coincides with forward/DD deterioration keeps the family's known failure
shape (the tape axis is saturated); record it, never promote it.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key passed via params-json, this file does
        not consume it)
        + jc_k {1.5, 2.0} (jump threshold in trailing daily sigmas)
        + jc_lb {3, 6} (window in monthly buckets ending at the print month)
        + jc_w {-0.2, -0.1, +0.1, +0.2} (percentile tilt; 0.0 = off-switch;
          positive = favour jump-dense tapes)
        + vol_lb 60 (internal trailing-vol window, documented, not swept).
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside

NEEDS_DAILY = True  # ids tilt (champion) and this file's signal read daily

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
    "jc_k": [1.5, 2.0],
    "jc_lb": [3, 6],
    "jc_w": [-0.2, -0.1, 0.1, 0.2],
}


def _monthly_jump(daily: pl.DataFrame, months, cols, k: float,
                  vol_lb: int = 60) -> np.ndarray:
    """Per (calendar month, stock) the share of bars whose return exceeded
    k x the trailing vol_lb-bar sigma (window ending at the PRIOR bar);
    NaN where the bucket had no classified bars."""
    d = daily.sort("symbol", "date")
    d = d.with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
    d = d.with_columns(
        pl.when(pl.col("pc").is_not_null() & (pl.col("pc") > 0))
          .then(pl.col("close") / pl.col("pc") - 1.0)
          .otherwise(None)
          .cast(pl.Float64).alias("ret"))
    # rolling std over the trailing vol_lb returns, then shift(1): bar d's
    # vol covers d-vol_lb .. d-1. min_samples defaults to window_size, so
    # classification is undefined until vol_lb bars exist (warm-up guard).
    d = d.with_columns(
        pl.col("ret").rolling_std(window_size=vol_lb).shift(1)
          .over("symbol").alias("vol"))
    d = d.with_columns(
        pl.when(pl.col("vol").is_not_null() & (pl.col("vol") > 0.0))
          .then(pl.col("ret") > (k * pl.col("vol")))
          .otherwise(None)
          .cast(pl.Float64).alias("jmp"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("jmp").mean())
          .sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="jmp").sort("date")
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
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
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

    jc_w = float(params.get("jc_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    if jc_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        jlb = int(params.get("jc_lb", 3))
        jk = float(params.get("jc_k", 1.5))
        J = _monthly_jump(daily, months, cols, jk)
        for t in range(1, out.shape[0]):
            lo = t - jlb
            if lo < 0:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                share = np.nanmean(J[lo:t], axis=0)
            valid = np.isfinite(share)
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = share[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + jc_w * (2.0 * pct - 1.0)
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
