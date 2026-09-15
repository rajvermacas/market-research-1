"""Candidate: floor-high rank with last-month reversal skip (strategy_lab contract).

Fresh gate on the hot line (imported, never copied): rank by
strat_floorhigh (floor-lift distance among names within max_dist of their
trailing high) but exclude names whose last-1m return sits above the
cross-sectional quantile `skip_q` (default 0.9). Thesis: the floorhigh
book's DD comes from buying vertical blowoff tops that then mean-revert
within weeks; momentum literature skips the most recent month for exactly
this reason, but no floorhigh trial applies a skip. Unlike the accel gate
(steepening over 3m vs 12m, tested negative), this is a pure exclusion of
the extreme right tail of the 1m return distribution — rank order among
the rest is untouched.

PIT-safe: 1m return uses closes px[m-1..m] only for holding month starting
months[m]; quantile computed cross-sectionally at t (no future).

SPACE = union of strat_floorhigh params + skip_q {0.85, 0.9, 0.95}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_floorhigh.SPACE + skip_q {0.85,0.9,0.95}"}


def score(panels, params):
    px = panels["px"]
    rank, regime = _fh_score(panels, params)
    q = float(params.get("skip_q", 0.9))
    out = rank.copy()
    r1 = np.full_like(px, np.nan)
    r1[1:] = px[1:] / px[:-1] - 1
    for t in range(len(panels["months"])):
        row = r1[t]
        ok = np.isfinite(row) & np.isfinite(out[t])
        if ok.sum() < 5:
            continue
        cut = np.quantile(row[ok], q)
        out[t][ok & (row > cut)] = np.nan
    return out, regime
