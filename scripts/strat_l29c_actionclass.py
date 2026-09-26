"""Candidate: corporate-action event-class tilts on the L25 champion (Loop-29 C).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported,
verbatim; universe nse_all, invvol top 25 via policy keys). From the daily
adjustment factor R = adj_close/close, per-name event streams are split by step
size into LARGE (step >= ac_thr 0.02: lumpy/special distributions) and SMALL
(regular cash dividends). Signals (imported from strat_l21a_actionclass._signals,
never copied; endpoints = last bar strictly before months[t] and before
months[t-ac_lb]): LREC = months since the last LARGE event (censored at ac_cap),
SSIZ = winsorised SMALL-payout size over ac_lb months. Each armed signal is
tie-averaged-percentiled (strat_l20a_divyield._pct_tie, imported) across its
finite population and applied as score * (1 + w*(2*pct-1)); NaN scores stay
NaN; names with no factor history keep tilt 1. Rows t < ac_lb carry no tilt.
ac_lr_w < 0 favours recent lumpy events (the legacy KEEP sign); ac_ss_w > 0
favours large regular payers. All weights 0 = exact off-switch. Exposure
untouched.

Hypothesis: a recent lumpy distribution (special dividend / capital-structure
event) on a fresh-print name signals cash-rich, promoter-confident firms; large
regular payers are the steadier, more fillable end of the board. Under realistic
fills either could lower DD. Falsifier: no arm beats +30.09/-17.22 train at no
deeper DD.

Novelty: strat_l21a_actionclass (L21, KEEP-not-promoted on the legacy chain:
ac_lr_w -0.15 105.55/-15.55 train but -2.48pp forward CAGR) and the dividend
family (strat_l20a*, divcombo KEEP-not-promoted) were fitted under the legacy
execution model that bought un-fillable limit-up names. No L22-L28 realistic
ledger row carries ac_* keys. Changed base: realistic execution + liqconfirm
strict regime + invvol top 25 book.
"""
from __future__ import annotations
import numpy as np
from strat_l23a_liqconfirm import score as _base
from strat_l21a_actionclass import _signals
from strat_l20a_divyield import _pct_tie

NEEDS_DAILY = True
SPACE = {"ac_lr_w": [-0.15, 0.15], "ac_ss_w": [-0.15, 0.15],
         "ac_lb": [36], "ac_thr": [0.02], "ac_cap": [60]}


def score(panels, params):
    scores, exposure = _base(panels, params)
    wl = float(params.get("ac_lr_w", 0.0))
    ws = float(params.get("ac_ss_w", 0.0))
    if wl == 0.0 and ws == 0.0:
        return scores, exposure
    k = int(params.get("ac_lb", 36))
    thr = float(params.get("ac_thr", 0.02))
    cap = float(params.get("ac_cap", 60.0))
    months = [m.date() if hasattr(m, "date") else m for m in panels["months"]]
    LREC, _LCNT, _SREC, SSIZ = _signals(months, panels["cols"], k, thr, cap)
    out = np.array(scores, dtype=float, copy=True)
    for mat, w in ((LREC, wl), (SSIZ, ws)):
        if w == 0.0:
            continue
        for t in range(k, out.shape[0]):
            sig = mat[t]
            valid = np.isfinite(sig)
            if int(valid.sum()) < 5:
                continue
            pct = _pct_tie(sig[valid])
            tilt = np.ones(out.shape[1])
            tilt[valid] = 1.0 + w * (2.0 * pct - 1.0)
            fin = np.isfinite(out[t])
            out[t, fin] = out[t, fin] * tilt[fin]
    return out, exposure
