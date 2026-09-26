"""Control: random rank tilt of the same size on the L25 champion (Loop-29 C).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported,
verbatim). At each month t every name with a finite score gets an i.i.d.
uniform draw u (numpy default_rng(rt_seed), one draw per month x name, drawn
for the whole matrix so it is independent of the score); the percentile pct of
u among finite-score names is applied exactly like the rank tilts of this loop:
score * (1 + rt_w*(2*pct-1)). rt_w = 0 is the exact off-switch.

Purpose: a NULL for the changed-base retests (strat_l29c_insideday / listage /
actionclass). Every tilt direction tried there gained 1-3pp train CAGR, which
is what a pure re-shuffle of the marginal names might also do. A tilt of the
same size with no information measures that re-shuffle effect; a real signal
must beat the spread of this control, not just the champion. Not a strategy
candidate - never gate it.

Novelty: first random-tilt null in the registry (no row carries rt_*). Base:
realistic execution + liqconfirm strict regime + invvol top 25.
"""
from __future__ import annotations
import numpy as np
from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"rt_w": [0.07, 0.15], "rt_seed": [1, 2, 3]}


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("rt_w", 0.0))
    if w == 0.0:
        return scores, exposure
    rng = np.random.default_rng(int(params.get("rt_seed", 1)))
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
    return out, exposure
