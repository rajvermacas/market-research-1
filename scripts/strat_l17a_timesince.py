"""Candidate: time-under-water tilt on the champion book (strategy_lab
contract) — Loop-17 designer A, price-path structure axis.

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
composition step, not an indicator). The new signal: how much of the
trailing year the name spent BELOW its own running peak. Per daily bar
and symbol, over a fixed 252-session rolling window (min_samples 63, not
searched):

    pk_d  = max(close over the trailing 252 sessions of the symbol)
    dd_d  = close_d / pk_d - 1        (in (-1, 0]; 0 exactly on new highs)

Per calendar-month bucket m, one of two statistics (tuw_mode):

    depth: tuw_m = mean over the bucket's bars of (-dd_d)   >= 0
           (mean fractional depth below the running peak)
    frac:  tuw_m = mean over the bucket's bars of 1[dd_d < 0] in [0, 1]
           (share of sessions strictly below the peak)

Averaged over the `tuw_lb` monthly buckets ending at bucket t-1 (the
calendar month before the holding month — the house convention). Among
names with a finite value in the row it is percentile-ranked into pct in
[0, 1] (higher = more/longer under water):

    tilt = 1 + tuw_w * (2 * pct - 1)   # tuw_w > 0 favours deep/long
    out  = current score * tilt        # under-water histories; < 0 favours
                                       # continuous grinds; NaN keeps 1.0

Hypothesis: the champion buys fresh 12-month-high printers, and its own
eligibility gate (max_dist 0.055) consumes the CURRENT distance below the
52-week high. The WINDOW-AVERAGE depth below the running peak is a
different object: it is the integral of the path BETWEEN highs. Two names
can both sit 2% under their high today — identical to the gate, to the
fresh-print rank, and to every monthly-close quantity — while one never
left the peak all year (a continuous grind) and the other surfaced from a
30% drawdown (a base-breaker whose supply was absorbed on the way up).
Classic base-breaking work treats a long, deep base as better
risk/reward per breakout; trend work prefers the uninterrupted grind.
Which quality continues better on this book is exactly what the screen
answers: tuw_w > 0 backs the surfacers, tuw_w < 0 the grinders. If the
short-trend/continuity gates plus the ids term already encode path
quality, every variant ties the champion and the channel closes.

Falsifier: tuw_w 0.0 must reproduce the champion EXACTLY (train +96.882%
/ DD -17.032% / calmar 5.688, fwd +48.973% / fwd DD -12.311% / fwd bench
+14.717%). The channel falsifies if no tested (tuw_lb, tuw_mode, tuw_w)
cell beats train +96.882% within the 2pp DD slack (DD >= -19.032%).
Known-construct warning carried from Loops 15/16: daily-tape tilts on
this book have been train-destructive in both directions more often than
not (rngcomp, seasonality, monpath, dskew, volpart) — a result showing
BOTH signs harming train closes the channel as a double-count of tape
quality the ids term already prices.

Import chain: strat_l17a_timesince -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> ids tilt re-applied with
`strat_l15b_insideday._monthly_inside` IMPORTED (frozen file; reuse,
never reimplement; application block line-for-line its own score()) ->
time-under-water term is NEW math (rolling per-symbol peak, daily
drawdown depth, monthly-bucket means) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score (identical loop: cap = cap_full where exposure
>= 1.0 else cap_weak; lower ranks set NaN after a stable descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window —
handled as follows). pk_d is a per-symbol ROLLING max over PAST sessions
only; dd_d uses close_d and pk_d of the SAME symbol — no future bar.
Daily bars are grouped into calendar-month buckets with
group_by_dynamic("1mo"); each bucket's statistic uses only its own bars.
For score row t (holding month starting months[t]) the newest bucket read
is bucket t-1, whose bars all have date in [months[t-1], months[t]) —
every bar read is strictly BEFORE months[t]; buckets t and later are
never touched, so the fact that `daily` covers the full panel window is
harmless. The percentile at row t uses only tuw values from that same
backward window. Rows with insufficient history (t < tuw_lb), names with
no bars in the window, and names younger than the 63-session
min_samples of the rolling peak read NaN and keep tilt exactly 1.0 —
eligibility and rank unmodified, nothing dropped on missing data,
nothing peeks. The cap reads month-t ranks only.

Off-switch identity (two levels): (1) tuw_w = 0.0 leaves the ids tilt
exactly as the champion applies it and the mirrored cap bitwise
unchanged, so the flat base IS the champion at the champion params (the
ids application here is line-for-line strat_l15b_insideday's own: same
nanmean window, same stable-argsort percentile, same np.where). (2)
ids_w 0.0 AND tuw_w 0.0 at otherwise champion keys reproduce the
wobble-only chain at gw_w 0.15: documented Loop-15 measurement gw 0.15
alone -> train +87.00 / DD -17.34. NOTE imported defaults leak:
strat_l12b_gatefail's own default is gf_w = 0.05 — this file setdefaults
gf_lb = 12 / gf_w = 0.0 / gw_w = 0.0 BEFORE delegating, so the off-switch
is exact and the champion's gw_w 0.15 and ids keys (ids_lb 3 / ids_w
-0.13) must be PASSED by the caller (champion keys, not defaults here).
This file's own defaults are NEUTRAL: tuw_w 0.0 (tuw_lb 3 / tuw_mode
"depth" are inert while the weight is 0).

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art in the mechanism inventory — (a) the
DEAD drought-shape tilts (strat_l12b_droughtshape, strat_l13b_concdrought,
and the Loop-14 freshness/drought re-bases): monthly-frequency patterns in
the SPACING of fresh prints (time between monthly highs); (b) 52w-high
proximity (DEAD — and the point-in-time distance below the high is
anyway the champion's own max_dist gate). The ONE thing changed: the
signal is the DAILY-PATH INTEGRAL BELOW THE RUNNING PEAK across the whole
window — average depth (a magnitude) or share of sessions below (a
duration) — a property of the path BETWEEN highs that no monthly-close
quantity, no print-spacing measure, and no current-proximity gate can
express. Concrete disagreement case: a name that ground sideways-to-up
all year and a name that crashed 30% and spent eight months recovering
are IDENTICAL to drought-shape (both print monthly highs at the same
cadence recently) and IDENTICAL to the proximity gate (both 2% under the
high today); they are OPPOSITE extremes on time-under-water. It is not
drawdown at the book level (index-DD veto — DEAD, market index), not
volatility level (rngcomp — DEAD, range vs own baseline), not inside-day
counts (ids — LIVE, session containment), not CLV (intra-day location —
DEAD): the running-peak drawdown integral is a variable nothing in the
chain consumes.

SPACE = my keys: tuw_lb {3, 6} (window in monthly buckets ending at the
        print month), tuw_w {-0.2, -0.1, +0.1, +0.2} (percentile tilt;
        0.0 = off-switch; positive = favour deep/long under-water
        histories, negative = favour continuous grinds), tuw_mode
        {"depth", "frac"} (mean depth below peak vs share of sessions
        below peak). The 252-session peak window and its 63-session
        min_samples are FIXED (not searched — they define "52-week
        peak", the object the hypothesis is about). Champion keys pinned
        (passed by the caller, docs only): b_hi 0.69, b_lo 0.45, b_mid
        0.55, floor_lb 19, lookback 12, max_dist 0.055, regime_ma 18,
        fast_ma 5, sustain_lo 3, sustain_hi 2, tier_lo 0.9999, tier_mid
        0.9999, cap_weak 11, cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15,
        ids_lb 3, ids_w -0.13. max_hold 3 is a HARNESS key passed via
        params-json; this file does not consume it.

Designer smoke observations (Loop-17, pre-freeze, nse_all top 15 25bps
split 2022-01-01, isolated ledger l17_dA): off-switch reproduced the
champion EXACTLY — train +96.88 / DD -17.03 / calmar 5.688, fwd +48.97 /
-12.31 (H1 +98.3 / H2 +95.5). tuw_lb 3 / tuw_mode depth: tuw_w -0.2
(grinders) -> train +74.58 / DD -20.16 / calmar 3.70, fwd +49.20 / -15.18;
tuw_w +0.2 (surfacers) -> train +79.48 / DD -21.46 / calmar 3.70, fwd
+56.43 / -20.52. BOTH signs are 17-22pp below the champion on train and
worsen DD — the base-breaker story AND the grind story both lose; the
fresh-print rank plus the ids term already order the cut better than
drawdown-history does. The surfacer arm is the better forward print
(+56.43) but blows the forward DD (-20.52). Falsifier FIRED: the
time-under-water channel is closed on this base at both signs; do not
spend worker windows on intermediate |tuw_w| (they interpolate toward the
champion, never above it — the Loop-16 monpath pattern) or on tuw_lb 6 /
frac mode (same statistic family, weaker case than the smoked cells).
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
    "tuw_lb": [3, 6],
    "tuw_w": [-0.2, -0.1, 0.1, 0.2],
    "tuw_mode": ["depth", "frac"],
}

_PK_WINDOW = 252      # fixed: the hypothesis is about the 52-week peak
_PK_MIN = 63          # fixed: min_samples so young names still get a peak


def _pivot_buckets(g: pl.DataFrame, months, cols) -> np.ndarray:
    """Pivot a (symbol, date, value) bucket aggregate into the months x
    stocks matrix aligned with `months`/`cols` (the _monthly_inside
    pattern, shared by every file on this chain)."""
    piv = g.pivot(on="symbol", index="date", values=g.columns[-1]).sort("date")
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


def _monthly_tuw(daily: pl.DataFrame, months, cols, mode: str) -> np.ndarray:
    """Per (calendar month, stock): mean depth below the running 252-session
    peak ('depth') or share of sessions below it ('frac'); NaN where the
    bucket had no bars or no peak yet."""
    d = daily.with_columns(
        pl.col("close")
        .rolling_max(_PK_WINDOW, min_samples=_PK_MIN)
        .over("symbol")
        .alias("pk"))
    d = d.with_columns(
        pl.when(pl.col("pk").is_not_null() & pl.col("close").is_not_null())
          .then(pl.col("close") / pl.col("pk") - 1.0)
          .otherwise(None)
          .alias("dd"))
    if mode == "frac":
        expr = (pl.col("dd") < 0.0).cast(pl.Float64)
    else:
        expr = (-pl.col("dd")).cast(pl.Float64)
    g = (d.with_columns(expr.alias("stat"))
          .group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("stat").mean())
          .sort("symbol", "date"))
    return _pivot_buckets(g, months, cols)


def _tilt_rows(stat: np.ndarray, target: np.ndarray, src: np.ndarray,
               lb: int, w: float) -> None:
    """Apply the percentile tilt of backward-window means of `stat` onto
    `target` rows, reading the base values from `src` (the
    strat_l15b_insideday application block, verbatim mechanics: window
    [t-lb, t), nanmean, stable-argsort percentile, np.where on finite
    src)."""
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

    tuw_w = float(params.get("tuw_w", 0.0))
    if tuw_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        mode = str(params.get("tuw_mode", "depth"))
        lb = int(params.get("tuw_lb", 3))
        TUW = _monthly_tuw(daily, months, cols, mode)
        _tilt_rows(TUW, out, out, lb, tuw_w)

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
