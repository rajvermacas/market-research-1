"""Candidate: cross-channel composition of the two Loop-20 KEEPs — Amihud
illiquidity (strat_l20b_illiq) x dividend-factor size+count
(strat_l20a2_divcombo) — on the L19 champion chain (strategy_lab contract).

Setup in words: the L19 champion chain strat_l19a_balanced is called EXACTLY
ONCE (`from strat_l19a_balanced import score as _l19`) and its returned scores
are re-weighted POST-chain by up to THREE strictly positive cross-sectional
percentile tilts, each a verbatim re-expression of a Loop-20
KEEP-not-promoted sibling (all three re-expressions are line-for-line copies
of the parent files' tested blocks, cited below):

  LEG 1 — Amihud illiquidity (source strat_l20b_illiq, KEEP at il_lb 12 /
    il_w +0.1 -> train 102.35/-15.98, footprint 30/139): per (month, name)
    the mean daily |close/prev_close - 1| / (close * volume) over the
    trailing il_lb-month buckets t-il_lb..t-1, percentile-ranked
    cross-sectionally among names with >= ceil(il_frac*il_lb) finite buckets,
    tilt = 1 + il_w*(2*pct - 1). il_w > 0 favours ILLIQUID names.
  LEG 2 — dividend-factor SIZE (source strat_l20a_divyield via
    strat_l20a2_divcombo mode "prod"): trailing dy_lb-month mean of the
    adjustment-factor change magnitude (adj_close/close ratio changes at
    ex-dates), percentile tilt 1 + dy_w*(2pct-1).
  LEG 3 — dividend-factor COUNT (source strat_l20a_divregular via
    strat_l20a2_divcombo mode "prod"): trailing dv_lb-month count of
    adjustment-factor events, percentile tilt 1 + dv_w*(2pct-1).

All three multipliers are strictly positive (|w| < 1), applied only to the
finite entries of the champion's returned scores; NaN stays NaN; names failing
a coverage guard keep tilt exactly 1.0 (never NaN-ed — re-ranking, not a
gate). The legs multiply, so the composed book is the champion's capped pool
re-ordered by the PRODUCT of the three signals.

Hypothesis: L20's within-channel and champion-paired compositions interfered
(illiq x spread = strat_l20b2_liqcombo DEAD at 102.14; dividend x spread =
strat_l20a3_divspread 101.88 on train), but the cross-channel composition
INSIDE the dividend channel was super-additive (strat_l20a2_divcombo +2.5pp
beyond an additive prediction). This file asks whether the illiquidity channel
and the dividend-factor channel — two different economic quantities (price
impact vs cash-return events), both individually KEEPs on the L19 base —
compose across channels or interfere. If they interfere, the pair is closed.

Falsifier: if every cell trails the better parent (divcombo: train +103.617 /
DD -16.556 / calmar 6.26) on train CAGR, or buys a train gain with a DD wider
than -16.556, the composition interferes and the pair closes. Before ANY
promotion: count the decision months where the composed picks differ from the
L19 champion's (Loop-16 lesson) — a gain sourced from a handful of
name-months is a sample of a handful, not an edge.

NOVELTY STATEMENT (closest registry rows -> the ONE thing changed):
- research/tested_mechanisms.tsv: strat_l20b_illiq (KEEP 102.35, il_lb 12 /
  il_w +0.1) and strat_l20a2_divcombo (KEEP 103.62, prod (36,-0.15)x
  (count,-0.15)) — the two parents, never composed with EACH OTHER.
- strat_l20b2_liqcombo (DEAD, illiq x spread interference: best 102.14) and
  strat_l20a3_divspread (SCREENING-SIBLING, dividend x spread interference on
  train 101.88) — both prior L20 compositions paired a channel with the
  SPREAD term; neither paired illiquidity with the dividend factor.
WHAT CHANGED: the pair. This is the only composition of the two KEEPs, and
the first cross-channel pair whose parents both sit ABOVE the L19 base on
train (102.35 and 103.62 vs 98.68).

Import chain: strat_l21o_liqdiv -> strat_l19a_balanced.score (L19 champion
chain: gatefail lift -> ids tilt -> cap -> listing-age tilt -> outrank tilt)
-> strat_l12b_gatefail.score -> floorhighfastgate + sustaincond + tiershape.
Tilt helpers imported from their source files: _monthly_illiq
(strat_l20b_illiq), _tilt_row (strat_l20a2_divcombo), _trail_yield
(strat_l20a_divyield), _signals (strat_l20a_divregular).

PIT argument: identical to the parents'. ILQ bucket k contains only bars with
date < months[k+1]; the window read at row t is buckets [t-il_lb, t-1] whose
bars all have date < months[t]. The dividend signals are built from the
adjustment-factor series by the parents' own builders (bucket-t-1-and-older
convention). Every percentile uses only the row's backward cross-section; no
row > t is read anywhere.

Off-switch identity: il_w = 0.0 AND dy_w = 0.0 AND dv_w = 0.0 (this file's OWN
setdefaults, applied BEFORE delegating) returns `_l19`'s scores bitwise. The
L19 champion keys are always PASSED by the caller, never defaulted here.

Flat-base metric (off-switch must reproduce exactly): train +98.682% /
DD -15.506% / calmar 6.364 / H1 +95.295% / H2 +101.966% / fwd +53.148% /
fwd DD -10.403% / full +79.237% / full DD -20.728%.

Keys consumed: il_w, il_lb, il_frac, dy_w, dy_lb, dv_w, dv_lb; everything else
flows through to the delegate.

SPACE = L19 champion keys pinned (gw_w 0.15, ids_lb 3, ids_w -0.13, la_w 0.5,
        or_lb 6, or_w -0.1, cap_weak 11, cap_full 20, ...) + max_hold 3 (a
        harness key passed via params-json)
        + documented variants:
          identity            (il 0.0, dy 0.0, dv 0.0) -> L19 base
          IL parent           (il_lb 12, il_w +0.1)
          DIV parent          (dy_lb 36, dy_w -0.15, dv_lb 24, dv_w -0.15)
          FULL stack          (both parents' doses together)
          FULL half doses     (il_w +0.05, dy_w -0.075, dv_w -0.075)
          FULL other il_lb    (il_lb 6, il_w +0.1, dy/dv parent doses)
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l19a_balanced import score as _l19
from strat_l20a2_divcombo import _tilt_row
from strat_l20a_divregular import _signals
from strat_l20a_divyield import _trail_yield
from strat_l20b_illiq import _monthly_illiq

NEEDS_DAILY = True  # the delegate's ids term reads daily; LEG 1 reads it too

SPACE = {
    # L19 champion keys (pinned, docs only)
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "cap_full": [20],
    "cap_weak": [11],
    "fast_ma": [5],
    "floor_lb": [19],
    "gf_lb": [12],
    "gf_w": [0.0],
    "gw_w": [0.15],
    "ids_lb": [3],
    "ids_w": [-0.13],
    "la_min": [0],
    "la_w": [0.5],
    "lookback": [12],
    "max_dist": [0.055],
    "or_lb": [6],
    "or_w": [-0.1],
    "regime_ma": [18],
    "sustain_hi": [2],
    "sustain_lo": [3],
    "tier_lo": [0.9999],
    "tier_mid": [0.9999],
    # this file's keys
    "il_lb": [12, 6],
    "il_w": [0.0, 0.1, 0.05],
    "il_frac": [0.5],
    "dy_lb": [36],
    "dy_w": [0.0, -0.15, -0.075],
    "dv_lb": [24],
    "dv_w": [0.0, -0.15, -0.075],
}


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-13/14 imported-defaults leak):
    # this file's own keys default to the off-switch / pinned windows whatever
    # the caller passes; the delegate neutralises ITS leakable defaults
    # (gf_w 0.05 / gw_w) inside strat_l19a_balanced.
    p.setdefault("il_w", 0.0)
    p.setdefault("il_lb", 12)
    p.setdefault("il_frac", 0.5)
    p.setdefault("dy_w", 0.0)
    p.setdefault("dy_lb", 36)
    p.setdefault("dv_w", 0.0)
    p.setdefault("dv_lb", 24)
    out, regime = _l19(panels, p)  # L19 champion chain, verbatim
    out = np.array(out, dtype=float, copy=True)

    il_w = float(p["il_w"])
    dy_w = float(p["dy_w"])
    dv_w = float(p["dv_w"])
    if il_w == 0.0 and dy_w == 0.0 and dv_w == 0.0:
        return out, regime  # off-switch: bitwise copy of the L19 base

    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    T = out.shape[0]

    # ---- LEG 1: re-expressed from strat_l20b_illiq.score (Amihud estimator
    # via its imported _monthly_illiq; percentile/coverage/tilt block copied
    # line-for-line from that file) ----
    if il_w != 0.0:
        ilb = int(p["il_lb"])
        need = max(2, int(np.ceil(float(p["il_frac"]) * ilb)))
        ILQ = _monthly_illiq(daily, months, cols)
        for t in range(ilb, T):
            win = ILQ[t - ilb : t]  # buckets t-ilb..t-1: all date < months[t]
            cnt = np.isfinite(win).sum(axis=0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                val = np.nanmean(win, axis=0)
            valid = np.isfinite(val) & (cnt >= need)  # coverage guard
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = val[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + il_w * (2.0 * pct - 1.0)
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt, np.nan)

    # ---- LEG 2 + LEG 3: exactly strat_l20a2_divcombo mode "prod" (its tested
    # leg code, copied line-for-line; _tilt_row carries the tie-averaged tilt
    # math, the signal matrices come from the round-1 builders) ----
    if dy_w != 0.0:
        Y = _trail_yield(months, cols, int(p["dy_lb"]))
        for t in range(int(p["dy_lb"]), T):
            tilt = _tilt_row(Y[t], dy_w)
            if tilt is None:
                continue
            fin = np.isfinite(out[t])
            out[t, fin] = out[t, fin] * tilt[fin]  # NaN stays NaN
    if dv_w != 0.0:
        CNT, _REC = _signals(months, cols, int(p["dv_lb"]))
        for t in range(int(p["dv_lb"]), T):
            tilt = _tilt_row(CNT[t], dv_w)
            if tilt is None:
                continue
            fin = np.isfinite(out[t])
            out[t, fin] = out[t, fin] * tilt[fin]  # NaN stays NaN

    return out, regime
