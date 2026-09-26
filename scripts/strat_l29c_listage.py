"""Candidate: listing-age rank tilt on the L25 champion (Loop-29 C).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported,
verbatim; universe nse_all, invvol top 25 via policy keys). At month t, each
name with a finite champion score gets age = (months[t] - listing_date) in
years (listing dates from the universe file via strat_l17c_listage.
_listing_dates, imported, not copied). Cross-sectional percentile pct of age
among the finite-score names at t (>= 5 names; point-in-time: only names the
champion could buy at t are ranked, unlike the legacy file's static
whole-universe percentile); score multiplied by 1 + la_w*(2*pct-1).
la_w > 0 favours seasoned listings (the legacy sign), la_w < 0 favours recent
listings. Names without a listing date keep tilt 1. NaN scores stay NaN;
la_w = 0 is the exact off-switch. Exposure untouched.

Hypothesis: recent listings on the fresh-print list are the ones most likely to
be circuit-locked, thin and mean-reverting after an IPO pop; seasoned names
carry a longer price-discovery record, so under realistic fills the age tilt
should cut blocked entries and drawdown. Falsifier: neither sign beats
+30.09/-17.22 train at no deeper DD.

Novelty: strat_l17c_listage (L17, LIVE champion term on the legacy chain,
la_w 0.5: 95.85/-15.51, composed into strat_l19a_balanced) was fitted under
the legacy execution model that bought un-fillable limit-up names. No L22-L28
realistic ledger row carries la_w (l28a_ipofroth is an exposure rule on the
new-listing COUNT, not a rank tilt). Changed base: realistic execution +
liqconfirm strict regime + invvol top 25 book.
"""
from __future__ import annotations
import numpy as np
from strat_l23a_liqconfirm import score as _base
from strat_l17c_listage import _listing_dates

NEEDS_DAILY = True
SPACE = {"la_w": [-0.3, -0.15, 0.15, 0.3, 0.5]}


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("la_w", 0.0))
    if w == 0.0:
        return scores, exposure
    ld = _listing_dates()
    months, cols = panels["months"], panels["cols"]
    d0 = [ld.get(s) for s in cols]
    out = np.array(scores, dtype=float, copy=True)
    for t in range(out.shape[0]):
        mt = months[t]
        mt = mt.date() if hasattr(mt, "date") else mt
        age = np.array([np.nan if d is None else (mt - d).days / 365.25 for d in d0])
        valid = np.isfinite(out[t]) & np.isfinite(age)
        n = int(valid.sum())
        if n < 5:
            continue
        order = np.argsort(age[valid], kind="stable")
        pct = np.empty(n)
        pct[order] = np.arange(n) / (n - 1)
        tilt = np.ones(out.shape[1])
        tilt[valid] = 1.0 + w * (2.0 * pct - 1.0)
        out[t] = np.where(np.isfinite(out[t]), out[t] * tilt, np.nan)
    return out, exposure
