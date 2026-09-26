"""Candidate: cross-universe confirmation — full-board breadth gates the Nifty 500 book.

Setup in words: the book is strat_floorhighfresh unchanged (imported). A second
regime reading is taken from the FULL NSE board (cached nse_all monthly panel,
same month grid): full-board breadth b_t = fraction of names with >= x_ma
months of history whose close px[t] is above their x_ma-month mean. When
b_t < x_thr, exposure is multiplied by (1 - x_cut).

Hypothesis: Nifty 500 breadth can stay healthy while the broad board (small
and micro caps) is already rolling over; the broad board leads. Requiring the
wider market to confirm should cut exposure ahead of Nifty 500 drawdowns.

Falsifier: no train DD improvement >= 1pp on a plateau of x_thr/x_ma
neighbours, or CAGR loss larger than the DD saved.

Off-switch: x_cut = 0 reproduces strat_floorhighfresh exactly.

Novelty: every breadth row in the registry (strat_floorhightier* / breadthlin /
hyst, strat_l14a_breadthdelta) reads breadth of the traded universe itself on
the legacy full-board harness; none gates one universe's book on ANOTHER
universe's breadth. Base also changed (Nifty 500, realistic harness).

PIT: b_t uses nse_all closes through px[t] only (month-end t, the same
information the base regime reads).
"""

from __future__ import annotations

import glob

import numpy as np

from strat_floorhighfresh import score as _base_score

NEEDS_DAILY = False
SPACE = {"x_ma": [10], "x_thr": [0.5], "x_cut": [0.0]}


def _full_board_px(months):
    for f in sorted(glob.glob(".cache/strategy_lab/panels/monthly_nse_all_*.npz")):
        d = np.load(f, allow_pickle=True)
        if len(d["months"]) == len(months) and np.array_equal(d["months"], months):
            return np.asarray(d["px"], dtype=float)
    raise RuntimeError("no nse_all monthly panel on the same month grid; run strategy_lab --universe nse_all once")


def full_breadth(px, ma):
    out = np.full(px.shape[0], np.nan)
    for t in range(ma - 1, px.shape[0]):
        w = px[t - ma + 1 : t + 1]
        ok = np.isfinite(w).all(axis=0)
        if ok.sum() < 50:
            continue
        out[t] = float((px[t, ok] > w[:, ok].mean(axis=0)).mean())
    return out


def score(panels, params):
    rank, exposure = _base_score(panels, params)
    cut = float(params.get("x_cut", 0.0))
    if cut == 0.0:
        return rank, exposure
    b = full_breadth(_full_board_px(np.array([m.toordinal() if hasattr(m, "toordinal") else int(m) for m in panels["months"]])), int(params.get("x_ma", 10)))
    weak = np.isfinite(b) & (b < float(params.get("x_thr", 0.5)))
    return rank, np.asarray(exposure, dtype=float) * np.where(weak, 1.0 - cut, 1.0)
