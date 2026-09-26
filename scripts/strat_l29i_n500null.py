"""Null controls on the Nifty 500 floorhighfresh book (Loop-29 I).

Setup in words: scores and exposure exactly as strat_floorhighfresh (imported,
run with --universe nifty500 --top 25). Two no-information perturbations,
chosen by ni_mode:

- "tilt": each month every finite-score name gets an i.i.d. uniform draw
  (numpy default_rng(ni_seed), drawn for the whole months x names matrix, so
  independent of the score); its percentile pct among finite-score names tilts
  the score by score * (1 + ni_w*(2*pct-1)). Same construction as
  strat_l29c_randtilt (which has no importable helper - its loop is inline).
- "cut": among TRAIN months only (2015-01 <= month < 2022-01) whose exposure is
  a partial tier (0 < regime < 1), pick ni_n distinct months uniformly with
  default_rng(ni_seed) and multiply exposure there by ni_cut. Forward months
  are never touched.

Purpose: noise bands for Nifty 500 screens (e.g. strat_l29b_*). A real signal
must beat the spread of these, not just the base. Not a strategy candidate.

Off-switch: ni_w = 0 (tilt) / ni_n = 0 (cut) -> base exactly.
"""

from __future__ import annotations

import sys

import numpy as np

from strat_floorhighfresh import score as _base
from strat_l29a_breadthspread import report_firings

NEEDS_DAILY = False
SPACE = {"ni_mode": ["tilt", "cut"], "ni_w": [0.0, 0.15], "ni_n": [0, 5],
         "ni_cut": [0.5], "ni_seed": list(range(1, 9))}


def _tilt(scores, w, seed):
    rng = np.random.default_rng(seed)
    u = rng.random(np.shape(scores))
    out = np.array(scores, dtype=float, copy=True)
    for t in range(out.shape[0]):
        valid = np.isfinite(out[t])
        n = int(valid.sum())
        if n < 5:
            continue
        order = np.argsort(u[t, valid], kind="stable")
        pct = np.empty(n)
        pct[order] = np.arange(n) / (n - 1)
        out[t, valid] = out[t, valid] * (1.0 + w * (2.0 * pct - 1.0))
    return out


def score(panels, params):
    res = _base(panels, params)
    scores, exposure = res[0], res[1]
    mode = str(params.get("ni_mode", "tilt"))
    seed = int(params.get("ni_seed", 1))
    if mode == "tilt":
        w = float(params.get("ni_w", 0.0))
        if w == 0.0:
            return res
        return (_tilt(scores, w, seed), exposure) + tuple(res[2:])
    n = int(params.get("ni_n", 0))
    months = panels["months"]
    base = np.asarray(exposure, dtype=float)
    ym = [str(m)[:7] for m in months]
    part = [t for t in range(len(base))
            if "2015-01" <= ym[t] < "2022-01" and 0.0 < base[t] < 1.0]
    print(f"L29I partial-tier train months: {len(part)}", file=sys.stderr)
    if n <= 0:
        return res
    cut = float(params.get("ni_cut", 0.5))
    rng = np.random.default_rng(seed)
    out = base.copy()
    pick = rng.choice(len(part), size=min(n, len(part)), replace=False)
    for i in sorted(pick):
        out[part[i]] = base[part[i]] * cut
    report_firings(months, base, out, f"L29I-cut-s{seed}")
    return (scores, out) + tuple(res[2:])
