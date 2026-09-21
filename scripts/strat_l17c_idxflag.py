"""Candidate: index-membership tilt on the champion book (strategy_lab
contract).

Setup in words: the CURRENT champion chain — strat_l15b_insideday (floor-lift
fresh-print rank among short-trend-passing, print-continuity-passing names,
breadth-tier exposure with tier 0.9999, regime-conditional cap cap_weak/
cap_full, eligibility-wobble gw_w 0.15, inside-day tilt ids_w -0.13 / lb 3) —
is imported wholesale via strat_l15b_insideday.score. Before the
regime-conditional cap step (mirrored inline, exactly as strat_l13a_concwobble
mirrors it), the imported lift is re-weighted by a NEW non-price attribute:
the name's membership in a Nifty index flag from the universe snapshot.

    member[j] = 1.0 if universe[ix_key][j] else 0.0   (ix_key: one of the
                 seven flags; coverage verified BEFORE building: 0 nulls on
                 all 2,559 symbols; counts 50/50/100/200/500/150/250)
    tilt[j]   = 1 + ix_w * (2 * member[j] - 1)   # members get +ix_w,
                 non-members -ix_w
    out[t]    = ids-tilted lift[t] * tilt        # t >= 1; NaN lift stays NaN

The optional `ix_gate` (0/1, default 0) instead cuts ELIGIBILITY: when 1,
non-members read NaN for every row — a book-composition variant, not a
re-weighting. A binary attribute makes the percentile convention trivial:
the tilt is a two-level handicap (member / non-member), the crudest
expression of the attribute.

Hypothesis: the champion buys fresh 12-month-high printers and its ids term
already re-ranks the tape; this mechanism asks whether TODAY's index
membership — an institutional-sponsorship attribute no price series carries —
adds selection information. Direction genuinely unknown ex ante:
(a) index members are wider-owned, better-arbitraged names — their breakouts
are more expensive and slower to continue (the standing large/mid-cap train
drag in this repo suggests a NEGATIVE member tilt, i.e. ix_w < 0 favours
non-members); (b) membership is a liquidity/float-quality floor that keeps
the book tradable and lets winners be held to their prints (positive tilt).
The screen answers which — or neither.

SURVIVORSHIP CAVEAT (the axis brief demands it, and it changes how any
result may be read): the flags are TODAY's snapshot, not point-in-time
membership. A name flagged in Nifty 500 today was not necessarily a member
at a 2016 decision date — a positive train result is contaminated by
membership look-ahead (today's members were selected BY the trailing
returns the backtest then measures). The mechanism is therefore falsifiable
in one direction only: it is DISCONFIRMED by the tilt doing nothing or
harming, and a train "gain" carries no evidential weight at all — the only
readable signal would be a train-NEUTRAL configuration whose forward window
(2022+, closest in time to the snapshot) improves over the champion, and
even that reads as an attribute proxy, never promotable on train evidence.

NOVELTY STATEMENT: the mechanism inventory has NO index-membership entry —
the closest prior art is (i) sector/industry neutrality (DEAD: 80%-null
`industry`; this file's flags have 0 nulls and exact counts, checked first)
and (ii) the harness-level `--universe nifty500` runs, which change the
PANEL, not the score. The one thing changed: membership acts as a
score-level tilt/gate INSIDE the nse_all book, so the breadth tiers, gates
and wobble continue to be computed on the full board while the pick is
re-weighted by the attribute — a channel (static index-membership flag)
nothing in the chain consumes. Not a re-shape of any dead family: no
volume, no tape geometry, no breadth derivative, no rank smoothing.

Import chain: strat_l17c_idxflag -> strat_l15b_insideday.score -> cap step
mirrored inline from strat_floorhightiershapeconc.score /
strat_l13a_concwobble.score.

PIT argument: the flag is a static attribute read from the universe file —
no panel data is touched for it. (Its PIT-invalidity is the survivorship
caveat above, not a window violation.) The tilt multiplies rows t >= 1;
the gate cuts month-t eligibility only; the cap reads month-t ranks only.

Off-switch identity: ix_key unset/empty (default), or ix_w = 0.0 with
ix_gate = 0, leave tilt a vector of exact 1.0 and the gate empty, so `out`
is bitwise the ids lift and the mirrored cap yields bitwise the champion's
scores at the same params. Champion keys are PASSED by the caller, not
defaulted here.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

PROMOTION PRECONDITION (Loop-16 lesson): both the tilt (at |ix_w| large
enough to re-order the top-15 cut) and especially ix_gate are
book-composition mechanisms — count differing decision months vs the
champion before believing any gain.

Falsifier: if every tested (ix_key, ix_w, ix_gate) combination trails the
flat base — train +96.882% / DD -17.032% / calmar 5.688 — then index
membership carries no information the champion chain does not already
consume, and the index-flag attribute axis closes at this base. Given the
snapshot caveat, the expected outcome — and the useful one either way — is
that the flag adds nothing: then it is recorded as DEAD with the caveat
that the negative is cleaner than any positive could have been.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key passed via params-json, not consumed
        here)
        + ix_key {"in_nifty500", "in_niftysmallcap250"} (flag consumed)
        + ix_w {+0.2, -0.2, +0.4, -0.4} (two-level tilt; 0.0 = off-switch)
        + ix_gate {0, 1} (0 = off; 1 = eligibility cut on non-members).
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
    "ix_key": ["", "in_nifty500", "in_niftysmallcap250"],
    "ix_w": [0.2, -0.2, 0.4, -0.4],
    "ix_gate": [0, 1],
}

_UNI_CACHE: dict = {}


def _flags() -> dict:
    if "u" not in _UNI_CACHE:
        root = Path(__file__).resolve().parents[1]
        _UNI_CACHE["u"] = pl.read_parquet(
            root / "data" / "universe" / "nse_universe.parquet")
    return _UNI_CACHE["u"]


def score(panels, params):
    lift, exposure = _ids_score(panels, params)
    out = np.array(lift, dtype=float, copy=True)

    ix_key = str(params.get("ix_key", "") or "")
    ix_w = float(params.get("ix_w", 0.0))
    ix_gate = int(params.get("ix_gate", 0) or 0)
    if ix_key and (ix_w != 0.0 or ix_gate):
        u = _flags()
        if ix_key in u.columns:
            member = {s: bool(v) for s, v in
                      zip(u["symbol"].to_list(), u[ix_key].to_list())}
            tilt = np.array([1.0 + ix_w * (2.0 * float(member.get(s, False)) - 1.0)
                             for s in panels["cols"]])
            for t in range(1, out.shape[0]):
                ok = np.isfinite(lift[t])
                out[t] = np.where(ok, lift[t] * tilt, np.nan)
                if ix_gate:
                    nom = np.array([not member.get(s, False) for s in panels["cols"]])
                    out[t] = np.where(ok & ~nom, out[t], np.nan)

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
