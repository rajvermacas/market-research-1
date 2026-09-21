"""Candidate: absolute price-level tilt on the champion book (strategy_lab
contract).

Setup in words: the CURRENT champion chain — strat_l15b_insideday (floor-lift
fresh-print rank among short-trend-passing, print-continuity-passing names,
breadth-tier exposure with tier 0.9999, regime-conditional cap cap_weak/
cap_full, eligibility-wobble gw_w 0.15, inside-day tilt ids_w -0.13 / lb 3) —
is imported wholesale via strat_l15b_insideday.score. Before the
regime-conditional cap step (mirrored inline, exactly as strat_l13a_concwobble
mirrors it), the imported lift is re-weighted by a NEW signal from the
non-price-attribute channel: the name's ABSOLUTE SHARE PRICE LEVEL at the
decision month.

    lvl[t, j] = mean of px over the last pl_lb month-end rows ending t
                (pl_src "px"), or px / face_value (pl_src "pxfv" — price per
                unit of face value, a snapshot-FV normalization)
    pct[t, j] = cross-sectional percentile of lvl among columns with a finite
                level in row t
    tilt[t,j] = 1 + pl_w * (2 * pct[t,j] - 1)   # pl_w > 0 favours HIGH-priced
    out[t]    = ids-tilted lift[t] * tilt       # NaN level keeps tilt 1.0

Hypothesis: the champion buys fresh 12-month-high printers; nothing in its
chain looks at what a share COSTS. Absolute price level is a per-share
attribute with real microstructure content: NSE's ₹0.05 tick is 1% of a ₹5
share and 0.001% of a ₹5,000 share, so low-priced names trade on a coarse
price grid; lot affordability concentrates retail flow in low-priced names;
and split/adjustment history has already normalised the panel so the level
is comparable across names. Two hypotheses, opposite signs: (a) the
fresh-high book is dominated by cheap small caps and the low-priced tail is
where momentum decays fastest (lot churn, no institutional sponsorship,
coarse ticks) — a HIGH-price tilt (pl_w > 0) would lift the cut's quality;
(b) low-priced names carry the attention/affordability flows that make
fresh highs continue — a LOW-price tilt (pl_w < 0) would. The screen
answers which — or neither.

NOVELTY STATEMENT: the mechanism inventory has NO price-level entry. Closest
prior art: (i) the vol-rank tilt (DEAD — dispersion of the name's own
RETURNS; this file consumes the LEVEL of the price, not its variability);
(ii) volume gates / volume participation (DEAD — SHARES TRADED, a flow; the
price level is a static-ish per-share attribute orthogonal to turnover: a
₹30 stock can carry 10 crore shares of volume and a ₹3,000 stock 2 lakh);
(iii) range compression / inside-day (tape geometry — intra-bar high-low
SHAPE, not the level). The one thing changed: the input is the absolute
price level — a level, not a flow, not a shape, not a dispersion — and no
term in the chain consumes it. (Not 52w-high proximity either: that is a
relation of the close to its own trailing high; here it is the price
itself, cross-sectionally ranked.)

Snapshot caveat: the daily closes are corporate-action adjusted, so the
level is the ADJUSTED price (a name that split 1:10 shows a tenth of its
historical price). The `pxfv` variant normalises by today's snapshot face
value — face values also change with splits, so that variant inherits the
same snapshot caveat as the index flags; the default `px` source does not
touch the universe file at all.

Import chain: strat_l17c_pxlevel -> strat_l15b_insideday.score -> cap step
mirrored inline from strat_floorhightiershapeconc.score /
strat_l13a_concwobble.score.

PIT argument: lvl reads only px rows up to and including the decision row t
(the decision-point closes — available at decision time) and the optional
static face_value. No future row. The percentile at row t uses only that
row's own levels. Rows t < 1 and names with no finite level keep tilt 1.0 —
eligibility and rank unmodified on missing data.

Off-switch identity: pl_w = 0.0 (default) leaves the tilt block skipped, so
`out` is bitwise the ids lift and the mirrored cap yields bitwise the
champion's scores at the same params. Champion keys are PASSED by the
caller, not defaulted here.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

PROMOTION PRECONDITION (Loop-16 lesson): the tilt re-orders the top-15 cut
(a book-composition mechanism) — diff the candidate's picks against the
champion's month by month and count differing decision months before
believing any gain.

Falsifier: if every tested (pl_w, pl_lb, pl_src) combination trails the flat
base — train +96.882% / DD -17.032% / calmar 5.688 — the absolute price
level carries no selection information beyond the champion chain, and the
price-level axis closes at this base. A train gain that coincides with
forward/DD deterioration keeps the family's known failure shape (the ids
term already saturates re-ranking); record it, never promote it.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key passed via params-json, not consumed
        here)
        + pl_w {+0.3, +0.15, -0.15, -0.3} (percentile tilt; 0.0 = off-switch;
          positive favours HIGH-priced names)
        + pl_lb {1, 3, 6} (month-end rows averaged into the level measure)
        + pl_src {"px", "pxfv"} (level source; "pxfv" = px / face_value).
"""

from __future__ import annotations

import warnings
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
    "pl_w": [0.3, 0.15, -0.15, -0.3],
    "pl_lb": [1, 3, 6],
    "pl_src": ["px", "pxfv"],
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

    pl_w = float(params.get("pl_w", 0.0))
    if pl_w != 0.0:
        px, cols = panels["px"], panels["cols"]
        plb = max(1, int(params.get("pl_lb", 3) or 1))
        src = str(params.get("pl_src", "px") or "px")
        A = np.asarray(px, dtype=float)
        if src == "pxfv":
            fv = _face_values()
            fv_row = np.array([fv.get(s, np.nan) for s in cols], dtype=float)
            with np.errstate(divide="ignore", invalid="ignore"):
                A = A / fv_row[None, :]
        for t in range(1, out.shape[0]):
            lo = max(0, t - plb + 1)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                lvl = np.nanmean(A[lo:t + 1], axis=0)
            valid = np.isfinite(lvl)
            n = int(valid.sum())
            tilt = np.ones(A.shape[1])
            if n >= 5:
                order = np.argsort(lvl[valid], kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + pl_w * (2.0 * pct - 1.0)
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
