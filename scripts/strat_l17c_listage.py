"""Candidate: listing-age tilt on the champion book (strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l15b_insideday (floor-lift
fresh-print rank among short-trend-passing, print-continuity-passing names,
breadth-tier exposure with tier 0.9999, regime-conditional cap cap_weak/
cap_full, eligibility-wobble gw_w 0.15, inside-day tilt ids_w -0.13 / lb 3) —
is imported wholesale via strat_l15b_insideday.score. Before the
regime-conditional cap step (mirrored inline, exactly as strat_l13a_concwobble
mirrors it — a composition step, not an indicator), the imported lift is
re-weighted by a NEW non-price attribute: the name's LISTING AGE at the
decision month, from the universe's `listing_date` column.

    age_ref[j] = max(0, (months[-1] - listing_date_j).days) / 365.25
    pct[j]     = cross-sectional percentile of age_ref among columns with a
                 known listing date (coverage verified BEFORE building:
                 0 nulls on all 2,559 symbols, n_unique 1,643)
    tilt[j]    = 1 + la_w * (2 * pct[j] - 1)   # la_w > 0 favours OLD listings
    out[t]     = ids-tilted lift[t] * tilt      # t >= 1; NaN lift stays NaN

Because every name ages one year per year, the percentile ORDER of listing
age is static across rows — tilt is a fixed per-name handicap, not a
time-varying signal. The optional `la_min` gate instead cuts ELIGIBILITY:
names listed fewer than la_min years before the decision month read NaN.

Hypothesis: the champion buys fresh 12-month-high printers across today's
full listing board. Listing age is known ex ante (a name's listing date is
public before that name can be traded, so reading it for the decision at
months[t] is PIT-clean by construction) and it is the ONE board attribute
with 100% coverage — the same attribute channel where sector/industry
neutrality died purely because `industry` is 80% null. Two live hypotheses,
opposite signs: (a) OLD listings — long price history, wide float,
institutional sponsorship past the IPO hyper-growth phase — print 12-month
highs as continuation moves on a seasoned tape; (b) YOUNG listings — recent
IPOs carry post-listing sponsorship flows, thinner analyst coverage and a
neglected-firm premium, so their highs start fresher trends. Note the
champion's own lookback already filters some of this: a name needs ~13
months of closes to have a finite 12-month momentum, so the eligible book is
certainly not today's brand-new listings — the tilt acts on maturity WITHIN
the ~1-year-plus eligible cohort. If either asymmetry survives the
momentum/gate/ids stack, the tilt re-orders the top-15 cut; if the gates
already encode maturity, every variant ties the base and the attribute axis
closes.

Survivorship statement (asked for by the axis brief): the attribute is
PIT-clean (known ex ante), but the UNIVERSE is today's listing. A young-tilt
concentrates on names that both listed recently AND survived to the snapshot;
an old-tilt concentrates on long-listed survivors. The tilt therefore
measures survivorship-conditioned age effects, not the ex-ante IPO universe.

NOVELTY STATEMENT: the mechanism inventory has NO non-price-attribute entry
other than sector/industry neutrality (DEAD — 80%-null `industry` silently
degraded it into a no-op/market gate). The one thing changed: this file is
built on `listing_date`, whose coverage was CHECKED FIRST (0 nulls / 2,559;
listing years 1995-2026) — a populated attribute, in a channel (static
company attribute) nothing in the chain consumes. It is not a re-shape of
any dead family: no volume, no daily-tape geometry (ids/range/CLV), no
streaks or freshness, no breadth, no rank smoothing, no exposure shape
beyond the champion's own.

Import chain: strat_l17c_listage -> strat_l15b_insideday.score (which
imports strat_l12b_gatefail.score: fastgate + sustaincond + tiershape + the
wobble tilt + the ids tilt) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score.

PIT argument: listing_date is a static ex-ante attribute — no panel data is
read for it, nothing can peek. The tilt multiplies rows t >= 1 of the
imported lift (rows the harness reads only from start_i); the `la_min` gate
reads only months[t] and listing_date. The cap reads month-t ranks only.

Off-switch identity: la_w = 0.0 AND la_min = 0 (both defaults) make tilt a
vector of exact 1.0 and the gate cut empty, so `out` is bitwise the ids
lift and the mirrored cap yields bitwise the champion's scores at the same
params. Champion keys are PASSED by the caller, not defaulted here (the
delegate itself already neutralises gatefail's gf_w 0.05 leak and wobble
before its own tilt).

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

PROMOTION PRECONDITION (Loop-16 lesson): the la_w tilt changes which names
the cap keeps — a book-composition mechanism. Before any promotion, diff the
candidate's picks against the champion's month by month and count the months
that actually differ; a gain sourced from a handful of name-months is a
sample of a handful, not an edge.

Falsifier: if every tested (la_w, la_min) combination trails the flat base —
train +96.882% / DD -17.032% / calmar 5.688 — listing age carries no
information beyond the champion chain's rank, gates and ids tilt, and the
non-price-attribute axis closes at this base. (A train gain that coincides
with forward/DD deterioration is the family's known failure shape — the
ids term already saturates re-ranking on this book — so a forward-only
improvement would be recorded as a forward-alternative, never a train keep.)

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key passed via params-json, not consumed
        here)
        + la_w {+0.4, +0.2, -0.2, -0.4} (percentile tilt; 0.0 = off-switch;
          positive favours OLD listings, negative favours young)
        + la_min {0, 3, 5} years (0 = off; 3/5 = eligibility gate on age).
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
    "la_w": [0.4, 0.2, -0.2, -0.4],
    "la_min": [0, 3, 5],
}

_UNI_CACHE: dict = {}


def _listing_dates() -> dict:
    if "ld" not in _UNI_CACHE:
        root = Path(__file__).resolve().parents[1]
        u = pl.read_parquet(root / "data" / "universe" / "nse_universe.parquet")
        _UNI_CACHE["ld"] = dict(zip(u["symbol"].to_list(), u["listing_date"].to_list()))
    return _UNI_CACHE["ld"]


def score(panels, params):
    lift, exposure = _ids_score(panels, params)
    out = np.array(lift, dtype=float, copy=True)

    la_w = float(params.get("la_w", 0.0))
    la_min = float(params.get("la_min", 0.0) or 0.0)
    if la_w != 0.0 or la_min > 0.0:
        ld = _listing_dates()
        months, cols = panels["months"], panels["cols"]
        # static age percentile (order is row-independent; reference date is
        # the last month, negatives clipped at 0 — order unchanged)
        age_ref = np.full(len(cols), np.nan)
        for j, s in enumerate(cols):
            d0 = ld.get(s)
            if d0 is not None:
                age_ref[j] = max(0, (months[-1] - d0).days) / 365.25
        tilt = np.ones(len(cols))
        valid = np.flatnonzero(np.isfinite(age_ref))
        if valid.size >= 5:
            order = valid[np.argsort(age_ref[valid], kind="stable")]
            pct = np.empty(valid.size)
            pct[order] = np.arange(valid.size) / (valid.size - 1)
            tilt[valid] = 1.0 + la_w * (2.0 * pct - 1.0)
        for t in range(1, out.shape[0]):
            ok = np.isfinite(lift[t])
            out[t] = np.where(ok, lift[t] * tilt, np.nan)
            if la_min > 0.0:
                d0s = np.array([ld.get(s) for s in cols], dtype=object)
                young = np.array(
                    [d is None or (months[t] - d).days < la_min * 365.25 for d in d0s])
                out[t] = np.where(ok & ~young, out[t], np.nan)

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
