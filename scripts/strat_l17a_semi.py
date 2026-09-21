"""Candidate: semi-deviation ratio tilt on the champion book
(strategy_lab contract) — Loop-17 designer A, price-path structure axis.

Setup in words: the CURRENT champion chain (strat_l13a_concwobble at
lookback 12: floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure with tier 0.9999,
regime-conditional book cap cap_weak/cap_full, eligibility-wobble discount
gw_w 0.15 / gf_lb 12) carrying the inside-day pause-share tilt ids_lb 3 /
ids_w -0.13 (strat_l15b_insideday, the live champion) is composed exactly
as the L15/L16 files compose it: strat_l12b_gatefail.score imports the
lift, the ids tilt is RE-APPLIED with `_monthly_inside` IMPORTED from the
frozen strat_l15b_insideday (identical percentile machinery, identical
pre-cap application point), then ONE NEW daily-path signal re-weights the
book BEFORE the regime-conditional cap step (mirrored inline, a
composition step, not an indicator). The new signal: the name's
VOLATILITY ASYMMETRY — whether its day-to-day VARIANCE is produced by
down moves or up moves. Per daily bar and symbol:

    lr_d = ln(close_d / close_{d-1})          (log return)

Per calendar-month bucket, over the bucket's bars:

    Sd    = sum of min(lr, 0)^2      (downside squared moves)
    Su    = sum of max(lr, 0)^2      (upside squared moves)
    s_m   = Sd / Su                  (semi-deviation ratio)

s_m > 1 = the name's variance is downside-dominated (grind-down /
distribution tape); s_m < 1 = upside-dominated (lottery / markup tape);
s_m = 0 is a bucket with no down move at all (kept — a legitimate
extreme); buckets with fewer than 10 returns (fixed guard, not searched)
or Su = 0 read NaN. Averaged over the `sem_lb` monthly buckets ending at
bucket t-1 (the house convention — the calendar month before the holding
month). Among names with a finite value in the row it is
percentile-ranked into pct in [0, 1] (higher = more downside-dominated):

    tilt = 1 + sem_w * (2 * pct - 1)   # sem_w > 0 favours downside-
    out  = current score * tilt        # dominated tapes, < 0 favours
                                       # upside-dominated; NaN keeps 1.0

Hypothesis: the champion buys fresh 12-month-high printers; its live
ids term rewards directional extension of the tape. Which SIDE carries
the variance is the untested half of that physics. An upside-dominated
tape is one where the biggest moves are the advances — accumulation
paying up, classic right-tail momentum quality; a downside-dominated
tape among fresh-high names is one that grinds up on small moves and
drops hard — fragile highs prone to air pockets. If upside-variance-
dominated printers continue better, sem_w < 0 adds train; if downside-
dominated names are the ones whose highs hold (deep, well-supported
books), sem_w > 0. If the rank, gates and ids term already price the
tape's asymmetry, every variant ties the champion and the channel
closes. BOTH signs are swept because the literature points both ways
(lottery-demand overpricing vs downside-risk premium).

Falsifier: sem_w 0.0 must reproduce the champion EXACTLY (train
+96.882% / DD -17.032% / calmar 5.688, fwd +48.973% / fwd DD -12.311% /
fwd bench +14.717%). The channel falsifies if no tested (sem_lb, sem_w)
cell beats train +96.882% within the 2pp DD slack (DD >= -19.032%).
Carried warning: seven per-name tape/return-shape families re-based onto
this champion across Loops 15-16 were train-destructive in both
directions, and three of Designer A's four earlier Loop-17 files
(timesince, rev36, rangeac, last5) fired the same way — the prior is
strongly that the ids term has soaked up the tape axis; a live result
must beat that prior, not just tie.

Import chain: strat_l17a_semi -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> ids tilt re-applied with
`strat_l15b_insideday._monthly_inside` IMPORTED (frozen file; reuse,
never reimplement; application block line-for-line its own score()) ->
semi-deviation term is NEW math (signed split of squared log returns,
monthly cross sums, ratio) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score (identical loop: cap = cap_full where exposure
>= 1.0 else cap_weak; lower ranks set NaN after a stable descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window —
handled as follows). lr_d uses close_d and close_{d-1} of the SAME
symbol (shift within symbol over dates sorted ascending) — no future
bar. Buckets are calendar months via group_by_dynamic("1mo"); each
bucket's Sd/Su use only its own bars. For score row t (holding month
starting months[t]) the newest bucket read is bucket t-1, whose bars all
have date in [months[t-1], months[t]) — every bar read is strictly
BEFORE months[t]; buckets t and later are never touched, so the fact
that `daily` covers the full panel window is harmless. The percentile at
row t uses only s values from that same backward window. Rows with
insufficient history (t < sem_lb), names with no returns in the window,
and buckets failing the 10-return guard read NaN and keep tilt exactly
1.0 — eligibility and rank unmodified, nothing dropped on missing data,
nothing peeks. The cap reads month-t ranks only.

Off-switch identity (two levels): (1) sem_w = 0.0 leaves the ids tilt
exactly as the champion applies it and the mirrored cap bitwise
unchanged, so the flat base IS the champion at the champion params (the
ids application here is line-for-line strat_l15b_insideday's own: same
nanmean window, same stable-argsort percentile, same np.where). (2)
ids_w 0.0 AND sem_w 0.0 at otherwise champion keys reproduce the
wobble-only chain at gw_w 0.15: documented Loop-15 measurement gw 0.15
alone -> train +87.00 / DD -17.34. NOTE imported defaults leak:
strat_l12b_gatefail's own default is gf_w = 0.05 — this file setdefaults
gf_lb = 12 / gf_w = 0.0 / gw_w = 0.0 BEFORE delegating, so the off-switch
is exact and the champion's gw_w 0.15 and ids keys (ids_lb 3 / ids_w
-0.13) must be PASSED by the caller (champion keys, not defaults here).
This file's own defaults are NEUTRAL: sem_w 0.0 (sem_lb 3 is inert while
the weight is 0).

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art in the mechanism inventory — the
DEAD daily-skewness family (strat_l16a_dskew, Loop-16: train 74.4-78.0,
both signs), whose own novelty statement reserved "any higher moment of
the daily return distribution". The ONE thing changed: the MOMENT ORDER
AND ESTIMATOR. Skewness is the CENTERED, STANDARDIZED THIRD moment — a
sample statistic dominated by its rarest, largest observations (cubic
weighting: one 10-sigma print can flip a bucket's sign) — while the
semi-deviation ratio is an UNCENTERED SECOND-moment split: the ratio of
aggregate downside to aggregate upside squared moves across ALL
sessions, no centering, no standardization, bounded below by 0 and
robust to single outliers. Concrete disagreement case: a name whose
skew is set by one exceptional +10% print reads strongly positive to
dskew while its day-in-day-out variance remains downside-dominated
(many moderate down days vs that single up day) — dskew ranks it at the
lottery end, this file ranks it at the distribution end; the two order
the book differently wherever tail outliers and typical-session variance
disagree. It is not range compression (rngcomp — UNSIGNED magnitude
level; the split by SIGN is invisible to it), not inside-day count
(ids — containment boolean), not volatility level or targeting (DEAD —
unsigned, no side), not CLV (within-day location — DEAD): the signed
SECOND-moment split of the daily return distribution is a variable no
file in the chain and no inventory family consumes.

SPACE = my keys: sem_lb {3, 6} (window in monthly buckets ending at the
        print month), sem_w {-0.2, -0.1, +0.1, +0.2} (percentile tilt;
        0.0 = off-switch; positive = favour downside-variance-dominated
        tapes, negative = favour upside-dominated). The 10-returns-per-
        bucket guard is FIXED (not searched). Champion keys pinned
        (passed by the caller, docs only): b_hi 0.69, b_lo 0.45, b_mid
        0.55, floor_lb 19, lookback 12, max_dist 0.055, regime_ma 18,
        fast_ma 5, sustain_lo 3, sustain_hi 2, tier_lo 0.9999, tier_mid
        0.9999, cap_weak 11, cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15,
        ids_lb 3, ids_w -0.13. max_hold 3 is a HARNESS key passed via
        params-json; this file does not consume it.

Designer smoke observations (Loop-17, pre-freeze, nse_all top 15 25bps
split 2022-01-01, isolated ledger l17_dA): off-switch reproduced the
champion EXACTLY — train +96.88 / DD -17.03 / calmar 5.688, fwd +48.97 /
-12.31 (H1 +98.3 / H2 +95.5). sem_lb 3: sem_w -0.2 (upside-variance-
dominated tapes) -> train +72.79 / DD -22.11 / calmar 3.29, fwd +64.42 /
-16.86; sem_w +0.2 (downside-dominated) -> train +81.04 / DD -24.51 /
calmar 3.31, fwd +56.41 / -20.11. BOTH signs 16-24pp below the champion
on train with worse DD — dskew's falsification extends to the second-
moment split of the same distribution. The -0.2 arm posts the by-now
familiar forward-heavy tape print (fwd +64.42 at train +72.79), joining
rngcomp / serpers-choppy / rangeac+0.2 / last5+0.2 on the never-promoted
forward-geometry list. Falsifier FIRED on both signs: volatility
asymmetry is closed on this base; do not spend worker windows on
sem_lb 6 or intermediate weights.
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside

NEEDS_DAILY = True
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
    "sem_lb": [3, 6],
    "sem_w": [-0.2, -0.1, 0.1, 0.2],
}

_MIN_RETS = 10  # fixed: minimum returns per monthly bucket


def _pivot_field(g: pl.DataFrame, field: str, months, cols) -> np.ndarray:
    """Pivot one field of a (symbol, date, ...) bucket aggregate into the
    months x stocks matrix aligned with `months`/`cols` (the
    _monthly_inside pattern, shared by every file on this chain)."""
    piv = (g.select("symbol", "date", field)
             .pivot(on="symbol", index="date", values=field).sort("date"))
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


def _monthly_semi(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month, stock): downside/upside semi-deviation ratio
    over the bucket's log returns; NaN where fewer than _MIN_RETS returns
    or no upside variance at all."""
    d = daily.with_columns(
        pl.col("close").shift(1).over("symbol").alias("pc"))
    d = d.with_columns(
        pl.when(pl.col("close").is_not_null() & pl.col("pc").is_not_null()
                & (pl.col("close") > 0.0) & (pl.col("pc") > 0.0))
          .then((pl.col("close") / pl.col("pc")).log())
          .otherwise(None)
          .alias("lr"))
    d = d.filter(pl.col("lr").is_not_null())
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.len().alias("n"),
               (pl.min_horizontal(pl.col("lr"), pl.lit(0.0)) ** 2)
               .sum().alias("sd"),
               (pl.max_horizontal(pl.col("lr"), pl.lit(0.0)) ** 2)
               .sum().alias("su"))
          .sort("symbol", "date"))
    g = g.with_columns(
        pl.when((pl.col("n") >= _MIN_RETS) & (pl.col("su") > 0.0))
          .then(pl.col("sd") / pl.col("su"))
          .otherwise(None)
          .alias("s"))
    return _pivot_field(g, "s", months, cols)


