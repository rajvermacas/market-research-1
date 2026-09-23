"""Candidate: CROSS-CHANNEL composition — the dividend / corporate-action
combo (divyield SIZE x divregular TIMING, cell A) x designer B's tight-spread
tilt — all multiplied into the CURRENT champion's returned scores
(strategy_lab contract).

Setup in words: the CURRENT champion chain, strat_l19a_balanced (floor-lift
fresh-print rank + breadth-tier exposure + eligibility wobble gw_w 0.15 +
inside-day tilt ids_w -0.13 + regime-conditional cap cap_weak/cap_full +
listing-age tilt la_w 0.5 + cross-sectional outrank tilt or_w -0.1) is called
EXACTLY ONCE through `from strat_l19a_balanced import score as _l19`, and its
returned scores are then re-weighted by three strictly positive post-chain
multipliers, each re-expressed from its tested source file:

  LEG 1 — dividend SIZE, source strat_l20a_divyield (round 1, md5
    2fdd0652...): y_j(t) = clip(log R(t2)/R(t1), 0, 0.01*dy_lb) with
    R = adj_close/close, t2/t1 = last daily bars strictly before months[t] /
    months[t - dy_lb]; tie-averaged cross-sectional percentile over the
    row's finite signal; tilt = 1 + dy_w*(2pct - 1).  Cell A window/weight:
    dy_lb 36 / dy_w -0.15 (favour NON-payers, the round-1 winner).

  LEG 2 — dividend TIMING (event count), source strat_l20a_divregular
    (round 1, md5 a6e08145...): event iff a daily R-step > 1e-4; n_j(t) =
    #events in (t1, t2]; same tie-averaged percentile; tilt = 1 + dv_w*(2pct
    - 1).  Cell A window/weight: dv_lb 24 / dv_w -0.15 (favour INFREQUENT
    payers).  Legs 1+2 together are exactly strat_l20a2_divcombo (round 2,
    md5 c8194563...) in mode "prod" at cell A — which posted
    train +103.617 / -16.556 / 6.259, fwd +55.673 / -10.381.

  LEG 3 — Corwin-Schultz spread LEVEL, source strat_l20b_spread (designer B,
    md5 ad974a8d...): the CS two-day spread estimator per consecutive-bar
    pair (Corwin & Schultz 2012, J. Finance 67(2), eqs. 3-5, negative
    estimates floored at 0, pairs <1 or >7 calendar days apart dropped),
    averaged inside calendar-month buckets, then averaged over the trailing
    window of buckets [t - sp_lb, t - 1]; cross-sectional percentile among
    names passing the coverage guard (>= ceil(sp_frac * sp_lb) finite
    buckets, sp_frac pinned 0.5); tilt = 1 + sp_w*(2pct - 1).  Promoted
    tight-spread cell: sp_lb 4 / sp_w -0.05 (favour TIGHT spread = execution
    quality), with sp_w -0.1 as the documented dose neighbour.

COMPOSITION CHOICE (documented, per the brief): the two parents' score()
functions CANNOT be composed by chaining — each one RESTARTS from its own
`_l19(panels, p)` call and returns a fresh array, so calling spread.score()
after divcombo.score() would simply DISCARD the dividend legs (and calling
them in the other order discards the spread leg); each parent's contract is
"delegate, then tilt", not "tilt the scores you were handed". The only
faithful composition is therefore: ONE _l19 call + the parents' imported
math applied in sequence. This file imports the tested helpers rather than
copying them — `_trail_yield` and `_pct_tie` from strat_l20a_divyield,
`_signals` from strat_l20a_divregular, `_tilt_row` from strat_l20a2_divcombo
(the tie-averaged tilt block itself), and `_monthly_spread` from
strat_l20b_spread (the whole CS estimator) — so no indicator exists twice;
only the two application blocks are re-expressed inline, cited line-for-line
from their sources. Each leg keeps its SOURCE's percentile convention
(dividend legs: tie-averaged `_pct_tie`, because those signals carry mass
ties at zero; spread leg: the stable-argsort position rank exactly as
strat_l20b_spread writes it, where continuous CS means rarely tie) —
faithfulness to each screened parent outranks internal uniformity.

Application order (documented; multiplication is commutative, the order only
matters for reproduction): Leg 1 -> Leg 2 (exactly divcombo mode "prod", cell
A) -> Leg 3 (spread). Every leg multiplies FINITE score entries only, NaN
stays NaN, rows before that leg's window (t < dy_lb / dv_lb / sp_lb) are
untouched, names failing a leg's signal/coverage guard keep tilt exactly 1.0
(re-ranking, never a gate — the round-1 gates were measured destructive and
are NOT carried), and |weight| < 1 keeps every multiplier strictly positive.

PIT argument — both channels, only bars strictly before months[t]:
 - dividend legs (inherited verbatim by calling the round-1/2 builders): the
   LEVEL of R = adj_close/close is NOT pit-clean (it embeds every future
   dividend); every signal here is a trailing WINDOW ending at the last bar
   strictly before months[t] and starting at the last bar strictly before
   months[t-k] < months[t], so distributions after the window's end sit in
   both endpoints of the ratio and cancel — only events public at the
   decision survive.
 - spread leg (inherited from strat_l20b_spread): bucket k of
   _monthly_spread holds only pairs whose CARRYING (second) bar falls in
   [months[k], months[k+1]); the window read at row t is buckets
   [t-sp_lb, t-1], whose bars all have date < months[t] (a pair is only used
   once its second bar is inside the bucket, so the estimate never reaches
   row t before both its bars do).
 - Each percentile at row t uses only that row's backward cross-section; no
   row > t is read anywhere; the champion delegate's PIT (ids: daily bars
   strictly before months[t]; la: static listing_date; or: px[t-or_lb]..px[t];
   cap: month-t ranks) is unchanged. All three legs sit POST-cap, matching
   every parent (Loop-20 tiltorder lesson: placement is a mechanism — the
   screened order is preserved).

Import chain: strat_l20a3_divspread -> strat_l19a_balanced.score (champion ->
strat_l12b_gatefail -> floorhighfastgate/floorhighsustaincond/
floorhightiershape + wobble -> ids tilt from strat_l15b_insideday -> mirrored
cap -> listage tilt from strat_l17c_listage -> outrank tilt from
strat_l16b_outrank) AND -> strat_l20a_divyield (_trail_yield, _pct_tie) ->
strat_l20a_divregular (_signals) -> strat_l20a2_divcombo (_tilt_row) ->
strat_l20b_spread (_monthly_spread).

Off-switch identity: with the neutral defaults set via setdefault BEFORE
delegating (gf_lb 12 / gf_w 0.0 / gw_w 0.0 — the values
strat_l19a_balanced sets itself, Loop-14 rule — plus dy_w 0.0, dv_w 0.0,
sp_w 0.0), NO leg is armed and the function returns `_l19(panels, p)`
untouched: bitwise champion scores.

Flat-base metric (off-switch must reproduce exactly, champion params passed
by the caller): train +98.682% / DD -15.506% / calmar 6.364 / H1 +95.295% /
H2 +101.966% / fwd +53.148% / fwd DD -10.403% / full +79.237% / -20.728%.

Pre-registered question (Loop-20 final recorded screen — window too short for
promotion-grade verification, so this is a FRONTIER SIBLING, not a promotion
candidate): do TWO DIFFERENT CHANNELS stack? Prior evidence in this loop:
same-axis compositions INTERFERE (illiquidity x spread — both load on
turnover-adjusted price movement — best combo 102.1, BELOW both parents
102.4 and 103.8, avg form below base), while different transforms of one NEW
channel were super-additive but paid DD (dividend size x timing: 103.6 vs an
additive prediction of 101.1, +2.5pp beyond additivity, DD -16.6). This file
composes ACROSS channels: corporate-action factor (fundamental cash-return
behaviour) x liquidity/spread (microstructure cost). Parents on this base:
    divcombo cell A : train +103.617 / -16.556 / 6.259, fwd +55.673 / -10.381
    spread (4,-0.05): train +102.990 / -15.510 / 6.640, fwd +54.060 / -10.381
    base            : train +98.682 / -15.506 / 6.364, fwd +53.148 / -10.403
    additive train prediction = 98.682 + 4.935 + 4.308 = 107.925
Verdict rules, fixed before the runs:
    STACK     : train > 103.617 (beats BOTH parents) AND train DD >= -16.556
                (no worse than the worse parent) AND fwd >= 54.06 (at least
                the weaker parent's forward) AND fwd DD >= -10.403.
    INTERFERE : train < 102.990 (below BOTH parents), or calmar < 6.259
                (worse than both parents) at train below the better parent.
    SATURATE  : anything between — beats one parent but not both, or matches
                the better parent within 0.3pp without improving risk.

Falsification test (exact): if the composed cell fails STACK and lands at or
below the better parent, the cross-channel hypothesis (the new L20 finding
generalised: compose ACROSS channels, not within one) fails for
action-factor x spread at this base, and the negative is recorded as the
screen's verdict.

NOVELTY STATEMENT (closest prior art -> the ONE thing that changed): the
closest prior art is the four parent files — strat_l20a2_divcombo (the
dividend A cell composed), strat_l20a_divyield / strat_l20a_divregular (its
two transforms, zero prior dividend/adj/corporate/payout rows in
research/tested_mechanisms.tsv), and strat_l20b_spread (the CS tilt). NO file
in this tree has ever measured a composition BETWEEN the corporate-action
channel and a liquidity/spread channel — that cross-channel product is the
ONE thing that changed. The new Loop-20 finding this file tests the
generalisation of: same-axis compositions interfere (illiq x spread — both
load on the same turnover-adjusted price movement — combined BELOW both
parents) while a genuinely new channel's composition can stack; the
cross-channel composition of a fundamental cash-return signal with a
microstructure cost signal has never been screened. A "same signal, new
weights" re-shape is explicitly NOT what is being claimed: both legs are
already-screened signals on DIFFERENT data channels, combined for the first
time, with each leg re-used from its source file rather than re-tuned.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1; max_hold 3 is a HARNESS key)
        + dy_lb [36] (pinned: divcombo cell-A SIZE window)
        + dy_w  {0.0, -0.15}  SIZE tilt weight (0 = leg off)
        + dv_lb [24] (pinned: divcombo cell-A TIMING window)
        + dv_w  {0.0, -0.15}  COUNT tilt weight (0 = leg off)
        + sp_lb [4]  (pinned: promoted tight-spread window)
        + sp_w  {0.0, -0.05, -0.1}  spread tilt weight (0 = leg off;
                 -0.05 promoted dose, -0.1 the dose neighbour from the
                 Loop-20 dose-dependence lesson)
        + sp_frac [0.5] pinned (coverage guard, as in strat_l20b_spread)
        Documented cells (4): (1) identity — dy_w 0, dv_w 0, sp_w 0;
        (2) prod(divcombo A: 36/-0.15 x count 24/-0.15) x spread(4,-0.05);
        (3) same with spread(4,-0.1); (4) divcombo A ALONE (spread off) —
        the parent control that must reproduce 103.617/-16.556/6.259,
        fwd 55.673/-10.381 for the composition to be believed.
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l19a_balanced import score as _l19
from strat_l20a2_divcombo import _tilt_row
from strat_l20a_divregular import _signals
from strat_l20a_divyield import _trail_yield
from strat_l20b_spread import _monthly_spread

NEEDS_DAILY = True  # champion ids leg + spread leg both read the daily panel

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
    "dy_lb": [36],                   # pinned: divcombo cell-A SIZE window
    "dy_w": [0.0, -0.15],            # SIZE leg; 0 = off
    "dv_lb": [24],                   # pinned: divcombo cell-A TIMING window
    "dv_w": [0.0, -0.15],            # COUNT leg; 0 = off
    "sp_lb": [4],                    # pinned: promoted tight-spread window
    "sp_w": [0.0, -0.05, -0.1],      # spread leg; 0 = off, -0.05 promoted
    "sp_frac": [0.5],                # pinned coverage guard
}


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-13/14 imported-defaults leak):
    # the same three strat_l19a_balanced sets itself, plus this file's legs at
    # OFF and their tested windows. Champion keys (gw_w 0.15, ids_w -0.13,
    # la_w 0.5, or_w -0.1, ...) are PASSED by the caller, never defaulted here.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    p.setdefault("dy_lb", 36)
    p.setdefault("dy_w", 0.0)
    p.setdefault("dv_lb", 24)
    p.setdefault("dv_w", 0.0)
    p.setdefault("sp_lb", 4)
    p.setdefault("sp_w", 0.0)
    p.setdefault("sp_frac", 0.5)
    out, regime = _l19(panels, p)          # champion scores, cap included
    out = np.array(out, dtype=float, copy=True)

    dy_w = float(p["dy_w"])
    dv_w = float(p["dv_w"])
    sp_w = float(p["sp_w"])
    if dy_w == 0.0 and dv_w == 0.0 and sp_w == 0.0:
        return out, regime                  # off-switch: bit-exact identity

    months, cols = panels["months"], panels["cols"]
    T = out.shape[0]

    # ---- LEG 1 + LEG 2: exactly strat_l20a2_divcombo mode "prod" at cell A
    # (source blocks cited in the docstring); _tilt_row carries the tested
    # tie-averaged tilt math, the signal matrices come from the round-1
    # builders ----
    if dy_w != 0.0:
        Y = _trail_yield(months, cols, int(p["dy_lb"]))
        for t in range(int(p["dy_lb"]), T):
            tilt = _tilt_row(Y[t], dy_w)
            if tilt is None:
                continue
            fin = np.isfinite(out[t])
            out[t, fin] = out[t, fin] * tilt[fin]   # NaN stays NaN
    if dv_w != 0.0:
        CNT, _REC = _signals(months, cols, int(p["dv_lb"]))
        for t in range(int(p["dv_lb"]), T):
            tilt = _tilt_row(CNT[t], dv_w)
            if tilt is None:
                continue
            fin = np.isfinite(out[t])
            out[t, fin] = out[t, fin] * tilt[fin]   # NaN stays NaN

    # ---- LEG 3: re-expressed from strat_l20b_spread.score (CS estimator via
    # its imported _monthly_spread; percentile/coverage/tilt block cited
    # line-for-line from that file: stable-argsort position rank over names
    # passing the coverage guard, tilt 1 + sp_w*(2pct-1), finite entries
    # only) ----
    if sp_w != 0.0:
        daily = panels["daily"]
        slb = int(p["sp_lb"])
        need = max(2, int(np.ceil(float(p["sp_frac"]) * slb)))
        SPR = _monthly_spread(daily, months, cols)
        for t in range(slb, T):
            win = SPR[t - slb : t]         # buckets t-slb..t-1: date < months[t]
            cnt = np.isfinite(win).sum(axis=0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                val = np.nanmean(win, axis=0)
            valid = np.isfinite(val) & (cnt >= need)   # coverage guard -> 1.0
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = val[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + sp_w * (2.0 * pct - 1.0)
            fin = np.isfinite(out[t])
            out[t, fin] = out[t, fin] * tilt[fin]       # NaN stays NaN
    return out, regime
