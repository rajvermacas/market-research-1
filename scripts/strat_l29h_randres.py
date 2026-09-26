"""Candidate: random-reserved-set NULL CONTROL for strat_l29e_coresat (Loop-29 H).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported).
Then, on each decision row t, the rr_k highest-scoring ELIGIBLE (finite-score)
names inside a FIXED RANDOM subset of the universe's columns receive a +1e6
bonus, so they occupy rr_k of the top-N slots; the rest fill by the champion
score. Identical mechanism to coresat, but the reserved set is drawn with
numpy default_rng(rr_seed) from panels["cols"], of size rr_size (default: the
number of in_nifty500 names present in cols, i.e. the same size as coresat's set).

Question: is coresat's gain from the index flag or from reserving slots for any
fixed subset of that size? The distribution over seeds is the null.

Off-switch: rr_k = 0 (default) returns the imported scores untouched -> champion.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _base
from strat_l29e_coresat import _members

NEEDS_DAILY = True
SPACE = {"rr_k": [0, 17], "rr_seed": list(range(1, 11))}
BONUS = 1e6


def score(panels, params):
    scores, exposure = _base(panels, params)
    k = int(params.get("rr_k", 0) or 0)
    if k <= 0:
        return scores, exposure
    cols = list(panels["cols"])
    mem = _members()
    size = params.get("rr_size")
    size = int(size) if size else int(sum(c in mem for c in cols))
    rng = np.random.default_rng(int(params.get("rr_seed", 1)))
    pick = rng.choice(len(cols), size=min(size, len(cols)), replace=False)
    is_r = np.zeros(len(cols), dtype=bool)
    is_r[pick] = True
    print(f"[l29h] reserved set size={int(is_r.sum())} of {len(cols)} cols, seed={params.get('rr_seed', 1)}")
    out = np.array(scores, dtype=float, copy=True)
    for t in range(out.shape[0]):
        r = out[t]
        idx = np.flatnonzero(np.isfinite(r) & is_r)
        if idx.size == 0:
            continue
        core = idx[np.argsort(-r[idx], kind="stable")[:k]]
        out[t, core] = r[core] + BONUS
    return out, exposure
