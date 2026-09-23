"""Candidate: TILT-ORDERING vs the regime-conditional cap on the champion book
(strategy_lab contract).

Setup in words: the current champion `strat_l19a_balanced` composes, in this
exact order, gatefail lift -> inside-day tilt -> CAP -> listing-age tilt ->
outrank tilt -> no-op cap. Because the cap BINDS below the book size in tier
months (cap_weak 11 < top 15), the two post-cap tilts only reorder an
11-name book there — every one of those 11 names is held regardless of tilt,
so the age/outrank tilts are INERT for holdings in every month where the cap
binds (raw exposure < 1.0, i.e. the tier months). They act only in
full-breadth months, where cap_full 20 > top 15 and the tilts select 15 of the
20 capped names. This file asks a structural question never screened: was the
cap-before-tilt order load-bearing, or do the two LIVE consistency tilts do
more work when they act on the FULL eligible pool and the cap then cuts the
RE-RANKED pool (making them active in every invested month)?

    champion order   : lift -> ids -> cap -> [age -> or] -> no-op
    this file (pre)  : lift -> ids -> [age -> or] -> cap -> no-op

NO new signal is introduced. The two tilts are re-expressed here with the
SAME formulas, cited from their tested sources (strat_l17c_listage: age_ref =
max(0,(months[-1]-listing_date).days)/365.25, tilt_a = 1 + la_w*(2*pct-1) over
the cross-sectional percentile among known listing dates, rows t >= 1;
strat_l16b_outrank: ret = px[t]/px[t-or_lb]-1, tilt_b = 1 + or_w*(2*pct-1)
over the cross-sectional percentile of finite rets in row t, rows t >= or_lb),
and the inside-day tilt and cap step are mirrored inline from
strat_l19a_balanced (ids via `_monthly_inside`, tilt = 1 + ids_w*(2*pct-1) on
the trailing ids_lb inside-day shares; cap = cap_full where exposure >= 1.0
else cap_weak, lower ranks NaN-ed after a stable descending sort). The only
variable is WHERE the cap sits relative to the two tilts, per tilt
independently (`pre_la`, `pre_or`).

Hypothesis: the L19 champion's train gain (+1.8pp over the L15 chain) came
mostly from the full-breadth months where the tilts actually select names.
Making the tilts select in the tier months too (top 11 of the tilted pool)
should shift those months toward old listings / panel laggards, which is the
direction each tilt was screened for (consistency and DD). If the tier-month
book composition is already decided by the lift rank and the ids tilt, moving
the two tilts pre-cap changes little and the axis closes.

Falsifier: if (pre_la, pre_or) = (1,0), (0,1), (1,1) all trail the champion on
BOTH train CAGR and Calmar with no forward/DD improvement, the ordering axis
closes at this base.

Off-switch identity: BOTH flags 0 delegates to `strat_l19a_balanced.score`
verbatim — bit-exact champion by construction. With champion keys the
identity must print train +98.682% / DD -15.506% / calmar 6.364 / H1 +95.295%
/ H2 +101.966% / fwd +53.148% / fwd DD -10.403% / full +79.237% / -20.728%.

PIT argument: unchanged from the sources. Ids tilt reads daily bars strictly
before months[t] (bucket t-1 and older). Age tilt reads only the static
`listing_date` attribute (0 nulls on the 2,559 universe symbols). Outrank
tilt at row t reads px[t] and px[t-or_lb] only. The cap reads month-t ranks
and the exposure row E[t], both computed from closes through month t. No row
> t is touched anywhere.

SPACE = champion keys pinned + pre_la {0, 1}, pre_or {0, 1} (placement bits;
0 = post-cap as in the champion, 1 = pre-cap).

NOVELTY STATEMENT: no new signal; a PLACEMENT mechanism. Closest prior art:
strat_l19a_balanced itself, whose docstring pins the order for faithfulness
to its two source files and never screens it; the cap-mechanism inventory
entry (`cap_weak`/`cap_full` sharp peaks, mechanism changes explicitly open)
is the family this touches. The one thing that changes: the cap's INPUT — the
tilted pool instead of the lift pool — which alters the held book in every
month the cap binds. No registry row has ever tested tilt-vs-cap ordering.
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside
from strat_l19a_balanced import _listing_dates
from strat_l19a_balanced import score as _l19_score

NEEDS_DAILY = True  # the ids term reads the daily panel (ids_w -0.13)

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
    "la_min": [0],
    "la_w": [0.5],
    "or_lb": [6],
    "or_w": [-0.1],
    # this file's placement bits
    "pre_la": [0, 1],
    "pre_or": [0, 1],
}


def _ids_tilt(out: np.ndarray, panels, params) -> np.ndarray:
    """Inside-day tilt, mirrored from strat_l19a_balanced.score (same formula:
    trailing ids_lb monthly inside-day shares via _monthly_inside, cross-
    sectional percentile among finite shares, tilt = 1 + ids_w*(2*pct-1))."""
    ids_w = float(params.get("ids_w", 0.0))
    if ids_w == 0.0:
        return out
    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    ilb = int(params.get("ids_lb", 3))
    IDS = _monthly_inside(daily, months, cols)
    for t in range(1, out.shape[0]):
        lo = t - ilb
        if lo < 0:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            share = np.nanmean(IDS[lo:t], axis=0)
        valid = np.isfinite(share)
        n = int(valid.sum())
        tilt = np.ones(out.shape[1])
        if n >= 5:
            sv = share[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt[valid] = 1.0 + ids_w * (2.0 * pct - 1.0)
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt, np.nan)
    return out


def _age_tilt(out: np.ndarray, panels, params) -> np.ndarray:
    """Listing-age tilt, re-expressed from strat_l17c_listage.score via
    strat_l19a_balanced (same static percentile, rows t >= 1)."""
    la_w = float(params.get("la_w", 0.0))
    la_min = float(params.get("la_min", 0.0) or 0.0)
    if la_w == 0.0 and la_min <= 0.0:
        return out
    ld = _listing_dates()
    months, cols = panels["months"], panels["cols"]
    age_ref = np.full(len(cols), np.nan)
    for j, s in enumerate(cols):
        d0 = ld.get(s)
        if d0 is not None:
            age_ref[j] = max(0, (months[-1] - d0).days) / 365.25
    tilt_a = np.ones(len(cols))
    valid = np.flatnonzero(np.isfinite(age_ref))
    if valid.size >= 5:
        order = valid[np.argsort(age_ref[valid], kind="stable")]
        pct = np.empty(valid.size)
        pct[order] = np.arange(valid.size) / (valid.size - 1)
        tilt_a[valid] = 1.0 + la_w * (2.0 * pct - 1.0)
    for t in range(1, out.shape[0]):
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt_a, np.nan)
    return out


def _or_tilt(out: np.ndarray, panels, params) -> np.ndarray:
    """Cross-sectional outrank tilt, re-expressed from strat_l16b_outrank.score
    via strat_l19a_balanced (ret over or_lb months, percentile tilt, rows
    t >= or_lb)."""
    or_w = float(params.get("or_w", 0.0))
    if or_w == 0.0:
        return out
    px = panels["px"]
    olb = int(params.get("or_lb", 6))
    for t in range(olb, out.shape[0]):
        with np.errstate(invalid="ignore"):
            ret = px[t] / px[t - olb] - 1.0
        valid = np.isfinite(ret)
        n = int(valid.sum())
        if n < 5:
            continue
        rv = ret[valid]
        order = np.argsort(rv, kind="stable")
        pct = np.empty(n)
        pct[order] = np.arange(n) / (n - 1)
        tilt_b = np.ones(out.shape[1])
        tilt_b[valid] = 1.0 + or_w * (2.0 * pct - 1.0)
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt_b, np.nan)
    return out


def _cap(scores: np.ndarray, E: np.ndarray, params) -> np.ndarray:
    """Regime-conditional cap, mirrored inline from strat_l19a_balanced.score
    (cap_full where exposure >= 1.0 else cap_weak; lower ranks NaN-ed after a
    stable descending sort)."""
    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    for t in range(scores.shape[0]):
        r = scores[t]
        fin = np.flatnonzero(np.isfinite(r))
        if fin.size == 0:
            continue
        cap = cf if E[t] >= 1.0 else cw
        if fin.size <= cap:
            continue
        order = fin[np.argsort(-r[fin], kind="stable")]
        scores[t, order[cap:]] = np.nan
    return scores


def score(panels, params):
    pre_la = int(params.get("pre_la", 0) or 0)
    pre_or = int(params.get("pre_or", 0) or 0)
    if pre_la == 0 and pre_or == 0:
        # bit-exact champion by delegation (off-switch identity)
        return _l19_score(panels, params)

    p = dict(params)
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, exposure = _gf_score(panels, p)
    out = np.array(lift, dtype=float, copy=True)
    E = np.asarray(exposure, dtype=float)

    out = _ids_tilt(out, panels, params)
    if pre_la:
        out = _age_tilt(out, panels, params)
    if pre_or:
        out = _or_tilt(out, panels, params)
    out = _cap(out, E, params)
    if not pre_la:
        out = _age_tilt(out, panels, params)
    if not pre_or:
        out = _or_tilt(out, panels, params)
    return _cap(out, E, params), E
