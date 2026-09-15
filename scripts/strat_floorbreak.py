"""Candidate: floor-seasoned breakout freshness (strategy_lab contract).

Fresh rank idea (imported, never copied): rank by strat_breakrec freshness
(-bars-since-trailing-high: yesterday's breakout outranks a six-month grinder)
but only among floor-seasoned names where strat_floorlift's score is finite
(full floor window + 12m positive trend + above the floor). Regime is
floorlift's index-vs-MA exposure (supports weak_exp tiers).

Rationale: strat_floorhigh showed floor-distance rank among near-high names
is the hot line; strat_breakrec tests the same intuition cut the other way
(WHEN the high printed, not HOW FAR below it). This is the clean ablation:
identical seasoning universe, freshness rank vs depth rank. If freshness
wins forward, timing dominates selection; if it loses, depth carries the
edge and the hot line stands.

PIT-safe: both legs use closes through px[m] only for holding month starting
months[m]; floor needs flb bars, high-recency needs lb bars (inherited).

SPACE = floor_lb {16,18}, lookback {15}, max_dist {0.03}, regime_ma {10},
        weak_exp {1.0} (mirrors the floorhigh hot line).
"""

from __future__ import annotations

import numpy as np

from strat_breakrec import score as _rec_score
from strat_floorlift import score as _floor_score

NEEDS_DAILY = False
SPACE = {
    "floor_lb": [16, 18],
    "lookback": [15],
    "max_dist": [0.03],
    "regime_ma": [10],
    "weak_exp": [1.0],
}


def score(panels, params):
    lift, regime = _floor_score(panels, params)
    rec, _ = _rec_score(panels, params)
    return np.where(np.isfinite(lift), rec, np.nan), regime
