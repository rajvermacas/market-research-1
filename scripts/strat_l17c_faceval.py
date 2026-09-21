"""Candidate: face-value tilt on the champion book (strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l15b_insideday (floor-lift
fresh-print rank among short-trend-passing, print-continuity-passing names,
breadth-tier exposure with tier 0.9999, regime-conditional cap cap_weak/
cap_full, eligibility-wobble gw_w 0.15, inside-day tilt ids_w -0.13 / lb 3) —
is imported wholesale via strat_l15b_insideday.score. Before the
regime-conditional cap step (mirrored inline, exactly as strat_l13a_concwobble
mirrors it), the imported lift is re-weighted by a NEW static attribute:
the name's NOMINAL FACE VALUE from the universe snapshot.

    fv[j]      = universe `face_value` (coverage verified BEFORE building:
                 0 nulls on all 2,559 symbols; discrete ladder — FV 1: 537,
                 2: 492, 5: 245, 10: 1,276 names, remainder 9)
    pct[j]     = cross-sectional percentile of fv among all columns
    tilt[j]    = 1 + fv_w * (2 * pct[j] - 1)   # fv_w > 0 favours HIGH FV
    out[t]     = ids-tilted lift[t] * tilt      # t >= 1; NaN lift stays NaN

Because face value is a static per-name attribute, the tilt is a fixed
per-name handicap (percentile order row-independent, as in
strat_l17c_listage).

Hypothesis: the daily panel is corporate-action ADJUSTED, so a name's
split/bonus history has been erased from its price series — every name
looks like a smooth log series. Face value recovers part of that lost
information statically: the denomination ladder (1 / 2 / 5 / 10) is a
proxy for HOW OFTEN a share was sliced (FV drops with each split) and for
its listing era (post-2010 listings standardized on FV 1-2; classic
companies carry FV 10). Two hypotheses, opposite signs: (a) split-heavy
small-FV names are serially recycled ("retail-friendly" share price
management) — their fresh highs mean-revert, so a HIGH-FV tilt
(fv_w > 0) lifts the cut's quality; (b) small-FV names are the young,
splitting, growing cohort and their prints are the genuine growth
breakouts — a LOW-FV tilt would. Note the attribute is deliberately NOT
price level (strat_l17c_pxlevel, this loop): a ₹1-FV share can trade at
₹2,000 and a ₹10-FV share at ₹40 — denomination is orthogonal to the
market price — and deliberately NOT listing age (strat_l17c_listage):
FV tracks split history, which a company's age does not (an old name that
split to FV 1 ranks young on fv but old on listage — the two attributes
disagree exactly where this screen can add something).

NOVELTY STATEMENT: the mechanism inventory has NO face-value or
corporate-action-attribute entry. Closest prior art: (i) the DEAD
sector/industry family (the only other universe-attribute family — 80%
null; face_value has 0 nulls, checked first); (ii) strat_l17c_pxlevel
(this loop — market price LEVEL; this file is the NOMINAL denomination, a
different column with a different economic reading: split/corporate-action
history, not affordability/tick granularity). The one thing changed: a new
static attribute (nominal face value) whose information content — split
recycling and listing era — is not carried by any price series term in the
chain (the panel is adjusted, which is precisely why the attribute can add
something). Not a re-shape of any dead family.

Snapshot caveat: face value is TODAY's value; splits change it going
forward, so past decisions read today's label — the same snapshot
limitation as the index flags and the series label, stated up front.

Import chain: strat_l17c_faceval -> strat_l15b_insideday.score -> cap step
mirrored inline from strat_floorhightiershapeconc.score /
strat_l13a_concwobble.score.

PIT argument: the attribute is static and read from the universe file; no
panel data is touched for it. The tilt multiplies rows t >= 1; the cap
reads month-t ranks only.

Off-switch identity: fv_w = 0.0 (default) leaves the tilt block skipped,
so `out` is bitwise the ids lift and the mirrored cap yields bitwise the
champion's scores at the same params. Champion keys are PASSED by the
caller, not defaulted here.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

PROMOTION PRECONDITION (Loop-16 lesson): the tilt re-orders the top-15 cut
(book composition) — count differing decision months vs the champion
before believing any gain.

Falsifier: if every tested fv_w trails the flat base — train +96.882% /
DD -17.032% / calmar 5.688 — the nominal denomination carries no selection
information beyond the champion chain (and beyond the age and price-level
tilts already screened this loop), and the static-attribute axis closes at
this base.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key passed via params-json, not consumed
        here)
        + fv_w {+0.2, +0.4, -0.2, -0.4} (percentile tilt; 0.0 = off-switch;
          positive favours high face value / rarely-split names).
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
    "fv_w": [0.2, 0.4, -0.2, -0.4],
}

_UNI_CACHE: dict = {}


def _face_values() -> dict:
    if "fv" not in _UNI_CACHE:
        root = Path(__file__).resolve().parents[1]
        u = pl.read_parquet(root / "data" / "universe" / "nse_universe.parquet")
        _UNI_CACHE["fv"] = dict(zip(u["symbol"].to_list(), u["face_value"].to_list()))
    return _UNI_CACHE["fv"]


def score(panels, params):
    lift, exposure = _ids_score(panels, params)
    out = np.array(lift, dtype=float, copy=True)

    fv_w = float(params.get("fv_w", 0.0))
    if fv_w != 0.0:
        fv = _face_values()
        fv_vec = np.array([fv.get(s, np.nan) for s in panels["cols"]], dtype=float)
        tilt = np.ones(len(panels["cols"]))
        valid = np.flatnonzero(np.isfinite(fv_vec))
        if valid.size >= 5:
            order = valid[np.argsort(fv_vec[valid], kind="stable")]
            pct = np.empty(valid.size)
            pct[order] = np.arange(valid.size) / (valid.size - 1)
            tilt[valid] = 1.0 + fv_w * (2.0 * pct - 1.0)
        for t in range(1, out.shape[0]):
            ok = np.isfinite(lift[t])
            out[t] = np.where(ok, lift[t] * tilt, np.nan)

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
