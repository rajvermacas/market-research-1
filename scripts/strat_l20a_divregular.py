"""Candidate: payout REGULARITY and RECENCY of the corporate-action
adjustment factor as two cross-sectional percentile tilts on the CURRENT
champion's returned scores (strategy_lab contract).

Setup in words: the CURRENT champion chain, strat_l19a_balanced (floor-lift
fresh-print rank + breadth-tier exposure + eligibility wobble gw_w 0.15 +
inside-day tilt ids_w -0.13 + regime-conditional cap cap_weak/cap_full +
listing-age tilt la_w 0.5 + cross-sectional outrank tilt or_w -0.1), is called
UNCHANGED through `from strat_l19a_balanced import score as _l19`, and this
file multiplies the scores it returns by one or two strictly positive,
cross-sectionally rank-based multipliers built from a channel no file in this
tree has ever read: the corporate-action adjustment factor

    R(t) = adj_close(t) / close(t)

(the harness's `panels["daily"]` carries only symbol/date/OHLCV, so the
factor series is read from the daily parquet via _r_factor imported from
strat_l20a_divyield — the same loader, never a second copy). In the daily
panel `close` is split-adjusted and `adj_close` is BOTH split- and
dividend-adjusted, so R isolates the cumulative CASH-DISTRIBUTION
adjustment: R is a step function that steps UP on each ex-distribution date.
This file does NOT use the size of the steps (that is strat_l20a_divyield's
job); it uses their TIMING — how often, and how recently, a name returns cash
to shareholders.

Formula citations:
 (a) Adjustment-factor identity — the standard multiplicative
     back-adjustment of a total-return series (S&P/MSCI price-vs-total-return
     index convention; Yahoo adj_close is the same construction):
         adj_close(t) = close(t) * Prod_{ex-dates d > t} A_d,  A_d = 1 - y_d,
         R(t) = adj_close(t)/close(t) = Prod_{d > t} A_d.
     Therefore an ex-distribution date shows up exactly as an UPWARD STEP of
     R across that bar: an EVENT iff
         R(bar_i) / R(bar_{i-1}) - 1 > dv_eps   (dv_eps = 1e-4, pinned).
     Empirical basis of the threshold (measured on all 7.47M daily bars before
     shipping): the rounding noise of adj_close/close moves R by <= 5.8e-7 at
     the 99th percentile (22+29 steps live in (1e-6, 1e-4)), while real
     distributions start at 1e-4 (801 steps in [1e-4,1e-3), 12,057 in
     [1e-3,1e-2), 10,686 in [1e-2,0.15]) — three orders of magnitude of
     separation either side, so 1e-4 counts distributions and nothing else.
 (b) Payout regularity = COUNT of separate upward steps in the trailing
     window (the event-count estimator of how consistently a name
     distributes; a one-time special and a steady payer differ only in this
     count once size is ignored). Recency = months elapsed between the last
     step and the window end, right-censored at dr_cap months (a name that
     has never distributed is assigned the censored maximum, the standard
     treatment for a not-yet-fired time-to-event).

Signal (per name j, holding month t, window dv_lb months = k):
    t2: last daily bar with date < months[t]      (strictly before)
    t1: last daily bar with date < months[t-k]    (strictly before)
    n_j(t) = #{ events e : t1_bar < e <= t2_bar }                 (count)
    rec_j(t) = min( (date(t2) - date(last event <= t2)) / 30.4375,
                    dr_cap ),  = dr_cap if no event yet           (months)
    pct = tie-averaged cross-sectional percentile of the signal among ALL
          names with a finite value in row t (champion convention: the
          la/or/ids tilts in strat_l19a_balanced all take the percentile over
          the whole row's finite signal, then multiply into the finite score
          entries only; ties are AVERAGE-ranked because the ~60%-of-names
          zero-event block must not be smeared across 60% of the pct axis in
          arbitrary column order)
    tilt_count = 1 + dv_w * (2 * pct(n) - 1)     # dv_w > 0 favours FREQUENT
    tilt_rec   = 1 + dr_w * (2 * pct(rec) - 1)   # dr_w < 0 favours RECENT
    out[t] = out[t] * tilt_count * tilt_rec      # finite entries only, NaN
                                                 # stays NaN, t < k untouched
|dv_w|, |dr_w| < 1 keep both tilts strictly positive, so this is a
re-weighting of the champion's own scores (except the documented dv_min gate).

PIT argument: the LEVEL of R is NOT point-in-time clean (it embeds every
future distribution), but every quantity here is read from bars strictly
before months[t]: t2 is the last bar before months[t], t1 the last bar
before months[t-k] < months[t], and the last event is by construction <= t2.
Counting events in (t1, t2] therefore uses only distributions that were
public at the decision; no row > t is read, rows t < k read no window and are
untouched (tilt exactly 1.0), and names with no factor history in a row keep
tilt 1.0 (unless the dv_min gate is armed).

Import chain: strat_l20a_divregular -> strat_l20a_divyield (_r_factor loader,
_pct_tie percentile) -> strat_l19a_balanced.score (champion: ->
strat_l12b_gatefail.score -> strat_floorhighfastgate /
strat_floorhighsustaincond / strat_floorhightiershape, wobble inside ->
re-expressed ids tilt from strat_l15b_insideday -> mirrored cap ->
listing-age tilt re-expressed from strat_l17c_listage -> outrank tilt
re-expressed from strat_l16b_outrank -> final no-op cap).

Off-switch identity: dv_w = 0.0 AND dr_w = 0.0 AND dv_min <= 0.0 returns
`_l19(panels, p)` untouched, with the neutral defaults (gf_lb 12 / gf_w 0.0 /
gw_w 0.0) set via setdefault BEFORE delegating — the same values
strat_l19a_balanced sets itself, so nothing leaks (Loop-14 lesson) and the
scores are bit-exact champion scores.

Flat-base metric (off-switch must reproduce exactly, champion params passed
by the caller): train +98.682% / DD -15.506% / calmar 6.364 / H1 +95.295% /
H2 +101.966% / fwd +53.148% / fwd DD -10.403% / full +79.237% / -20.728%.

Hypothesis: the TIMING of cash distributions is a second, distinct read of
the same untouched channel — a name that has paid within the last few months,
and paid several times in two years, is being run for cash by its owners
(governance/sponsorship signal), while a stale or never-payer of the same
momentum shape is not. If that cohort ordering matters for the champion's
near-cap frontier, either tilt moves the book; the two arms can disagree in
sign (frequency vs. recency separate a lapsed steady payer from a newly
initiated one), which is why both are pre-registered in both signs.

Falsification test (exact): on the champion params below, if EVERY variant in
SPACE trails the flat base on train CAGR AND on calmar (and none improves the
forward window while paying for it on train/DD — Loop-17 lesson), then the
payout-regularity/recency axis is closed at this base. Base to beat: train
+98.682% / DD -15.506% / calmar 6.364 / fwd +53.148% / fwd DD -10.403%.

NOVELTY STATEMENT: `research/tested_mechanisms.tsv` (140 rows) contains ZERO
rows matching dividend / adj / corporate / payout — verified by grep before
writing; no file in this tree has ever read adj_close or any
corporate-action field, so there is no closest prior art ON THIS DATA CHANNEL
by construction. The nearest families I checked and cite as the structural
analogs are (i) the ATTRIBUTE axis — strat_l17c_listage (LIVE, a champion
term), strat_l17c_faceval / strat_l17c_idxflag / strat_l17c_seriesgate (DEAD),
static ex-ante per-name attributes tilted post-chain; (ii) the
recency/base-duration family — strat_breakrec / strat_floortrendq /
strat_highbase (all DEAD, recency of PRICE events); and (iii)
strat_l17a_timesince (DEAD, time-under-water RECENCY on the price path) plus
strat_floorhighrankpersist / strat_l15b_upstreak (persistence/streak
families, DEAD on price). Every prior recency/regularity signal in this tree
measures the PRICE path; none measures a corporate action. The ONE thing that
changed: the DATA CHANNEL — timing of cash distributions from
adj_close/close, as opposed to another transformation of price, volume,
calendar, or a static board attribute. (strat_l20a_divyield reads the same
channel for SIZE; this file reads it for TIMING — a different transform of a
brand-new field, pre-registered as two files in one brief.)

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1; max_hold 3 is a HARNESS key
        passed via params-json)
        + dv_lb {24}          trailing window in months (default 24)
        + dv_w  {+0.15, -0.15} event-COUNT percentile tilt (default 0.0 =
                               off; positive favours frequent payers)
        + dr_w  {-0.15, +0.15} RECENCY percentile tilt (default 0.0 = off;
                               negative favours RECENT payers)
        + dv_min {0.0, 1.0}    ELIGIBILITY GATE: NaN any finite score with
                               fewer than dv_min events in the window (0.0 =
                               disarmed). Documented as a VARIANT only —
                               gates are usually destructive (Loop-17
                               membership/series gates).
        Pinned constants: dv_eps 1e-4 (event threshold, justified above),
        dr_cap 60 months (recency censoring horizon).
        Documented variant rows: (dv_w +0.15) frequent payers; (dv_w -0.15)
        infrequent; (dr_w -0.15) recent payers; (dr_w +0.15) stale payers;
        (dv_w +0.15, dv_min 1) minimum-payer gate.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from strat_l19a_balanced import score as _l19
from strat_l20a_divyield import _pct_tie, _r_factor

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
    "dv_lb": [24],                   # trailing window, months
    "dv_w": [0.0, 0.15, -0.15],      # event-count tilt; 0.0 = off-switch
    "dr_w": [0.0, -0.15, 0.15],      # recency tilt; 0.0 = off-switch
    "dv_min": [0.0, 1.0],            # minimum-payer eligibility gate
    "dv_eps": [1e-4],                # pinned event threshold (see docstring)
    "dr_cap": [60],                  # pinned recency censoring, months
}

_EPS = 1e-4   # event threshold: noise <= 5.8e-7, real steps >= 1e-4
_CAP = 60.0   # recency censoring horizon, months
_EPOCH = date(1970, 1, 1)
_EVT_CACHE: dict = {}


def _event_idx(cols) -> dict:
    """symbol -> int64 array of BAR INDICES whose R-step exceeds _EPS.

    Bar indices are positions in the symbol's own sorted (date, R) series, so
    a window test is a positional range check. Built once per process from
    the same factor series strat_l20a_divyield reads for size.
    """
    key = tuple(cols)
    if key not in _EVT_CACHE:
        series = _r_factor(cols)
        ev = {}
        for s, (_d, r) in series.items():
            if r.size >= 2:
                rel = r[1:] / r[:-1] - 1.0
                e = np.flatnonzero(rel > _EPS) + 1   # index of the step-up bar
                ev[s] = e.astype(np.int64)
            else:
                ev[s] = np.empty(0, dtype=np.int64)
        _EVT_CACHE[key] = ev
    return _EVT_CACHE[key]


def _signals(months, cols, k: int):
    """(count, recency) matrices of shape (len(months), len(cols)).

    count[t, j]  = events with bar index in (t1, t2], NaN if t < k or no bar
    rec[t, j]    = months from the last event <= t2 to t2, right-censored at
                   _CAP (never-fired names get _CAP); same NaN conditions
    t2 = last bar strictly before months[t]; t1 = last bar strictly before
    months[t-k].
    """
    series = _r_factor(cols)
    events = _event_idx(cols)
    cuts = np.array([(m - _EPOCH).days for m in months], dtype=np.int64)
    T = len(months)
    cnt = np.full((T, len(cols)), np.nan)
    rec = np.full((T, len(cols)), np.nan)
    for j, s in enumerate(cols):
        sr = series.get(s)
        if sr is None:
            continue
        d, _r = sr
        e = events.get(s, np.empty(0, dtype=np.int64))
        ix = np.searchsorted(d, cuts, side="left") - 1
        i2 = ix[k:]
        i1 = ix[:T - k]
        ok = (i2 >= 0) & (i1 >= 0)
        if not ok.any():
            continue
        i2v = i2[ok]
        i1v = i1[ok]
        if e.size == 0:
            # never distributed: count 0 everywhere, recency right-censored
            rows = np.arange(k, T)[ok]
            cnt[rows, j] = 0.0
            rec[rows, j] = _CAP
            continue
        n_hi = np.searchsorted(e, i2v, side="right")   # #{e <= i2}
        n_lo = np.searchsorted(e, i1v, side="right")   # #{e <= t1}
        sub_cnt = (n_hi - n_lo).astype(float)          # events in (t1, t2]
        # recency: months from the last event <= t2 to t2, censored at _CAP
        # (never-fired or fired longer ago than the horizon both read _CAP)
        last_e = e[np.maximum(n_hi - 1, 0)]
        ms = (d[i2v] - d[last_e]) / 30.4375
        sub_rec = np.where(n_hi > 0, np.minimum(ms, _CAP), _CAP)
        rows = np.arange(k, T)[ok]
        cnt[rows, j] = sub_cnt
        rec[rows, j] = sub_rec
    return cnt, rec


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-14 imported-defaults leak):
    # the same three strat_l19a_balanced sets itself, plus this file's own
    # keys. Champion keys (gw_w 0.15, ids_w -0.13, la_w 0.5, or_w -0.1, ...)
    # are PASSED by the caller, never defaulted here.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    p.setdefault("dv_lb", 24)
    p.setdefault("dv_w", 0.0)
    p.setdefault("dr_w", 0.0)
    p.setdefault("dv_min", 0.0)
    out, regime = _l19(panels, p)          # champion scores, cap included
    out = np.array(out, dtype=float, copy=True)

    dv_w = float(p["dv_w"])
    dr_w = float(p["dr_w"])
    dv_min = float(p["dv_min"])
    if dv_w == 0.0 and dr_w == 0.0 and dv_min <= 0.0:
        return out, regime                  # off-switch: bit-exact identity

    k = int(p["dv_lb"])
    months, cols = panels["months"], panels["cols"]
    CNT, REC = _signals(months, cols, k)
    for t in range(k, out.shape[0]):
        if dv_min > 0.0:
            # ELIGIBILITY GATE (documented variant, default disarmed):
            # names with fewer than dv_min payouts in the window lose
            # eligibility; unknown factor history also fails the gate.
            fin = np.isfinite(out[t])
            c = CNT[t]
            out[t, fin & ~(np.isfinite(c) & (c >= dv_min))] = np.nan
        # percentile over the row's SIGNAL (all names with a finite value in
        # row t — the population strat_l19a's la/or/ids tilts use), applied to
        # the finite SCORE entries only (champion-convention composition)
        for sig_mat, w in ((CNT, dv_w), (REC, dr_w)):
            if w == 0.0:
                continue
            sig = sig_mat[t]
            valid_sig = np.isfinite(sig)
            if int(valid_sig.sum()) < 5:
                continue
            pct = _pct_tie(sig[valid_sig])
            tilt = np.ones(out.shape[1])
            tilt[valid_sig] = 1.0 + w * (2.0 * pct - 1.0)   # strictly positive
            fin = np.isfinite(out[t])
            out[t, fin] = out[t, fin] * tilt[fin]            # NaN stays NaN
    return out, regime
