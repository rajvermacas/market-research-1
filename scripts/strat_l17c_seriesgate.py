"""Candidate: trading-series eligibility attribute on the champion book
(strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l15b_insideday (floor-lift
fresh-print rank among short-trend-passing, print-continuity-passing names,
breadth-tier exposure with tier 0.9999, regime-conditional cap cap_weak/
cap_full, eligibility-wobble gw_w 0.15, inside-day tilt ids_w -0.13 / lb 3) —
is imported wholesale via strat_l15b_insideday.score. Before the
regime-conditional cap step (mirrored inline, exactly as strat_l13a_concwobble
mirrors it), the imported lift is re-weighted / re-eligibilized by a NEW
static attribute: the name's NSE TRADING SERIES from the universe snapshot.

    series[j]  = universe `series` value (coverage verified BEFORE building:
                 0 nulls on all 2,559 symbols; EQ 2,287 / BE 244 / BZ 28)
    tilt[j]    = 1 + sg_w * (2 * is_series(sg_key)[j] - 1)   # two-level
    gate       = when sg_gate 1: names whose series != sg_key read NaN
    out[t]     = ids-tilted lift[t] * tilt (then optional gate cut), t >= 1

Hypothesis (grounded in a diagnostic run BEFORE the file was written): the
champion book is NOT an EQ-only book — replaying the champion's own picks
month by month shows 85.7% EQ / 12.9% BE / 1.3% BZ held-name-months
(1,129 name-months, 2015-01 to 2026-08), i.e. roughly two of every fifteen
slots sit in trade-for-trade (BE) or surveillance (BZ) series whose fills
the backtest models as clean month-end closes. BE names trade in the
T2T segment (no intraday leverage, delivered settlement) and several carry
thin books; BZ names are under surveillance action. Two live hypotheses:
(a) those series carry the book's most fragile fills — the 25 bps cost
model understates their true cost, and their "fresh prints" are more often
illiquidity artifacts than sponsorship — so cutting them (sg_gate) trades
return for book quality and should show up as lower DD per unit of CAGR
given up; (b) BE/BZ names are exactly the neglected, sponsor-less microcaps
where 12-month-high momentum is strongest and cleanest (no derivatives
crowd) — the gate would be train-destructive, confirming the book NEEDS
them. The two-level tilt (sg_w) measures the same attribute without
changing eligibility.

NOVELTY STATEMENT: the mechanism inventory has NO trading-series entry.
Closest prior art within this loop: strat_l17c_idxflag (index-membership
attribute — a DIFFERENT universe column; series is the exchange's
settlement/surveillance segment, not institutional index membership, and
the two overlap weakly: the champion book is 86% EQ while also being ~0%
today's-Nifty500 members, so series is NOT a large-cap proxy). Also
distinct from every DEAD family: it is not a volume/liquidity gate (series
is a settlement-regime LABEL, not a flow measure), not sector, not a
count cap, not a tape re-rank. The one thing changed: a new static
attribute channel — the trading series label — that nothing in the chain
consumes.

Snapshot caveat: series is today's value; names migrate between series
over time (EQ<->BE on surveillance or shareholding changes), so the gate
reads today's label for past decisions — the same snapshot limitation as
the index flags, stated up front: train effects are read with that
asymmetry in mind, and the mechanism is DISCONFIRMED (cleanly) by doing
nothing or harming.

Import chain: strat_l17c_seriesgate -> strat_l15b_insideday.score -> cap
step mirrored inline from strat_floorhightiershapeconc.score /
strat_l13a_concwobble.score.

PIT argument: the series label is a static attribute read from the
universe file; no panel data is touched for it. The tilt multiplies rows
t >= 1; the gate cuts month-t eligibility only; the cap reads month-t
ranks only.

Off-switch identity: sg_key unset/empty (default) — or sg_w = 0.0 with
sg_gate = 0 on a set key — leaves tilt a vector of exact 1.0 and the gate
empty, so `out` is bitwise the ids lift and the mirrored cap yields
bitwise the champion's scores at the same params. Champion keys are PASSED
by the caller, not defaulted here.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

PROMOTION PRECONDITION (Loop-16 lesson): the gate is a book-composition
mechanism — count differing decision months vs the champion before
believing any gain (the diagnostic already says the gate touches ~14% of
held-name-months, so it is not a no-op).

Falsifier: if every tested (sg_key, sg_w, sg_gate) combination trails the
flat base — train +96.882% / DD -17.032% / calmar 5.688 — the trading
series carries no selection information beyond the champion chain, and the
series axis closes at this base. Note the two hypotheses cut in OPPOSITE
directions, so a tie on BOTH the gate and the tilt is informative: it
would mean the BE/BZ share of the book is return-neutral, i.e. the cost
model's 25 bps is neither flattered nor penalised by the trade-for-trade
names it models as liquid fills.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key passed via params-json, not consumed
        here)
        + sg_key {"", "EQ"} (series consumed; "" = off-switch)
        + sg_w {+0.2, -0.2} (two-level tilt; 0.0 = off-switch)
        + sg_gate {0, 1} (0 = off; 1 = eligibility cut on non-EQ names).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from strat_l15b_insideday import score as _ids_score

NEEDS_DAILY = True  # the delegate's ids term reads the daily panel (ids_w -0.13)

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
    "sg_key": ["", "EQ"],
    "sg_w": [0.2, -0.2],
    "sg_gate": [0, 1],
}

_UNI_CACHE: dict = {}


def _series() -> dict:
    if "s" not in _UNI_CACHE:
        root = Path(__file__).resolve().parents[1]
        u = pl.read_parquet(root / "data" / "universe" / "nse_universe.parquet")
        _UNI_CACHE["s"] = dict(zip(u["symbol"].to_list(), u["series"].to_list()))
    return _UNI_CACHE["s"]


def score(panels, params):
    lift, exposure = _ids_score(panels, params)
    out = np.array(lift, dtype=float, copy=True)

    sg_key = str(params.get("sg_key", "") or "")
    sg_w = float(params.get("sg_w", 0.0))
    sg_gate = int(params.get("sg_gate", 0) or 0)
    if sg_key and (sg_w != 0.0 or sg_gate):
        ser = _series()
        member = np.array([ser.get(s, "") == sg_key for s in panels["cols"]])
        tilt = 1.0 + sg_w * (2.0 * member.astype(float) - 1.0)
        for t in range(1, out.shape[0]):
            ok = np.isfinite(lift[t])
            out[t] = np.where(ok, lift[t] * tilt, np.nan)
            if sg_gate:
                out[t] = np.where(ok & member, out[t], np.nan)

    # cap step mirrored inline from strat_floorhightiershapeconc.score /
    # strat_l13a_concwobble.score (book-size composition, not an indicator)
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
