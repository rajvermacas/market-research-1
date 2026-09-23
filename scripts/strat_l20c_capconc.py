"""Candidate: SIGNAL-CONCENTRATION-driven book cap on the CURRENT champion
chain (strategy_lab contract, Loop-20 designer C).

Setup in words: this file re-implements the strat_l19a_balanced champion
chain faithfully — gatefail delegate with neutralised defaults, inside-day
(ids) tilt on the returned lift, the regime-conditional book cap, the
listing-age tilt, the cross-sectional outrank tilt, final no-op cap pass —
and replaces the ONE thing under test: the cap's binary regime switch

    cap_t = cap_full if E[t] >= 1.0 else cap_weak          # champion (LIVE)

with a cap driven by SIGNAL CONCENTRATION at the decision month: when the
eligible top ranks are BUNCHED (the floor-lift signal barely discriminates
them), hold FEWER names; when the rank spread is wide, hold more (the sign
is itself tested — the reverse arm is in the SPACE). Concentration is read
only from the structure of the champion's OWN eligible lift at row t — never
from the held book's returns — so it is PIT by construction and is NOT a
re-shape of book-health (which conditioned exposure on held-book gate
attrition via a causal replay, strat_l12a_bookhealth, DEAD).

Formula (all steps new; the cap's position and sort are mirrored exactly
from strat_l19a_balanced.score, whose own citations are
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score):

    1. take `out` = ids-tilted gatefail lift at row t, PRE-cap (the
       "eligible champion lift"; finite entries are the gate-passing
       candidates);
    2. keep the top K = cc_k finite values rv (or all, if fewer);
    3. dispersion  d_t = p90(rv) - p50(rv)          if cc_meas == "p90"
                   d_t = std(rv)                    if cc_meas == "std"
    4. adaptive level: q_t = midrank percentile of d_t among the finite
       d's of rows [t - cc_lb + 1 .. t]  (trailing cc_lb rows INCLUDING t;
       requires >= 5 finite in-window, else q_t undefined);
    5. cap_t = clip( round( base_t + cc_w * (cap_full - cap_weak)
                                   * (2 * q_t - 1) ), 2, 40 )
       where base_t = cap_full if E[t] >= 1.0 else cap_weak (the champion's
       binary switch, preserved as the anchor) and rows with undefined q_t
       keep base_t exactly.

So cc_w > 0 implements the hypothesis (bunched -> FEWER names: low q pulls
cap below the band anchor; wide spread -> more names: high q pushes it
above, up to cap_full + (cap_full - cap_weak) at full weight), cc_w < 0
tests the reverse sign, and cc_w = 0 is the off-switch (step 5 degenerates
to the binary switch, step 4 never runs). The trailing-percentile mapping
in step 4 keeps the cap LEVEL adaptive — an absolute dispersion threshold
would silently trend with the lift's scale across eras.

Hypothesis: cap_weak/cap_full is a sharp peak (skill inventory: PARTIAL —
"their local neighbourhood is closed to tuning, but changing their
MECHANISM is not") whose current mechanism only knows the MARKET regime
(breadth band). The information the cap really needs at month t is how
discriminating the signal itself is: a bunched top-of-book means the
11th-ranked name is nearly indistinguishable from the 1st — marginal names
are noise in that month and the book should thin out; a wide spread means
the ranked tail carries real structure and more names are worth holding.
Concentration is a property of the score cross-section, not of the market's
trend breadth and not of the held book.

Falsifier: if every tested (cc_w, cc_meas) variant in the SPACE below
trails the flat base — train +98.682% / DD -15.506% / calmar 6.364 /
H1 +95.295% / H2 +101.966% / fwd +53.148% / fwd DD -10.403% — on BOTH
train CAGR and forward risk-adjusted numbers, then the score-distribution
concentration of the eligible lift carries no book-size information beyond
the regime binary, and the concentration-cap axis closes at this base
(no keep can ratchet: needs train > 98.682+0.05 with DD >= -17.506 and
both halves > 0).

Import chain: strat_l20c_capconc -> strat_l12b_gatefail.score (imports
strat_floorhighfastgate + strat_floorhighsustaincond + strat_floorhightiershape
for the gate layers and rank/exposure, applies the wobble tilt; its gf_w
0.05 default is neutralised by setdefault BEFORE delegating — Loop-14
lesson) -> ids tilt re-expressed from strat_l15b_insideday.score via
_monthly_inside (same percentile math) -> CONCENTRATION CAP (this file,
in the exact position of the champion's mirrored cap) -> listing-age tilt
re-expressed from strat_l17c_listage.score -> outrank tilt re-expressed
from strat_l16b_outrank.score -> final no-op cap pass (a no-op because the
first pass leaves fin.size <= cap_t on every row).

PIT argument: the dispersion at row t reads only the lift cross-section of
row t, which the chain computes from closes through px[t] and daily bars
strictly before months[t] (ids term). The trailing window in step 4 reads
rows <= t only. No row > t, no held-book state, no replay, no forward
data. NEEDS_DAILY = True because the champion's ids term needs the daily
panel.

Off-switch identity: cc_w = 0.0 (neutral default set via setdefault BEFORE
delegating) skips steps 2-4 entirely and the cap loop is the champion's
binary switch verbatim, so `out` is bitwise the champion's scores at the
same params; champion keys are PASSED by the caller, never defaulted here
(gf_lb 12 / gf_w 0.0 neutralised, gw_w 0.15 / ids_lb 3 / ids_w -0.13 /
la_w 0.5 / or_w -0.1 passed).

Flat-base metric (off-switch must reproduce exactly): train +98.682% /
DD -15.506% / calmar 6.364 / H1 +95.295% / H2 +101.966% /
fwd +53.148% / fwd DD -10.403% / full +79.237% / full DD -20.728%.

NOVELTY STATEMENT (exact registry rows, research/tested_mechanisms.tsv):
closest prior art is
  (a) `strat_l12b2_symcap.py  l12  symmetric count caps  DEAD  -  cap_full
       inert for values >= top` — constants moved on BOTH bands, over the
       old rankpersist base (lookback 10, tier 0.999, no ids/age/outrank);
  (b) `strat_l15a_capgrand.py  l15  weak-month cap grandfather
       KEEP-not-promoted  train 85.5-86.1 / DD -16.05` — cap exceptions
       conditioned on HELD-BOOK incumbency (needs a causal replay);
  (c) `strat_l12a_bookhealth.py  l12  book-health floors  DEAD  - exposure
       conditioned on book health` — held-book gate attrition;
  (d) the LIVE cap itself (skill inventory: "regime-conditional weak-month
       cap cap_weak/cap_full") whose LOCAL NEIGHBOURHOOD is closed but
       whose mechanism change is explicitly open;
  (e) `strat_l19a_balanced.py  l19  PROMOTED (CHAMPION)` — the base.
THE ONE THING THAT CHANGED: the cap level is now a function of the score
cross-section's own dispersion at the decision month (percentile-adaptive
over trailing months) — a signal-structure read at the moment of choice.
Every prior cap row keyed on a market REGIME band (a), held-book history
(b, c), or constants (a); none read how bunching/discrimination of the
eligible lift. Not book-health: no held-book quantity is used; not a
re-shape of a DEAD row: the signal class (score-distribution dispersion)
is new AND the base changed (symcap's falsification was on rankpersist).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1; max_hold 3 is a HARNESS key
        passed via params-json, not consumed here)
        + cc_w {0.0 (off-switch), 0.25, 0.5, 1.0, -0.5} (concentration
          weight; positive = bunched top -> FEWER names, negative = reverse
          sign)
        + cc_meas {"p90" (p90-p50 of top-K), "std"} (dispersion measure)
        + cc_lb [12] (trailing rows for the adaptive percentile)
        + cc_k [30] (top-K candidates entering the dispersion)
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside

NEEDS_DAILY = True  # the delegate's ids term reads the daily panel (ids_w -0.13)

_UNI_CACHE: dict = {}


def _listing_dates() -> dict:
    """symbol -> listing_date from the universe snapshot (static ex-ante
    attribute; copied from strat_l19a_balanced._listing_dates)."""
    if "ld" not in _UNI_CACHE:
        root = Path(__file__).resolve().parents[1]
        u = pl.read_parquet(root / "data" / "universe" / "nse_universe.parquet")
        _UNI_CACHE["ld"] = dict(zip(u["symbol"].to_list(), u["listing_date"].to_list()))
    return _UNI_CACHE["ld"]

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
    # this file's keys
    "cc_w": [0.0, 0.25, 0.5, 1.0, -0.5],
    "cc_meas": ["p90", "std"],
    "cc_lb": [12],
    "cc_k": [30],
}


def _dispersion(L: np.ndarray, k: int, meas: str) -> np.ndarray:
    """Row t: dispersion of the top-k finite pre-cap lift values. NaN where
    fewer than 5 finite candidates exist."""
    out = np.full(L.shape[0], np.nan)
    for t in range(L.shape[0]):
        fin = np.flatnonzero(np.isfinite(L[t]))
        if fin.size < 5:
            continue
        rv = L[t, fin]
        if fin.size > k:
            rv = rv[np.argsort(-rv, kind="stable")[:k]]
        out[t] = (float(np.std(rv)) if meas == "std"
                  else float(np.percentile(rv, 90) - np.percentile(rv, 50)))
    return out


def _trail_pct(d: np.ndarray, lb: int) -> np.ndarray:
    """Row t: midrank percentile of d[t] among the finite d's of rows
    [t-lb+1 .. t]; NaN where d[t] is NaN or the window has < 5 finite."""
    q = np.full(d.shape[0], np.nan)
    for t in range(d.shape[0]):
        if not np.isfinite(d[t]):
            continue
        lo = max(0, t - lb + 1)
        w = d[lo:t + 1]
        w = w[np.isfinite(w)]
        if w.size < 5:
            continue
        q[t] = ((w < d[t]).sum() + 0.5 * (w == d[t]).sum()) / w.size
    return q


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (gatefail's own gf_w 0.05 default
    # would leak — Loop-14 lesson); this file's own keys neutralised the
    # same way. Champion keys gw_w 0.15 / ids_w -0.13 / ids_lb 3 / la_w 0.5
    # / or_w -0.1 must be PASSED by the caller.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    p.setdefault("cc_w", 0.0)
    p.setdefault("cc_lb", 12)
    p.setdefault("cc_k", 30)
    p.setdefault("cc_meas", "p90")
    lift, exposure = _gf_score(panels, p)  # champion lift (wobble tilt inside)
    out = np.array(lift, dtype=float, copy=True)

    # ---- ids tilt, re-expressed from strat_l15b_insideday.score (its inline
    # loop: tilt = 1 + ids_w * (2 * pct - 1) on the trailing ids_lb monthly
    # inside-day shares, percentile-ranked among finite shares) ----
    ids_w = float(params.get("ids_w", 0.0))
    if ids_w != 0.0:
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

    # ---- cap step, mirrored inline from strat_l19a_balanced.score (same
    # position: between the ids tilt and the age/outrank tilts; same stable
    # descending sort) with the MECHANISM under test: the binary regime
    # switch (cap = cap_full if E >= 1.0 else cap_weak) becomes the anchor
    # of a concentration-driven level (see docstring steps 1-5). ----
    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    E = np.asarray(exposure, dtype=float)
    caps = np.where(E >= 1.0, cf, cw)  # champion binary switch (the anchor)

    cc_w = float(p.get("cc_w", 0.0))
    if cc_w != 0.0:
        cc_lb = int(p.get("cc_lb", 12))
        cc_k = int(p.get("cc_k", 30))
        meas = str(p.get("cc_meas", "p90"))
        d = _dispersion(out, cc_k, meas)          # step 2-3, PRE-cap lift
        q = _trail_pct(d, cc_lb)                  # step 4, rows <= t only
        adj = cc_w * float(cf - cw) * (2.0 * np.nan_to_num(q, nan=0.5) - 1.0)
        adj = np.where(np.isfinite(np.nan_to_num(q, nan=np.nan)), adj, 0.0)
        caps = np.clip(np.round(caps + adj), 2, 40).astype(int)

    def _cap(scores: np.ndarray) -> np.ndarray:
        for t in range(scores.shape[0]):
            r = scores[t]
            fin = np.flatnonzero(np.isfinite(r))
            if fin.size == 0:
                continue
            cap = int(caps[t])
            if fin.size <= cap:
                continue
            order = fin[np.argsort(-r[fin], kind="stable")]
            scores[t, order[cap:]] = np.nan
        return scores

    out = _cap(out)

    # ---- (a) listing-age tilt, re-expressed from strat_l17c_listage.score
    # (source formula, cited in strat_l19a_balanced's docstring:
    #   age_ref = max(0, (months[-1] - listing_date).days) / 365.25;
    #   tilt_a = 1 + la_w * (2 * pct - 1); rows t >= 1) ----
    la_w = float(params.get("la_w", 0.0))
    la_min = float(params.get("la_min", 0.0) or 0.0)  # retained, PINNED 0
    if la_w != 0.0 or la_min > 0.0:
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
            if la_min > 0.0:
                d0s = np.array([ld.get(s) for s in cols], dtype=object)
                young = np.array(
                    [d is None or (months[t] - d).days < la_min * 365.25 for d in d0s])
                out[t] = np.where(ok & ~young, out[t], np.nan)

    # final no-op cap pass (strat_l17c_listage re-runs the mirrored cap
    # after its tilt; fin.size <= cap_t on every row, so it removes nothing —
    # structure kept so the chain matches strat_l19a_balanced end-to-end)

    # ---- (b) cross-sectional outrank tilt, re-expressed from
    # strat_l16b_outrank.score (source formula, cited in strat_l19a's
    # docstring: ret = px[t]/px[t-or_lb] - 1; tilt_b = 1 + or_w*(2pct-1)) ----
    or_w = float(params.get("or_w", 0.0))
    if or_w != 0.0:
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

    return _cap(out), E
