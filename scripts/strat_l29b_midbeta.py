"""Candidate (L29 designer B): Nifty 500 fresh-print book with LOW-BETA
selection only in partial-exposure (middle breadth tier) months (strategy_lab contract).

Setup in words: rank and breadth-tier exposure are strat_floorhighfresh's,
imported unchanged (universe nifty500, top 25). In months whose exposure is a
PARTIAL tier (0 < E < 1: breadth between b_lo and b_hi, i.e. the market is
neither clearly risk-on nor off), eligible names whose trailing beta to the
panel's equal-weight index sits above the `bt_q` quantile of that month's
eligible names are DEMOTED below every other eligible name (score - 1e6):
they stay eligible (so the harness minimum-count rule and book size are
untouched) but are bought only if the low-beta side cannot fill the book.
Full-risk (E == 1) and cash months are untouched.

Beta: OLS slope of a name's monthly returns on the EW index's monthly
returns over the last `bt_lb` completed months (returns px[t-1]->px[t] for
t <= m; closes through px[m] only), requiring >= bt_lb // 2 paired months;
names without a beta are left as-is.

Novelty: betacap (L28, DEAD) capped high-beta counts in EVERY month on the
full-board champion; ddquality/invvol tilts were unconditional. This is the
first tier-CONDITIONAL rank rule (defensive only in the middle tier) and runs
on a changed base (Nifty 500 L25 cell). Disclosure: the target (Nifty 500
book DD) was MOTIVATED by the revealed L25 forward DD -25.65; bt_q/bt_lb are
chosen on train only.

Off-switch: bt_q >= 1.0 returns the base scores exactly.
SPACE = base params + bt_lb {12, 24}, bt_q {0.3, 0.5, 0.7, 1.0}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _fresh_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65], "b_mid": [0.58], "b_lo": [0.45], "floor_lb": [24],
    "lookback": [16], "max_dist": [0.055], "regime_ma": [24],
    "bt_lb": [12, 24], "bt_q": [0.3, 0.5, 0.7, 1.0],
}


def trailing_beta(px, m, lb):
    """Per-name beta over monthly returns ending at px[m] (no later close)."""
    lo = max(m - lb, 0)
    w = px[lo:m + 1]
    with np.errstate(invalid="ignore", divide="ignore"):
        r = w[1:] / w[:-1] - 1.0
    idx = np.nanmean(r, axis=1)
    ok = np.isfinite(r) & np.isfinite(idx)[:, None]
    n = ok.sum(axis=0)
    x = np.where(ok, idx[:, None], 0.0)
    y = np.where(ok, r, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mx = x.sum(0) / n
        my = y.sum(0) / n
        cov = (np.where(ok, (x - mx) * (y - my), 0.0)).sum(0)
        var = (np.where(ok, (x - mx) ** 2, 0.0)).sum(0)
        beta = cov / var
    beta[(n < max(lb // 2, 3)) | ~np.isfinite(beta)] = np.nan
    return beta


def score(panels, params):
    scores, exposure = _fresh_score(panels, params)
    q = float(params.get("bt_q", 1.0))
    if q >= 1.0:
        return scores, exposure
    lb = int(params.get("bt_lb", 24))
    px = panels["px"]
    out = np.array(scores, dtype=float, copy=True)
    e = np.asarray(exposure, dtype=float)
    for m in range(len(e)):
        if not (0.0 < e[m] < 1.0):
            continue
        elig = np.isfinite(out[m])
        if elig.sum() == 0:
            continue
        b = trailing_beta(px, m, lb)
        bb = b[elig & np.isfinite(b)]
        if bb.size == 0:
            continue
        cut = np.quantile(bb, q)
        hi = elig & np.isfinite(b) & (b > cut)
        out[m, hi] = out[m, hi] - 1e6
    return out, exposure
