"""Candidate: windowed max-drawdown stress tilt on the champion book
(strategy_lab contract).

Setup in words: the CURRENT champion chain (strat_l12b_gatefail.score:
floor-lift fresh-print rank among short-trend-passing, print-continuity-
passing names, breadth tiers, eligibility-wobble) carrying the champion's
inside-day tilt (ids_lb 3 / ids_w -0.13, helper imported from
strat_l15b_insideday and mirrored pre-cap exactly as strat_l17b_crowd
mirrors it) is re-weighted, BEFORE the regime-conditional cap step (mirrored
inline), by a NEW daily-path signal: the name's DEEPEST DRAWDOWN within the
recent window, benchmarked against the panel's stress in the same window.
Per daily bar and symbol, over the running peak of closes:

    dd_d  = 1 - close_d / cummax(close)_d      (cummax over the loaded
                                                daily history per symbol)

Per calendar-month bucket the bucket's max dd; over the rl_lb monthly
buckets ending at the print month (the calendar month before the holding
month) the WINDOW statistic is the max of those — the deepest peak-to-
trough point in the window. The panel-relative form is

    rel[t,j] = DDW[t,j] - median_j'( DDW[t,j'] )   (cross-sectional, row t)

Hypothesis: every eligible name sits AT a fresh 12-month high (current dd ~
0), so the only path information left is the road INTO the high. Two
opposite stories: (a) rl_w > 0 — a deep drawdown inside the window that has
already healed into a fresh high is a V-recovery: sellers exhausted, every
holder in profit, maximum relief-rally character; (b) rl_w < 0 — a shallow
path is the clean grinder; crash-recovered names are falling knives that
found a bid, not trends. If the window's deepest point adds nothing beyond
the champion chain (and beyond the l17a_timesince integral that already
failed), every variant ties the base and the channel closes.

NOVELTY STATEMENT (closest registry rows + the one thing changed):
- strat_l17a_timesince (DEAD, 74.6-86.2): the CLOSEST prior art — the
  daily-path integral below the peak (sum of dd over bars = depth x
  DURATION). This file's statistic is the MAX dd in the window — the
  deepest POINT. The two orderings disagree on disjoint cases: a V-bottom
  (deep, brief) scores high on max-dd and low on the integral; a slow
  shallow bleed (never deep, always under) scores low on max-dd and high on
  the integral. The timesince falsifier (integral, off-switch dominated)
  therefore cannot bind the max functional; if the answer is the same, the
  path-stress axis closes on BOTH functionals.
- strat_l14b_relstrength / l16b_outrank (PARTIAL/DEAD): rs compares
  ENDPOINT return levels to the panel; a name can have rs strongly positive
  while carrying a deep mid-window drawdown, and vice versa — endpoint
  statistics cannot see the path.
- strat_l17b_beta / l17b_idvol (DEAD): second-moment decompositions vs the
  panel (correlation x relative vol; 1-R^2) — variance, not path depth.
- strat_l17a_rangeac / l15b_rngcomp / insideday: range/volatility shape of
  bars, not position relative to the running peak.
The one thing changed: the deepest peak-to-trough POINT within the trailing
window, cross-sectionally benchmarked to the panel's own stress in the same
window. HONEST CAVEAT (stated because the brief asks for the median
subtraction): the tilt is a per-row cross-sectional PERCENTILE rank, and
subtracting a row-constant median is an order-preserving shift — the
tilt's ordering is identical to ranking the raw windowed max-dd. The
median term is kept because the brief defines the statistic that way and
because the LEVEL (rel) is what a later gate would consume; for this
file's rank tilt the benchmarking is interpretive, and the tested signal is
the windowed max-dd functional itself.

Import chain: strat_l17d_reldd -> strat_l12b_gatefail.score (which imports
floorhighfastgate + floorhighsustaincond + floorhightiershape and applies
the wobble) + the ids tilt mirrored via _monthly_inside imported from
strat_l15b_insideday (champion term, pre-cap) + cap step mirrored inline
from strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score (book-size composition, not an indicator).

PIT argument: NEEDS_DAILY loads the daily long panel (full window).
cummax(close) is a backward running maximum per symbol over dates sorted
ascending — bar d's dd uses bars <= d only, no future bar; the peak's
memory starts at the first loaded bar (2000-era for old listings), the
longest history available, identical for all names. Buckets are calendar
months via group_by_dynamic("1mo"); for score row t (holding month starting
months[t]) the newest bucket read is t-1, whose bars all have date <
months[t]; the window max reads buckets [t-rl_lb, t) and the row-t median
uses only those same window values. Rows t < rl_lb and names with no bars
in the window keep tilt exactly 1.0 — eligibility and rank unmodified,
nothing dropped on missing data, nothing peeks. `close` is split-adjusted,
so splits do not fabricate a drawdown; dividends are ignored in the depth
(one bar among ~63 per bucket).

Off-switch identity: rl_w = 0.0 (default) skips the tilt block, so `out`
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

Falsifier: if every tested (rl_lb, rl_w) combination trails the flat base —
train +96.882% / DD -17.032% / calmar 5.688 — then the windowed max-dd
path-stress functional carries no selection information beyond the champion
chain (and, combined with l17a_timesince, the daily path-stress axis is
closed on BOTH the integral and the max functional at this base). A train
gain that coincides with forward/DD deterioration keeps the family's known
failure shape; record it, never promote it.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key passed via params-json, this file does
        not consume it)
        + rl_lb {3, 6} (window in monthly buckets ending at the print month)
        + rl_w {-0.2, -0.1, +0.1, +0.2} (percentile tilt; 0.0 = off-switch;
          positive = favour deep-then-recovered paths, negative = favour
          shallow grinders).
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
    "rl_lb": [3, 6],
    "rl_w": [-0.2, -0.1, 0.1, 0.2],
}


def _monthly_maxdd(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month, stock) the bucket's max drawdown depth
    1 - close / running peak of closes (per symbol, over the loaded daily
    history); NaN where the bucket had no bars."""
    d = daily.sort("symbol", "date")
    d = d.with_columns(pl.col("close").cum_max().over("symbol").alias("pk"))
    d = d.with_columns(
        pl.when(pl.col("pk") > 0)
          .then(1.0 - pl.col("close") / pl.col("pk"))
          .otherwise(None)
          .cast(pl.Float64).alias("dd"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("dd").max())
          .sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="dd").sort("date")
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

    rl_w = float(params.get("rl_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    if rl_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        rlb = int(params.get("rl_lb", 3))
        DD = _monthly_maxdd(daily, months, cols)  # per-bucket max dd
        for t in range(1, out.shape[0]):
            lo = t - rlb
            if lo < 0:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                ddw = np.nanmax(DD[lo:t], axis=0)      # deepest point in window
                med = np.nanmedian(ddw)                # panel stress, same window
            rel = ddw - med                            # row-constant shift (see
            valid = np.isfinite(rel)                   # docstring caveat)
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = rel[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + rl_w * (2.0 * pct - 1.0)
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
