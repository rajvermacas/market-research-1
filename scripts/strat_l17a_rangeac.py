"""Candidate: range-ratio serial-correlation tilt on the champion book
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
composition step, not an indicator). The new signal: the SERIAL
CORRELATION of the name's daily range series — is the tape's volatility
PERSISTENT (wide days follow wide days: clustering, a regime in progress)
or ALTERNATING (burst-pause-burst: churn)? Per daily bar and symbol:

    pc_d = close_{d-1}                       (same symbol, prior bar)
    tr_d = max(high_d - low_d,
               |high_d - pc_d|, |low_d - pc_d|)     (true range)
    x_d  = tr_d / close_d                (normalized true range, unitless)

Over ADJACENT pairs (x_{d-1}, x_d) within each calendar-month bucket
(the pair spanning a bucket boundary lands in the bucket of its second
element, as in serpers), the bucket's lag-1 Pearson autocorrelation:

    n   = paired bars in the bucket
    AC  = (Sxy - Sx*Sy/n)
          / sqrt((Sxx - Sx^2/n) * (Syy - Sy^2/n))

with Sx, Sxx, Sy, Syy, Sxy the paired-row sums of x, x^2, y, y^2, x*y
(y = x shifted one bar). Buckets with fewer than 10 paired bars (fixed
guard, not searched) or a non-positive variance read NaN. Averaged over
the `rac_lb` monthly buckets ending at bucket t-1 (the house convention
— the calendar month before the holding month). Among names with a
finite value in the row it is percentile-ranked into pct in [0, 1]
(higher = more persistent range):

    tilt = 1 + rac_w * (2 * pct - 1)   # rac_w > 0 favours clustered/
    out  = current score * tilt        # persistent-vol printers, < 0
                                       # favours burst-pause churn; NaN
                                       # keeps tilt 1.0

Hypothesis: the champion buys fresh 12-month-high printers and its one
LIVE daily-tape term rewards FEWER inside days — sessions that failed to
extend the prior range, i.e. alternation. Range serial correlation is
the continuous, magnitude-side counterpart: a tape whose wide days
cluster is in an active volatility regime (accumulation and markup
arrive in runs, and a breakout printed inside a clustering regime has
fuel), while a tape whose wide days alternate with dead ones is churn —
the ids count sees the dead sessions, this sees whether the LIVE
sessions sustain each other. If range persistence adds information the
inside-day count does not carry, rac_w > 0 adds train (and < 0 tests the
churn-favours-the-print converse); if the ids term already encodes the
alternation structure completely, every variant ties the champion and
the channel closes.

Falsifier: rac_w 0.0 must reproduce the champion EXACTLY (train
+96.882% / DD -17.032% / calmar 5.688, fwd +48.973% / fwd DD -12.311% /
fwd bench +14.717%). The channel falsifies if no tested (rac_lb, rac_w)
cell beats train +96.882% within the 2pp DD slack (DD >= -19.032%).
Carried warning: daily-tape tilts on this book have been
train-destructive in both directions more often than not (rngcomp,
monpath, dskew, volpart, timesince and rev36 this loop) — a
both-signs-harm result closes the channel as a double-count of tape
quality the ids term already prices.

Import chain: strat_l17a_rangeac -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> ids tilt re-applied with
`strat_l15b_insideday._monthly_inside` IMPORTED (frozen file; reuse,
never reimplement; application block line-for-line its own score()) ->
range serial-correlation term is NEW math (true-range pairs, monthly
cross-moment sums, within-bucket Pearson) -> cap step mirrored inline
from strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score (identical loop: cap = cap_full where
exposure >= 1.0 else cap_weak; lower ranks set NaN after a stable
descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window —
handled as follows). tr_d uses high/low of bar d and pc_d = close_{d-1}
of the SAME symbol (shift within symbol over dates sorted ascending) —
no future bar; pairs are between adjacent bars only. Daily bars are
grouped into calendar-month buckets with group_by_dynamic("1mo"); each
bucket's cross-moment sums use only its own paired rows. For score row t
(holding month starting months[t]) the newest bucket read is bucket t-1,
whose bars all have date in [months[t-1], months[t]) — every bar read is
strictly BEFORE months[t]; buckets t and later are never touched, so the
fact that `daily` covers the full panel window is harmless. The
percentile at row t uses only AC values from that same backward window.
Rows with insufficient history (t < rac_lb), names with no paired bars
in the window, and buckets failing the 10-pair guard read NaN and keep
tilt exactly 1.0 — eligibility and rank unmodified, nothing dropped on
missing data, nothing peeks. The cap reads month-t ranks only.

Off-switch identity (two levels): (1) rac_w = 0.0 leaves the ids tilt
exactly as the champion applies it and the mirrored cap bitwise
unchanged, so the flat base IS the champion at the champion params (the
ids application here is line-for-line strat_l15b_insideday's own: same
nanmean window, same stable-argsort percentile, same np.where). (2)
ids_w 0.0 AND rac_w 0.0 at otherwise champion keys reproduce the
wobble-only chain at gw_w 0.15: documented Loop-15 measurement gw 0.15
alone -> train +87.00 / DD -17.34. NOTE imported defaults leak:
strat_l12b_gatefail's own default is gf_w = 0.05 — this file setdefaults
gf_lb = 12 / gf_w = 0.0 / gw_w = 0.0 BEFORE delegating, so the off-switch
is exact and the champion's gw_w 0.15 and ids keys (ids_lb 3 / ids_w
-0.13) must be PASSED by the caller (champion keys, not defaults here).
This file's own defaults are NEUTRAL: rac_w 0.0 (rac_lb 3 is inert while
the weight is 0).

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art in the mechanism inventory — (a)
DEAD range compression (strat_l15b_rngcomp, Loop-16 re-based onto the ids
chain): the LEVEL of the name's normalized true range vs its own
trailing baseline — a magnitude, no time-ordering; (b) the LIVE
inside-day term (strat_l15b_insideday): a COUNT of sessions contained by
the prior session's range — pause frequency, no magnitude; (c) DEAD
serial-dependence sign-persistence (strat_l15b_serpers, Loop-15): serial
dependence of RETURN SIGNS (direction), a binary autocorrelation of the
signed sequence. The ONE thing changed: the serial dependence of the
range MAGNITUDE series itself — a continuous lag-1 autocorrelation of
normalized true ranges, sign-free and direction-free. Concrete
disagreement cases: a tape can trend day-to-day (high return-sign
persistence — serpers' variable) while its magnitude stays flat (zero
range autocorrelation); a burst-pause tape has strongly NEGATIVE range
autocorrelation under ANY return drift; and two names with the SAME
average range (identical to rngcomp) can sit at opposite extremes of
range persistence. No file in the chain or inventory consumes the
time-ordering of volatility magnitude. It is not vol-of-vol level, not
NR7 (a count of tight sessions — DEAD as range compression), not
inside-day variants beyond the live ids term: the ordering statistic of
the range series is new.

SPACE = my keys: rac_lb {3, 6} (window in monthly buckets ending at the
        print month), rac_w {-0.2, -0.1, +0.1, +0.2} (percentile tilt;
        0.0 = off-switch; positive = favour range-persistent /
        clustered-vol printers, negative = favour burst-pause churn).
        The 10-pairs-per-bucket guard is FIXED (not searched). Champion
        keys pinned (passed by the caller, docs only): b_hi 0.69, b_lo
        0.45, b_mid 0.55, floor_lb 19, lookback 12, max_dist 0.055,
        regime_ma 18, fast_ma 5, sustain_lo 3, sustain_hi 2, tier_lo
        0.9999, tier_mid 0.9999, cap_weak 11, cap_full 20, gf_lb 12,
        gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13. max_hold 3 is a
        HARNESS key passed via params-json; this file does not consume
        it.

Designer smoke observations (Loop-17, pre-freeze, nse_all top 15 25bps
split 2022-01-01, isolated ledger l17_dA): off-switch reproduced the
champion EXACTLY — train +96.88 / DD -17.03 / calmar 5.688, fwd +48.97 /
-12.31 (H1 +98.3 / H2 +95.5). rac_lb 3: rac_w +0.2 (persistent/
clustered vol) -> train +74.17 / DD -22.30 / calmar 3.33, fwd +64.37 /
-12.60; rac_w -0.2 (burst-pause churn) -> train +74.28 / DD -21.60 /
calmar 3.44, fwd +44.78 / -27.69. BOTH signs ~22pp below the champion on
train; the churn arm also destroys forward (fwd DD -27.69 ~ bench).
rac_w +0.2 repeats the range family's forward-heavy signature (fwd-calmar
5.11 vs champion 3.98 with fwd DD essentially unchanged) — alongside
rngcomp (fwd +60.94/-11.61) and serpers' choppy arm (fwd +69.55/-16.13),
vol-structure tilts keep buying forward risk-adjusted quality at train
cost; a forward-geometry stack candidate, never a train-ratchet one.
Falsifier FIRED on both signs: range serial correlation is closed on
this base for selection purposes; do not spend worker windows on
rac_lb 6 or intermediate weights.
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
    "rac_lb": [3, 6],
    "rac_w": [-0.2, -0.1, 0.1, 0.2],
}

_MIN_PAIRS = 10  # fixed: minimum paired bars per monthly bucket


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


def _monthly_rangeac(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month, stock): the lag-1 Pearson autocorrelation of
    the normalized true-range series within the bucket's paired bars;
    NaN where fewer than _MIN_PAIRS pairs or zero variance."""
    d = daily.with_columns(
        pl.col("close").shift(1).over("symbol").alias("pc"))
    d = d.with_columns(
        pl.max_horizontal(
            pl.col("high") - pl.col("low"),
            (pl.col("high") - pl.col("pc")).abs(),
            (pl.col("low") - pl.col("pc")).abs(),
        ).alias("tr"))
    d = d.with_columns(
        pl.when(pl.col("close") > 0.0)
          .then(pl.col("tr") / pl.col("close"))
          .otherwise(None)
          .alias("x"))
    d = d.with_columns(pl.col("x").shift(1).over("symbol").alias("y"))
    # paired rows only, so every sum below is over the SAME bar set
    d = d.filter(pl.col("x").is_not_null() & pl.col("y").is_not_null())
    d = d.with_columns(
        (pl.col("x") * pl.col("x")).alias("x2"),
        (pl.col("y") * pl.col("y")).alias("y2"),
        (pl.col("x") * pl.col("y")).alias("xy"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.len().alias("n"),
               pl.col("x").sum().alias("sx"),
               pl.col("y").sum().alias("sy"),
               pl.col("x2").sum().alias("sxx"),
               pl.col("y2").sum().alias("syy"),
               pl.col("xy").sum().alias("sxy"))
          .sort("symbol", "date"))
    N = _pivot_field(g, "n", months, cols).astype(float)
    SX = _pivot_field(g, "sx", months, cols)
    SY = _pivot_field(g, "sy", months, cols)
    SXX = _pivot_field(g, "sxx", months, cols)
    SYY = _pivot_field(g, "syy", months, cols)
    SXY = _pivot_field(g, "sxy", months, cols)
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = SXY - SX * SY / N
        vx = SXX - SX * SX / N
        vy = SYY - SY * SY / N
        den = np.sqrt(np.maximum(vx, 0.0) * np.maximum(vy, 0.0))
        ac = cov / den
    ok = (N >= _MIN_PAIRS) & (den > 0.0) & np.isfinite(ac)
    return np.where(ok, ac, np.nan)


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

    rac_w = float(params.get("rac_w", 0.0))
    if rac_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        lb = int(params.get("rac_lb", 3))
        AC = _monthly_rangeac(daily, months, cols)
        _tilt_rows(AC, out, out, lb, rac_w)

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