def _tilt_rows(stat: np.ndarray, target: np.ndarray, src: np.ndarray,
               lb: int, w: float) -> None:
    """Apply the percentile tilt of backward-window means of `stat` onto
    `target` rows, reading the base values from `src` (the
    strat_l15b_insideday application block, verbatim mechanics)."""
    for t in range(1, target.shape[0]):
        lo = t - lb
        if lo < 0:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            val = np.nanmean(stat[lo:t], axis=0)
        valid = np.isfinite(val)
        n = int(valid.sum())
        tilt = np.ones(target.shape[1])
        if n >= 5:
            sv = val[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt[valid] = 1.0 + w * (2.0 * pct - 1.0)
        ok = np.isfinite(src[t])
        target[t] = np.where(ok, src[t] * tilt, np.nan)


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into the off-switch. Champion values are passed, not defaulted.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, exposure = _gf_score(panels, p)
    base = np.array(lift, dtype=float, copy=True)
    out = np.array(base, dtype=float, copy=True)

    ids_w = float(params.get("ids_w", 0.0))
    if ids_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        ilb = int(params.get("ids_lb", 3))
        IDS = _monthly_inside(daily, months, cols)
        _tilt_rows(IDS, out, base, ilb, ids_w)

    sem_w = float(params.get("sem_w", 0.0))
    if sem_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        lb = int(params.get("sem_lb", 3))
        S = _monthly_semi(daily, months, cols)
        _tilt_rows(S, out, out, lb, sem_w)

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
