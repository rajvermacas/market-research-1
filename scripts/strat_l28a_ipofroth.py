"""Candidate: new-listing (IPO) wave FROTH exposure cut (Loop-28 A).

Setup in words: rank, eligibility, breadth-tier exposure and book are exactly
strat_l23a_liqconfirm (imported, never copied; weighting/top are harness
policy keys). A market-level froth gauge is added: n_t = number of universe
symbols whose listing_date falls in the ip_k months before months[t]
(listing_date < months[t], so it is known at decision time). The gauge is
ratio_t = n_t / mean(n over the ip_base trailing monthly windows before that),
i.e. the IPO pace relative to its own recent history. If ratio_t > ip_thr
exposure *= (1 - ip_cut) for that month.

Hypothesis (theory, chosen before any look at data): primary-issuance waves
cluster at speculative peaks (India: 2007-Jan-2008, 2017-early-2018,
2021) because promoters sell when valuations are rich; a surge in issuance
pace is a supply-side froth signal independent of price breadth.
Falsifier: no cell improves train DD without costing CAGR, or only one
knife-edge cell does.

Caveat: the universe is today's listing, so IPOs that later delisted are
missing; the own-history normalisation limits (does not cure) that bias.
listing_date null_count = 0 (checked).

Novelty: l27a_froth / l27o_frothami (illiquid-minus-liquid RETURN spread),
l27a_sizeflight, l17c_listage (per-stock listing-age TILT, a rank term) --
none uses the market-level COUNT of new listings as an exposure signal.

Off-switch: ip_cut = 0 -> champion exactly.
SPACE: ip_k {3,6}, ip_base {24,36}, ip_thr {1.5,2.0,2.5}, ip_cut {0,0.5,1.0}.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"ip_k": [3, 6], "ip_base": [24, 36], "ip_thr": [1.5, 2.0, 2.5],
         "ip_cut": [0.0, 0.5, 1.0]}
_UNI = Path(__file__).resolve().parents[1] / "data" / "universe" / "nse_universe.parquet"


def ipo_ratio(months, k: int, base: int) -> np.ndarray:
    ld = pl.read_parquet(_UNI)["listing_date"].cast(pl.Date).drop_nulls().to_list()
    ld = np.array(sorted(d.toordinal() for d in ld))
    mo = np.array([date(m.year, m.month, m.day).toordinal() for m in months])

    def cnt(end_ord, nmon):
        lo = end_ord - int(round(nmon * 30.44))
        return np.searchsorted(ld, end_ord, "left") - np.searchsorted(ld, lo, "left")

    out = np.full(len(months), np.nan)
    for t in range(len(months)):
        n = cnt(mo[t], k)
        hist = [cnt(mo[t] - int(round(j * k * 30.44)), k) for j in range(1, max(1, base // k) + 1)]
        mu = float(np.mean(hist))
        if mu > 0:
            out[t] = n / mu
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    cut = float(params.get("ip_cut", 0.0))
    if cut <= 0:
        return scores, exposure
    r = ipo_ratio(panels["months"], int(params.get("ip_k", 3)), int(params.get("ip_base", 36)))
    thr = float(params.get("ip_thr", 2.0))
    out = np.asarray(exposure, dtype=float).copy()
    for t in range(len(out)):
        if np.isfinite(r[t]) and r[t] > thr:
            out[t] = out[t] * (1.0 - cut)
    return scores, out
