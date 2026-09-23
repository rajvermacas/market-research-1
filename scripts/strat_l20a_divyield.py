"""Candidate: trailing dividend-FACTOR change (an approximate trailing
dividend yield) as a cross-sectional percentile tilt on the CURRENT champion's
returned scores (strategy_lab contract).

Setup in words: the CURRENT champion chain, strat_l19a_balanced (floor-lift
fresh-print rank + breadth-tier exposure + eligibility wobble gw_w 0.15 +
inside-day tilt ids_w -0.13 + regime-conditional cap cap_weak/cap_full +
listing-age tilt la_w 0.5 + cross-sectional outrank tilt or_w -0.1), is called
UNCHANGED through `from strat_l19a_balanced import score as _l19`, and this
file multiplies the scores it returns by one more strictly positive,
cross-sectionally rank-based multiplier built from a channel no file in this
tree has ever read: the corporate-action adjustment factor

    R(t) = adj_close(t) / close(t)

read straight from the daily panel (the harness's `panels["daily"]` carries
only symbol/date/OHLCV, so this file reads the parquet itself, exactly as
strat_l17c_listage reads `listing_date` from the universe snapshot). In the
daily panel `close` is split-adjusted and `adj_close` is BOTH split- and
dividend-adjusted, so the ratio R isolates the cumulative CASH-DISTRIBUTION
(back-)adjustment factor: R is a step function that steps UP on each
ex-dividend date and is otherwise flat up to ~1e-7 float rounding (measured
over all 7.47M bars: 99th-pctile step 5.8e-7, 23,708 real steps > 1e-4,
10 down-steps ever, all pre-2010).

Formula citations:
 (a) Adjustment-factor identity — the standard multiplicative back-adjustment
     of a total-return series used by every index methodology (S&P/MSCI
     "price vs. total-return index" convention; Yahoo's adj_close is the same
     construction):
         adj_close(t) = close(t) * Prod_{ex-dates d > t} A_d,  A_d = 1 - y_d
     hence R(t) = adj_close(t)/close(t) = Prod_{d > t} A_d.
 (b) Trailing dividend yield from a price/total-return pair — the standard
     estimator "yield = accumulation of the TR/price divergence over the
     window". With t1 < t2:
         log( R(t2) / R(t1) ) = Sum_{t1 < d <= t2} -log(A_d) = Sum y_d
                                   ~= total dividend yield over (t1, t2].
     All factors for ex-dates AFTER t2 appear in both R(t2) and R(t1) and
     cancel — only events inside the window survive. So the SIGNAL used here
     is the trailing change of the ratio (a window yield), never a raw level.

Signal (per name j, holding month t, window dy_lb months = k):
    t2_j(t) = last daily bar with date <  months[t]        (strictly before)
    t1_j(t) = last daily bar with date <  months[t-k]      (strictly before)
    y_j(t)  = clip( log( R(t2) / R(t1) ), 0, 0.01 * k )    # 0 floor,
                                                           # 12%/yr log cap
    pct_j(t)= tie-averaged cross-sectional percentile of y among ALL names
              with a finite y in row t (the champion-convention population:
              strat_l19a's la/or/ids tilts all take the percentile over the
              whole row's finite signal, then multiply into the finite score
              entries only)
    tilt_j(t)= 1 + dy_w * (2 * pct_j(t) - 1)               # |dy_w| < 1
    out[t]   = out[t] * tilt                               # finite entries
                                                           # only, NaN stays
                                                           # NaN, t < k
                                                           # untouched
dy_w > 0 favours HIGH trailing yield (cash-distributing names); dy_w < 0
favours low/no payers. |dy_w| < 1 keeps tilt strictly positive, so this is a
re-weighting of the champion's own scores, never a new eligibility (except
the documented dy_min gate below). Ties are AVERAGE-ranked: ~60% of NSE names
pay nothing in a given window (all y = 0 exactly); a stable-argsort position
rank would hand that tied block an arbitrary per-name handicap spread over
60% of the pct axis, so tied values share the mean position instead.

PIT argument: the LEVEL R(t) is NOT point-in-time clean — it embeds every
dividend the company will ever pay AFTER t, which the decision at months[t]
cannot know. The RATIO log(R(t2)/R(t1)) with both endpoints sampled from bars
strictly before months[t] IS pit-clean: distributions occurring after t2 sit
inside both endpoints and cancel exactly; the only events that survive are
those in (t1, t2], all of which happened before months[t] and were therefore
public at the decision. t2 < months[t] and t1 < months[t-k] < months[t], so
no bar the decision could not have seen is read. Rows t < k read no window at
all and are left untouched (tilt exactly 1.0). Names with no finite factor
history in a row keep tilt exactly 1.0 (unless the dy_min gate is armed).

Import chain: strat_l20a_divyield -> strat_l19a_balanced.score (champion:
-> strat_l12b_gatefail.score -> strat_floorhighfastgate /
strat_floorhighsustaincond / strat_floorhightiershape, wobble inside ->
re-expressed ids tilt from strat_l15b_insideday -> mirrored cap ->
listing-age tilt re-expressed from strat_l17c_listage -> outrank tilt
re-expressed from strat_l16b_outrank -> final no-op cap). This file adds ONE
post-chain multiplier and imports nothing else from the tree.

Off-switch identity: dy_w = 0.0 AND dy_min <= 0.0 returns `_l19(panels, p)`
untouched, and the neutral defaults (gf_lb 12 / gf_w 0.0 / gw_w 0.0) are set
via setdefault BEFORE delegating — identical values to the ones
strat_l19a_balanced sets itself, so nothing leaks (Loop-14 lesson) and the
returned scores are bit-exact champion scores.

Flat-base metric (off-switch must reproduce exactly, champion params passed
by the caller): train +98.682% / DD -15.506% / calmar 6.364 / H1 +95.295% /
H2 +101.966% / fwd +53.148% / fwd DD -10.403% / full +79.237% / -20.728%.

Hypothesis: a cash-distribution channel is genuinely absent from this tree's
mechanism set (the champion's book is a small/non-index momentum book —
Loop-17 found the index-membership gate COLLAPSES it), so dividend behaviour
has never been measured against it. If Indian payers are a distinct
cross-sectional cohort (mature, cash-generative, institutionally held), the
trailing-yield percentile may re-order the champion's near-cap frontier
usefully in either direction: rewarding sponsorship (dy_w > 0) or avoiding the
"dividend trap" value names the momentum book would otherwise touch
(dy_w < 0).

Falsification test (exact): on the champion params below, if EVERY variant in
SPACE trails the flat base on train CAGR AND on calmar (and none improves the
forward window without paying for it on train/DD — Loop-17 lesson: a train
gain bought with DD or forward is an artifact), then the dividend-yield tilt
is closed at this base. Base to beat: train +98.682% / DD -15.506% /
calmar 6.364 / fwd +53.148% / fwd DD -10.403%.

NOVELTY STATEMENT: `research/tested_mechanisms.tsv` (140 rows) contains ZERO
rows matching dividend / adj / corporate / payout — verified by grep before
writing; NO file in this tree has ever read adj_close, a dividend, or any
corporate-action field, so there is no closest prior art to cite on this axis
by construction. The nearest families I checked and cite as the structural
analogue are the ATTRIBUTE axis (strat_l17c_listage LIVE as a champion term,
strat_l17c_faceval / strat_l17c_idxflag / strat_l17c_seriesgate DEAD — static
ex-ante per-name attributes tilted post-chain) and the
liquidity/volume/sponsorship axis (strat_floorhighaccum / ...spons DEAD). The
ONE thing that changed: the DATA CHANNEL — a time-varying corporate-action
signal (adj_close/close), as opposed to another transformation of price,
volume, calendar, or a static board attribute.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1; max_hold 3 is a HARNESS key
        passed via params-json)
        + dy_lb {12, 24, 36}  trailing window in months (default 24)
        + dy_w  {+0.15, -0.15} percentile tilt weight (default 0.0 = off;
                                 positive favours HIGH trailing yield)
        + dy_min {0.0, 0.02}   ELIGIBILITY GATE: NaN any finite score whose
                                 trailing log-yield is below dy_min (0.0 =
                                 disarmed). Documented as a VARIANT only —
                                 gates are usually destructive (Loop-17
                                 membership/series gates), but the
                                 minimum-payer variant is part of the
                                 pre-registered question.
        Documented variant rows: (dy_lb 24, dy_w +0.15) payers-up;
        (24, -0.15) payers-down; (12, +0.15) short window; (36, -0.15) long
        window, negative sign; (24, +0.15, dy_min 0.02) minimum-payer gate.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from strat_l19a_balanced import score as _l19

NEEDS_DAILY = True  # the champion delegate's ids term reads the daily panel

SPACE = {
    # champion keys (pinned, docs only)
    "b_hi": [0.69], "b_lo": [0.45], "b_mid": [0.55],
    "floor_lb": [19], "lookback": [12], "max_dist": [0.055],
    "regime_ma": [18], "fast_ma": [5],
    "sustain_lo": [3], "sustain_hi": [2],
    "tier_lo": [0.9999], "tier_mid": [0.9999],
    "cap_weak": [11], "cap_full": [20],
    "gf_lb": [12], "gf_w": [0.0], "gw_w": [0.15],
    "ids_lb": [3], "ids_w": [-0.13],
    "la_min": [0], "la_w": [0.5], "or_lb": [6], "or_w": [-0.1],
    # this file's keys
    "dy_lb": [12, 24, 36],          # trailing window, months
    "dy_w": [0.0, 0.15, -0.15],     # percentile tilt; 0.0 = off-switch
    "dy_min": [0.0, 0.02],          # minimum-payer eligibility gate, off at 0
}

_EPOCH = date(1970, 1, 1)
_R_CACHE: dict = {}


def _r_factor(cols) -> dict:
    """symbol -> (dates as int64 epoch-days ascending, R = adj_close/close).

    Read once per process from the committed daily panel; scratch-free (no
    writes). close/adj_close are never null and always > 0 in this panel
    (verified before shipping); rows are sorted by symbol, date.
    """
    key = tuple(cols)
    if key not in _R_CACHE:
        root = Path(__file__).resolve().parents[1]
        df = (
            pl.scan_parquet(str(root / "data" / "ohlcv" / "daily" / "**" / "*.parquet"),
                            hive_partitioning=True)
            .filter(pl.col("symbol").is_in(list(cols))
                    & (pl.col("close") > 0) & (pl.col("adj_close") > 0))
            .select("symbol", "date", "close", "adj_close")
            .with_columns((pl.col("adj_close") / pl.col("close")).alias("r"),
                          pl.col("date").dt.epoch("d").alias("d"))
            .select("symbol", "d", "r")
            .sort("symbol", "d")
            .collect()
        )
        sym = df["symbol"].to_numpy()
        d = df["d"].to_numpy()
        r = df["r"].to_numpy()
        starts = np.flatnonzero(np.r_[True, sym[1:] != sym[:-1]])
        ends = np.r_[starts[1:], len(sym)]
        _R_CACHE[key] = {str(s): (d[a:b], r[a:b]) for s, a, b in zip(sym[starts], starts, ends)}
    return _R_CACHE[key]


def _pct_tie(v: np.ndarray) -> np.ndarray:
    """Tie-averaged cross-sectional percentile in [0, 1] of a finite 1-D
    array: every equal value shares the mean position it would span. (The
    champion's stable-argsort rank would smear the ~60%-of-names tied zero
    block across 60% of the pct axis in arbitrary column order.)"""
    n = v.size
    if n == 1:
        return np.full(1, 0.5)
    order = np.argsort(v, kind="stable")
    sv = v[order]
    ends = np.r_[np.flatnonzero(sv[1:] != sv[:-1]), n - 1]
    starts = np.r_[0, ends[:-1] + 1]
    counts = ends - starts + 1
    ranks_sorted = np.repeat((starts + ends) / 2.0, counts)
    pct = np.empty(n)
    pct[order] = ranks_sorted / (n - 1)
    return pct


def _trail_yield(months, cols, k: int) -> np.ndarray:
    """(len(months) x len(cols)) matrix of
        y[t, j] = clip(log(R(t2)/R(t1)), 0, 0.01*k)
    with t2 = last bar of j strictly before months[t], t1 = last bar strictly
    before months[t-k]; NaN where either endpoint is missing or t < k.
    One searchsorted per symbol over all month cutoffs, then gathers.
    """
    series = _r_factor(cols)
    cuts = np.array([(m - _EPOCH).days for m in months], dtype=np.int64)
    T = len(months)
    out = np.full((T, len(cols)), np.nan)
    cap = 0.01 * k  # winsorisation constant: 1%/month of window, log units
    for j, s in enumerate(cols):
        sr = series.get(s)
        if sr is None:
            continue
        d, r = sr
        ix = np.searchsorted(d, cuts, side="left") - 1  # last bar < cutoff
        i2 = ix[k:]
        i1 = ix[:T - k]
        ok2 = i2 >= 0
        ok1 = i1 >= 0
        r2 = np.where(ok2, r[np.maximum(i2, 0)], np.nan)
        r1 = np.where(ok1, r[np.maximum(i1, 0)], np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            y = np.log(r2 / r1)
        y = np.clip(np.where(np.isfinite(y), y, np.nan), 0.0, cap)
        out[k:, j] = y
    return out


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-14 imported-defaults leak):
    # the same three strat_l19a_balanced sets itself, plus this file's own
    # keys. Champion keys (gw_w 0.15, ids_w -0.13, la_w 0.5, or_w -0.1, ...)
    # are PASSED by the caller, never defaulted here.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    p.setdefault("dy_lb", 24)
    p.setdefault("dy_w", 0.0)
    p.setdefault("dy_min", 0.0)
    out, regime = _l19(panels, p)          # champion scores, cap included
    out = np.array(out, dtype=float, copy=True)

    dy_w = float(p["dy_w"])
    dy_min = float(p["dy_min"])
    if dy_w == 0.0 and dy_min <= 0.0:
        return out, regime                  # off-switch: bit-exact identity

    k = int(p["dy_lb"])
    months, cols = panels["months"], panels["cols"]
    Y = _trail_yield(months, cols, k)
    for t in range(k, out.shape[0]):
        y = Y[t]
        if dy_min > 0.0:
            # ELIGIBILITY GATE (documented variant, default disarmed):
            # names without a trailing log-yield >= dy_min lose eligibility.
            fin = np.isfinite(out[t])
            out[t, fin & ~(np.isfinite(y) & (y >= dy_min))] = np.nan
        if dy_w == 0.0:
            continue
        # percentile over the row's SIGNAL (every name with a finite y in
        # row t — the population strat_l19a's la/or/ids tilts use), applied
        # to the finite SCORE entries only (champion-convention composition)
        sig = np.isfinite(y)
        if int(sig.sum()) < 5:
            continue
        pct = _pct_tie(y[sig])
        tilt = np.ones(out.shape[1])
        tilt[sig] = 1.0 + dy_w * (2.0 * pct - 1.0)   # strictly positive
        fin = np.isfinite(out[t])
        out[t, fin] = out[t, fin] * tilt[fin]         # NaN stays NaN
    return out, regime
