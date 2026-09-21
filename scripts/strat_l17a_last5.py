"""Candidate: turn-of-month persistence tilt on the champion book
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
composition step, not an indicator). The new signal: how much of each
month's return this name SYSTEMATICALLY earns in the month's final
sessions — a persistent per-name turn-of-month timing fingerprint, not a
property of any single month. Per calendar-month bucket m and symbol,
with n_m the bucket's bar count and tom_k the session window (default 5):

    prev_m = close immediately BEFORE the bucket's first bar
    L_m    = last close of the bucket / close tom_k sessions before it
             - 1                    (the final tom_k sessions' return)
    R_m    = last close of the bucket / prev_m - 1   (the month's return)
    s_m    = ln(last/base) / ln(last/prev)

s_m is the LOG-SHARE of the month's move earned in its final tom_k
sessions (symmetric: a down month with a positive final week reads
negative; values beyond [-1, 1] mean the final window more than
accounted for the month). Buckets with n_m <= tom_k, any non-positive
price, or |monthly log move| < 0.01 (fixed robustness guard against
division noise — NOT searched) read NaN. Averaged over the `tom_lb`
monthly buckets ending at bucket t-1 (the house convention — the
calendar months before the holding month). Among names with a finite
value in the row it is percentile-ranked into pct in [0, 1] (higher =
gains systematically concentrated at the turn):

    tilt = 1 + tom_w * (2 * pct - 1)   # tom_w > 0 favours persistent
    out  = current score * tilt        # turn-of-month-strong names; NaN
                                       # keeps tilt 1.0

Hypothesis: in India a large, predictable flow lands at the turn of
every month — SIP instalments and mutual-fund allocations settle on
month-end dates, and FPI rebalancing clusters there. Names that
repeatedly absorb that flow show gains concentrating in the final
sessions of MANY consecutive months — a structural demand fingerprint,
not momentum (the rank already owns level) and not a within-month shape
of the current move. If persistent turn-of-month strength identifies
flow-supported names whose fresh prints hold, tom_w > 0 adds train; if
the final-week concentration is noise or already priced by the
fresh-print rank, every variant ties the champion and the channel
closes. tom_w < 0 tests the converse (front-loaded names continue
better).

Falsifier: tom_w 0.0 must reproduce the champion EXACTLY (train
+96.882% / DD -17.032% / calmar 5.688, fwd +48.973% / fwd DD -12.311% /
fwd bench +14.717%). The channel falsifies if no tested (tom_k, tom_lb,
tom_w) cell beats train +96.882% within the 2pp DD slack (DD >=
-19.032%). Carried warning: daily-tape / path-shape tilts on this book
have been train-destructive in both directions more often than not
(rngcomp, monpath, dskew, volpart, timesince, rev36, rangeac this loop)
— a both-signs-harm result closes the channel as a double-count of what
the rank and ids term already price.

Import chain: strat_l17a_last5 -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> ids tilt re-applied with
`strat_l15b_insideday._monthly_inside` IMPORTED (frozen file; reuse,
never reimplement; application block line-for-line its own score()) ->
turn-of-month persistence term is NEW math (positional within-bucket
closes, log-share of the final tom_k sessions, multi-bucket mean) ->
cap step mirrored inline from strat_floorhightiershapeconc.score /
strat_l13a_concwobble.score / strat_l15b_insideday.score (identical
loop: cap = cap_full where exposure >= 1.0 else cap_weak; lower ranks
set NaN after a stable descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window —
handled as follows). prev_m uses close.shift(1) WITHIN SYMBOL over dates
sorted ascending — the prior bar, never a future one; L_m and R_m use
only the bucket's own bars plus that one prior close. For score row t
(holding month starting months[t]) the newest bucket read is bucket t-1,
whose bars all have date in [months[t-1], months[t]) — every bar read is
strictly BEFORE months[t]; buckets t and later are never touched, so the
fact that `daily` covers the full panel window is harmless. The
percentile at row t uses only s values from that same backward window.
Rows with insufficient history (t < tom_lb) and buckets failing the
bar-count / price / 1%-move guards read NaN and keep tilt exactly 1.0 —
eligibility and rank unmodified, nothing dropped on missing data,
nothing peeks. The cap reads month-t ranks only.

Off-switch identity (two levels): (1) tom_w = 0.0 leaves the ids tilt
exactly as the champion applies it and the mirrored cap bitwise
unchanged, so the flat base IS the champion at the champion params (the
ids application here is line-for-line strat_l15b_insideday's own: same
nanmean window, same stable-argsort percentile, same np.where). (2)
ids_w 0.0 AND tom_w 0.0 at otherwise champion keys reproduce the
wobble-only chain at gw_w 0.15: documented Loop-15 measurement gw 0.15
alone -> train +87.00 / DD -17.34. NOTE imported defaults leak:
strat_l12b_gatefail's own default is gf_w = 0.05 — this file setdefaults
gf_lb = 12 / gf_w = 0.0 / gw_w = 0.0 BEFORE delegating, so the off-switch
is exact and the champion's gw_w 0.15 and ids keys (ids_lb 3 / ids_w
-0.13) must be PASSED by the caller (champion keys, not defaults here).
This file's own defaults are NEUTRAL: tom_w 0.0 (tom_k 5 / tom_lb 3 are
inert while the weight is 0).

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art in the mechanism inventory — the
DEAD intramonth path-shape family (strat_l16a_monpath, Loop-16): the
front-vs-back-HALF return difference of the PRINT MONTH ALONE (its SPACE
fixes mp_lb at 1 and its own docstring argues averaging over months
would dilute the recency its hypothesis needed). The ONE thing changed:
the ESTIMAND is a persistent per-name calendar property — the share of
 EACH month's return earned in its final tom_k sessions, AVERAGED over
tom_lb trailing buckets — not a property of the print month. monpath
asked "was THIS move back-loaded?" (a state of the current move);
last5 asks "does this name SYSTEMATICALLY earn its monthly return at
the turn?" (a stable timing fingerprint that requires averaging to
estimate at all — the multi-bucket mean is the signal, not a dilution).
The functional differs too: a log-share of a short end-window vs a
half-vs-half difference. Concrete disagreement case: a name whose
current print month happened to be back-loaded (monpath scores it high)
but whose prior months were front-loaded reads ~0 here, and vice versa.
It is not freshness/drought (print recency — DEAD), not ids (session
containment — LIVE), not CLV (intra-day close location — DEAD), not
seasonal momentum (same-calendar-month returns across years — DEAD):
the within-month TIMING PERSISTENCE of returns is a variable nothing in
the chain or inventory consumes.

SPACE = my keys: tom_k {3, 5} (final-session window per bucket),
        tom_lb {3, 6} (trailing buckets the share is averaged over),
        tom_w {-0.2, -0.1, +0.1, +0.2} (percentile tilt; 0.0 =
        off-switch; positive = favour persistent turn-of-month-strong
        names). The |monthly log move| >= 0.01 guard is FIXED (not
        searched). Champion keys pinned (passed by the caller, docs
        only): b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19, lookback
        12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w
        -0.13. max_hold 3 is a HARNESS key passed via params-json; this
        file does not consume it.

Designer smoke observations (Loop-17, pre-freeze, nse_all top 15 25bps
split 2022-01-01, isolated ledger l17_dA): off-switch reproduced the
champion EXACTLY — train +96.88 / DD -17.03 / calmar 5.688, fwd +48.97 /
-12.31 (H1 +98.3 / H2 +95.5). tom_k 5 / tom_lb 3: tom_w +0.2 (persistent
turn-of-month strength) -> train +79.14 / DD -21.31 / calmar 3.71, fwd
+63.78 / -17.19; tom_w -0.2 (front-loaded names) -> train +70.24 /
DD -19.12 / calmar 3.67, fwd +44.85 / -18.49. BOTH signs 18-27pp below
the champion on train — the flow-fingerprint story does not beat the
rank+ids ordering either. Falsifier FIRED on both signs: turn-of-month
persistence is closed on this base; do not spend worker windows on
tom_k 3 / tom_lb 6 or intermediate weights (they interpolate toward the
champion, never above it — the Loop-16 monpath pattern, whose print-
month-only variant this result now brackets from the persistence side).
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
    "tom_k": [3, 5],
    "tom_lb": [3, 6],
    "tom_w": [-0.2, -0.1, 0.1, 0.2],
}

_MIN_LOG_MOVE = 0.01  # fixed: |monthly log return| guard against division noise


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


def _monthly_lastk(daily: pl.DataFrame, months, cols, k: int) -> np.ndarray:
    """Per (calendar month, stock): the log-share of the month's move
    earned in its final k sessions; NaN on short buckets, bad prices, or
    |monthly log move| < _MIN_LOG_MOVE."""
    d = daily.filter(pl.col("close").is_not_null() & (pl.col("close") > 0.0))
    d = d.with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.len().alias("n"),
               pl.col("close").last().alias("lastc"),
               # positional: close exactly k sessions before the last bar
               pl.col("close").tail(k + 1).first().alias("basek"),
               # positional: close immediately before the bucket's first bar
               pl.col("pc").first().alias("prevc"))
          .sort("symbol", "date"))
    g = g.with_columns(
        pl.when(
            (pl.col("n") > k)
            & pl.col("basek").is_not_null() & (pl.col("basek") > 0.0)
            & pl.col("prevc").is_not_null() & (pl.col("prevc") > 0.0)
        ).then(
            pl.when(((pl.col("lastc") / pl.col("prevc")).log().abs()
                     >= _MIN_LOG_MOVE))
              .then((pl.col("lastc") / pl.col("basek")).log()
                    / (pl.col("lastc") / pl.col("prevc")).log())
              .otherwise(None)
        ).otherwise(None).alias("s"))
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

    tom_w = float(params.get("tom_w", 0.0))
    if tom_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        k = int(params.get("tom_k", 5))
        lb = int(params.get("tom_lb", 3))
        S = _monthly_lastk(daily, months, cols, k)
        _tilt_rows(S, out, out, lb, tom_w)

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
