"""Candidate: PER-CLASS corporate-action event dynamics (lumpy/capital-
structure-class vs regular cash-class factor jumps) as strictly positive
cross-sectional percentile tilts on the CURRENT champion's returned scores
(strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l20b_spread (the
Corwin-Schultz spread tilt applied post-chain on the strat_l19a_balanced
book: floor-lift fresh-print rank + breadth-tier exposure + eligibility
wobble gw_w 0.15 + inside-day tilt ids_w -0.13 + regime-conditional cap
cap_weak/cap_full + listing-age tilt la_w 0.5 + outrank tilt or_w -0.1 +
spread tilt sp_lb 4 / sp_w -0.05; top 15, nse_all, cost 25bps, split
2022-01-01) — is composed VERBATIM via `from strat_l20b_spread import
score as _champ` (the champion chain IS l20b_spread over l19; delegating
to _l19 alone would drop the champion's sp_* term and reproduce 98.682
instead of the 102.990 identity target), and this file multiplies the
scores it returns by one or more strictly positive cross-sectional
percentile tilts built from the Loop-20 adjustment-factor channel
R(t) = adj_close(t)/close(t) (loader `_r_factor` imported from
strat_l20a_divyield — never a second copy), with the ONE new dimension:
the event stream is SPLIT INTO TWO CLASSES by step magnitude before any
signal is computed.

Event classes (per daily bar, step = R(bar)/R(prev) - 1, event iff step >
ac_eps 1e-4 — the threshold and its 3-orders-of-magnitude noise separation
measured in strat_l20a_divregular, cited there: rounding noise <= 5.8e-7 at
the 99th percentile vs real steps from 1e-4 up):
  LARGE  : step >= ac_thr (0.02)  — lumpy / capital-structure-class events
  SMALL  : ac_eps < step < ac_thr — regular cash-distribution events
Honest label note: in THIS panel `close` is already split-adjusted, so a
clean split/bonus does NOT step R (both close and adj_close carry the split
factor); the LARGE class therefore captures lumpy one-off distributions
(special / bonus-sized payouts) plus any upstream adjustment residue — the
classification is a magnitude HYPOTHESIS about two behavioural classes,
not a verified split detector, and the mechanisms below test exactly that
hypothesis.

Signals (per name j, holding month t, window ac_lb months = k, censoring
ac_cap months; every signal NaN where t < k or the name has no factor
history, else finite — never-distributed names read the censored/zero
value, matching strat_l20a_divregular's convention):
    LCNT[t,j] = # LARGE events with bar index in (t1, t2]           (count)
    LREC[t,j] = months from last LARGE event <= t2 to t2, right-
                censored at ac_cap (no LARGE event yet = ac_cap)    (recency)
    SREC[t,j] = same recency computed on SMALL events only
    SSIZ[t,j] = clip( sum of log(1+step) over SMALL events in (t1, t2],
                0, 0.01*k )                                         (size)
with t2 = last bar strictly before months[t], t1 = last bar strictly
before months[t-k] (the exact endpoints of strat_l20a_divregular._signals).
Each armed signal is tie-averaged-percentiled across the row's finite
SIGNAL population (champion convention via _pct_tie — the zero-event block
must not be smeared across the pct axis in column order) and applied as

    tilt = 1 + w * (2 * pct - 1),  |w| < 1
    out[t] = out[t] * tilt        # finite score entries only; NaN stays NaN

arms: ac_lr_w on LREC (< 0 favours RECENT lumpy events, > 0 favours
lumpy-stale/never names), ac_lc_w on LCNT (> 0 favours many lumpy events),
ac_sr_w on SREC (< 0 favours recently-paid regular payers), ac_ss_w on
SSIZ (> 0 favours large regular cash payouts, < 0 favours small/non-payers
— the round-1 winning sign on the mixed-class size transform).

PIT argument: every endpoint and every event bar is strictly before
months[t]: t2 = last bar with date < months[t], t1 = last bar with date <
months[t-k] < months[t], and every counted event bar is <= t2 by
construction (the LEVEL of R embeds future dividends and is NOT used —
only backward window differences / backward recency, exactly the argument
in strat_l20a_divyield/divregular). Rows t < k read no window and keep
tilt exactly 1.0; names with no factor history keep tilt 1.0 (re-ranking,
never a gate); no row > t is read. The delegate's PIT is unchanged from
strat_l20b_spread (spread buckets t-sp_lb..t-1, ids daily bars strictly
before months[t], age static, outrank px[t-or_lb]..px[t]).

Import chain: strat_l21a_actionclass -> strat_l20b_spread.score (CURRENT
champion: -> strat_l19a_balanced.score -> strat_l12b_gatefail.score ->
floorhighfastgate/sustaincond/tiershape + wobble -> ids tilt re-expressed
from strat_l15b_insideday -> mirrored cap -> listage tilt from
strat_l17c_listage -> outrank tilt from strat_l16b_outrank -> post-chain
CS-spread tilt) AND -> strat_l20a_divyield (_r_factor loader, _pct_tie).
This file adds only the per-class signals and their tilts; the event
threshold logic mirrors strat_l20a_divregular._event_idx (same 1e-4, same
positional-window test) but keeps the step magnitudes it discards there.

Off-switch identity: ac_lr_w = ac_lc_w = ac_sr_w = ac_ss_w = 0.0 (this
file's OWN setdefaults, applied to the params copy BEFORE delegating —
Loop-13/14 imported-defaults lesson) skips the whole tilt block before any
signal is built, so `out` is a bitwise copy of strat_l20b_spread's returned
scores at the PASSED keys. Champion keys (including sp_lb 4 / sp_w -0.05 /
sp_frac 0.5) are always PASSED by the caller, never defaulted here.

Flat-base metric (off-switch must reproduce exactly): train +102.990% /
DD -15.506% / ret-DD 6.642 / H1 +100.204% / H2 +105.682% / fwd +54.057% /
fwd DD -10.381% / full +82.001% / full DD -20.728%.

Hypothesis: Loop-20 pooled every factor step into ONE series — size
(divyield) mixed a 0.5% interim with a 10% special, and count/recency
(divregular) let a lumpy one-off reset the recency clock of a regular payer
— yet the two classes should behave differently economically (a lumpy
capital-class event signals a one-off recapitalisation/sponsor action; a
small regular step signals an ongoing payout policy). If the pooled
signals' mostly-neutral verdicts (99.79 / 100.00 at mixed DD-worse doses)
were averaging two opposite class effects, separating the classes moves
the book; if every per-class arm trails, the channel carries no class
information and the axis closes. Coverage check before building (the
Loop-20 join-key rule): every signal above is finite for every name with
factor history in rows t >= k (never-LARGE names read the censored cap,
never-small names read 0), so no arm can silently degenerate below the
n >= 5 percentile guard.

Falsifier (exact): on the champion params below, if EVERY variant in SPACE
trails the flat base on train CAGR AND on calmar, and none improves the
forward window without paying for it on train/DD (Loop-17 rule: a train
gain bought with DD or forward is an artifact), then per-class corporate-
action dynamics are closed at this base. Base to beat: train +102.990% /
DD -15.506% / calmar 6.642 / fwd +54.057% / fwd DD -10.381%. Before ANY
promotion: this is a book-composition mechanism — count the decision months
whose picks differ from the champion's (Loop-16 lesson).

NOVELTY STATEMENT (closest registry rows -> the ONE thing that changed):
- research/tested_mechanisms.tsv line 142 strat_l20a_divyield — same
  channel, SIZE transform pooling ALL steps (DEAD-not-promoted, best
  99.79/-15.72/6.35, sign-consistent but calmar-neutral);
- line 143 strat_l20a_divregular — same channel, COUNT/RECENCY pooling all
  events (DEAD-not-promoted, 100.00/-16.43/6.09, DD worse);
- line 144 strat_l20a2_divcombo — size x count composition
  (KEEP-not-promoted 103.62/-16.56/6.26, weight spike);
- line 152 strat_l20a3_divspread — cross-channel dividend x spread sibling
  (SCREENING-SIBLING, interference on train).
The ONE thing that changed: EVENT CLASS — no row above ever conditioned
the signal on the event's magnitude; all four pooled both classes into one
series. Class-conditional recency/count/size (per-class clocks that a
lumpy event does not reset for the regular class, per-class sizes that a
0.5% interim does not dilute) is new information from an opened but only
partially mined channel. Off-channel analogs checked and distinct: the
recency/base-duration price families (strat_breakrec / strat_floortrendq /
strat_highbase / strat_l17a_timesince, all DEAD) measure PRICE events; the
streak/persistence families (strat_floorhighrankpersist,
strat_l15b_upstreak, DEAD) measure price streaks — this file's classed
EVENT clocks have no registry row at any base.

Keys consumed: this file reads ac_lb, ac_thr, ac_cap, ac_lr_w, ac_lc_w,
ac_sr_w, ac_ss_w; everything else in params-json flows through to the
delegate (all champion SPACE keys incl. sp_*) or is read by the harness
(max_hold 3).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, cap_full 20,
        cap_weak 11, fast_ma 5, floor_lb 19, gf_lb 12, gf_w 0.0, gw_w 0.15,
        ids_lb 3, ids_w -0.13, la_min 0, la_w 0.5, lookback 12,
        max_dist 0.055, max_hold 3, or_lb 6, or_w -0.1, regime_ma 18,
        sp_frac 0.5, sp_lb 4, sp_w -0.05, sustain_hi 2, sustain_lo 3,
        tier_lo 0.9999, tier_mid 0.9999)
        + ac_lb {36}   trailing window in months (36 chosen: LARGE events
                        are rare, a 24m window starves the class; 24 is the
                        deepen option, not smoked here)
        + ac_thr {0.02} class boundary (pinned; measured on the full panel
                        before shipping — 23,709 events > 1e-4 split into
                        5,257 LARGE (894 of 1,745 event-emitting symbols
                        ever LARGE, median 4, max 28 per symbol) and 18,452
                        SMALL; bins: [1e-2,0.02) 5,594 / [0.02,0.05) 4,223 /
                        [0.05,0.1) 776 / [0.1,10) 255 — 0.02 sits at the
                        mode of the lumpy tail, two decades above the floor)
        + ac_cap {60}  recency censoring horizon, months (divregular pin)
        + ac_lr_w {0.0, -0.15, +0.15} LARGE-class recency tilt
        + ac_lc_w {0.0, +0.15}         LARGE-class count tilt
        + ac_sr_w {0.0, -0.15}         SMALL-class recency tilt
        + ac_ss_w {0.0, -0.15}         SMALL-class size tilt
        Documented smoke rows (6): V0 identity (all four 0.0);
        V1 ac_lr_w -0.15 (recent lumpy favoured); V2 ac_lr_w +0.15
        (lumpy-stale/never favoured — both signs first-class); V3 ac_lc_w
        +0.15 (frequent lumpy); V4 ac_sr_w -0.15 (recent regular payer);
        V5 ac_ss_w -0.15 (small regular payout, round-1 winning sign).
        Deepen-only (not smoked): ac_lc_w -0.15, ac_ss_w +0.15, ac_lb 24.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from strat_l20a_divyield import _pct_tie, _r_factor
from strat_l20b_spread import score as _champ

NEEDS_DAILY = True  # the champion delegate's ids/spread terms read the daily panel

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
    "sp_frac": [0.5], "sp_lb": [4], "sp_w": [-0.05],
    # this file's keys
    "ac_lb": [36],                    # trailing window, months
    "ac_thr": [0.02],                 # LARGE/SMALL class boundary, pinned
    "ac_cap": [60],                   # recency censoring, months, pinned
    "ac_lr_w": [0.0, -0.15, 0.15],    # LARGE recency tilt; 0.0 = off
    "ac_lc_w": [0.0, 0.15],           # LARGE count tilt; 0.0 = off
    "ac_sr_w": [0.0, -0.15],          # SMALL recency tilt; 0.0 = off
    "ac_ss_w": [0.0, -0.15],          # SMALL size tilt; 0.0 = off
}

_EPS = 1e-4    # event floor (strat_l20a_divregular: noise <= 5.8e-7)
_EPOCH = date(1970, 1, 1)
_EVT_CACHE: dict = {}


def _classed(cols, thr: float) -> dict:
    """symbol -> (bar indices of R-steps > _EPS, their step magnitudes).

    Same construction as strat_l20a_divregular._event_idx (same 1e-4 floor,
    positional bar indices into the symbol's own sorted (date, R) series),
    but keeps the magnitudes that file discards, so callers can split the
    stream into classes at `thr`. Built once per (cols, thr) per process.
    """
    key = (tuple(cols), float(thr))
    if key not in _EVT_CACHE:
        series = _r_factor(cols)
        ev = {}
        for s, (_d, r) in series.items():
            if r.size >= 2:
                rel = r[1:] / r[:-1] - 1.0          # rel[i] steps INTO bar i+1
                e = np.flatnonzero(rel > _EPS) + 1   # index of the step-up bar
                ev[s] = (e.astype(np.int64), rel[e - 1])
            else:
                ev[s] = (np.empty(0, dtype=np.int64), np.empty(0, dtype=float))
        _EVT_CACHE[key] = ev
    return _EVT_CACHE[key]


def _signals(months, cols, k: int, thr: float, cap: float):
    """(LREC, LCNT, SREC, SSIZ) matrices, each (len(months), len(cols)).

    Endpoints identical to strat_l20a_divregular._signals:
        t2 = last bar strictly before months[t]; t1 = last bar strictly
        before months[t-k]; rows t < k stay NaN.
    A name WITH factor history always reads finite values in rows t >= k
    (0 / cap where its class never fired — never-distributed names get the
    censored maximum, the standard not-yet-fired treatment); a name with NO
    factor history stays NaN (tilt 1.0 in the caller — re-ranking, not a
    gate).
    """
    series = _r_factor(cols)
    events = _classed(cols, thr)
    cuts = np.array([(m - _EPOCH).days for m in months], dtype=np.int64)
    T = len(months)
    lrec = np.full((T, len(cols)), np.nan)
    lcnt = np.full((T, len(cols)), np.nan)
    srec = np.full((T, len(cols)), np.nan)
    ssiz = np.full((T, len(cols)), np.nan)
    for j, s in enumerate(cols):
        sr = series.get(s)
        if sr is None:
            continue
        d, _r = sr
        e, st = events[s]
        ix = np.searchsorted(d, cuts, side="left") - 1
        i2 = ix[k:]
        i1 = ix[:T - k]
        ok = (i2 >= 0) & (i1 >= 0)
        if not ok.any():
            continue
        rows = np.arange(k, T)[ok]
        i2v = i2[ok]
        i1v = i1[ok]
        if e.size == 0:
            # factor history exists but never a single event
            lcnt[rows, j] = 0.0
            lrec[rows, j] = cap
            srec[rows, j] = cap
            ssiz[rows, j] = 0.0
            continue
        big = st >= thr
        eL, stL = e[big], st[big]
        eS, stS = e[~big], st[~big]

        # ---- LARGE class: count + recency ----
        if eL.size:
            nHi = np.searchsorted(eL, i2v, side="right")
            nLo = np.searchsorted(eL, i1v, side="right")
            lcnt[rows, j] = (nHi - nLo).astype(float)
            last = eL[np.maximum(nHi - 1, 0)]
            ms = (d[i2v] - d[last]) / 30.4375
            lrec[rows, j] = np.where(nHi > 0, np.minimum(ms, cap), cap)
        else:
            lcnt[rows, j] = 0.0
            lrec[rows, j] = cap

        # ---- SMALL class: recency + winsorised size sum ----
        if eS.size:
            nHi = np.searchsorted(eS, i2v, side="right")
            nLo = np.searchsorted(eS, i1v, side="right")
            last = eS[np.maximum(nHi - 1, 0)]
            ms = (d[i2v] - d[last]) / 30.4375
            srec[rows, j] = np.where(nHi > 0, np.minimum(ms, cap), cap)
            cs = np.r_[0.0, np.cumsum(np.log1p(stS))]
            ssiz[rows, j] = np.clip(cs[nHi] - cs[nLo], 0.0, 0.01 * k)
        else:
            srec[rows, j] = cap
            ssiz[rows, j] = 0.0
    return lrec, lcnt, srec, ssiz


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-13/14 imported-defaults leak):
    # this file's own keys, plus the trio strat_l19a_balanced neutralises
    # itself (belt-and-braces, same values). Champion keys (gw_w 0.15,
    # ids_w -0.13, la_w 0.5, or_w -0.1, sp_w -0.05, ...) are PASSED by the
    # caller, never defaulted here.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    p.setdefault("ac_lb", 36)
    p.setdefault("ac_thr", 0.02)
    p.setdefault("ac_cap", 60.0)
    p.setdefault("ac_lr_w", 0.0)
    p.setdefault("ac_lc_w", 0.0)
    p.setdefault("ac_sr_w", 0.0)
    p.setdefault("ac_ss_w", 0.0)
    out, regime = _champ(panels, p)       # current champion chain, verbatim
    out = np.array(out, dtype=float, copy=True)

    arms_w = (float(p["ac_lr_w"]), float(p["ac_lc_w"]),
              float(p["ac_sr_w"]), float(p["ac_ss_w"]))
    if all(w == 0.0 for w in arms_w):
        return out, regime                # off-switch: bitwise champion copy

    k = int(p["ac_lb"])
    thr = float(p["ac_thr"])
    cap = float(p["ac_cap"])
    months, cols = panels["months"], panels["cols"]
    LREC, LCNT, SREC, SSIZ = _signals(months, cols, k, thr, cap)
    for mat, w in zip((LREC, LCNT, SREC, SSIZ), arms_w):
        if w == 0.0:
            continue
        for t in range(k, out.shape[0]):
            sig = mat[t]
            valid = np.isfinite(sig)
            if int(valid.sum()) < 5:
                continue
            pct = _pct_tie(sig[valid])
            tilt = np.ones(out.shape[1])
            tilt[valid] = 1.0 + w * (2.0 * pct - 1.0)   # strictly positive
            fin = np.isfinite(out[t])
            out[t, fin] = out[t, fin] * tilt[fin]        # NaN stays NaN
    return out, regime
