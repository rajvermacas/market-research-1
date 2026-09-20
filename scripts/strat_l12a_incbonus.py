"""Candidate: incumbency-aware book — retention bonus and grandfathered
eligibility over the champion base (strategy_lab contract).

Setup in words: rank, gates and shaped exposure are imported wholesale from
strat_floorhighrankpersist (the champion chain). On top, the book's own
holdings — replicated exactly by replaying the harness pick rule over the
candidate's own rows (see replay_book) — modify the score matrix two ways:

  inc_b  retention bonus: an incumbent (held entering the decision month)
         gets `rank + inc_b`, so a fresh name must out-rank it by the bonus
         to take its slot. Eligibility is untouched; this is pure reordering.
  gfade  grandfathered exit: an incumbent whose imported rank goes NaN (gate
         failure — lost the fresh print, fast-MA cross, or print drought)
         keeps a decaying score `last_finite_rank - gfade * months_since`
         instead of being dropped instantly. It exits only when its decayed
         score falls out of the top-N on its own.

Hypothesis: the harness re-picks top-N every month with no incumbency memory,
so the champion book churns whenever a marginal fresh name noses ahead of a
holder by a hair — paying 25 bps/side and discarding names whose trend is
intact. If month-to-month rank wiggles inside the top-N are noise, a retention
bonus buys the same exposure from fewer round trips (less cost drag, same or
better CAGR); and a decayed exit should dominate the fixed max_hold cap
because it keys on the name's own signal path, not a month count.
Falsified if: the bonus holds stale names through real deterioration (train
CAGR falls faster than cost savings) or the grandfather trails max_hold at
equal holding lengths — then the monthly re-pick discipline IS the edge.

PIT: the imported rank reads month-end closes through px[t] only (its own
chain's guarantee). Incumbency at t comes from replayed picks at months
< t, which use rows ≤ t-1 and closes ≤ px[t-1]. The replay masks on the same
px[t+1]-FINITENESS the harness's own pick rule uses — only the existence of a
next month-end close is read (a delisting bit), never its value; this matches
the harness exactly instead of approximating it. gfade memory stores the
name's own last finite base rank while in the book, purged on exit.

book_n must equal the harness --top (15 in this loop's trials).

SPACE = champion base + variants:
  {"inc_b": 0.3, "gfade": 0.0, "max_hold": 4}    retention reorder, champion risk
  {"inc_b": 1.0, "gfade": 0.0, "max_hold": 4}    hard incumbency priority
  {"inc_b": 0.0, "gfade": 0.15, "max_hold": 9}   decay exit vs fixed cap
  {"inc_b": 0.0, "gfade": 0.25, "max_hold": 12}  faster decay, longer room
"""

from __future__ import annotations

import numpy as np

from strat_floorhighrankpersist import score as _rp_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "floor_lb": [19],
    "lookback": [10],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [5],
    "sustain_lo": [3],
    "sustain_hi": [2],
    "tier_lo": [1.0],
    "tier_mid": [1.0],
    "pers_lb": [6],
    "pers_w": [-0.16],
    "max_hold": [4, 9, 12],
    "book_n": [15],
    "inc_b": [0.0, 0.3, 1.0],
    "gfade": [0.0, 0.15, 0.25],
}


def replay_book(panels, exposure, book_n: int, max_hold: int, build_row):
    """Exact replication of strategy_lab.backtest_scores' book-keeping (the
    trail_k path is not replicated — no trial here sets it). Walks decision
    months from start_i; at each t asks `build_row(t, held)` for the row the
    candidate wants the harness to see, then applies the harness's own rule:
    mask on finite row / px[t] / px[t+1], NaN out names past max_hold, take
    top `book_n` by stable descending sort when exposure > 0 and at least
    max(book_n // 2, 3) names survive.

    Returns (held_mat, entry_mat): held_mat[t, j] True when name j is in the
    book ENTERING decision month t (i.e. picked at t-1); entry_mat[t, j] its
    entry month index (-1 otherwise). Causal by construction.
    """
    px, months, cols = panels["px"], panels["months"], panels["cols"]
    start_i = panels["start_i"]
    col_idx = {s: j for j, s in enumerate(cols)}
    n_m, n_s = len(months), len(cols)
    held_mat = np.zeros((n_m, n_s), dtype=bool)
    entry_mat = np.full((n_m, n_s), -1, dtype=int)
    held: dict[str, int] = {}
    for t in range(start_i, n_m - 1):
        for sym, t0 in held.items():
            j = col_idx.get(sym)
            if j is not None:
                held_mat[t, j] = True
                entry_mat[t, j] = t0
        E = float(np.clip(exposure[t] if t < len(exposure) else 1.0, 0.0, 1.0))
        s = np.array(build_row(t, held), dtype=float, copy=True)
        ok = np.isfinite(s) & np.isfinite(px[t]) & np.isfinite(px[t + 1])
        s[~ok] = np.nan
        if max_hold:
            for sym, t0 in held.items():
                j = col_idx.get(sym)
                if j is not None and t - t0 >= max_hold:
                    s[j] = np.nan
        idx = np.flatnonzero(np.isfinite(s))
        pick: dict[str, int] = {}
        if E > 0 and idx.size >= max(book_n // 2, 3):
            order = idx[np.argsort(-s[idx], kind="stable")[:book_n]]
            for i in order:
                sym = cols[i]
                pick[sym] = held.get(sym, t)
        held = pick
    return held_mat, entry_mat


def score(panels, params):
    rank, exposure = _rp_score(panels, params)
    book_n = int(params.get("book_n", 15))
    max_hold = int(params.get("max_hold", 0) or 0)
    inc_b = float(params.get("inc_b", 0.0))
    gfade = float(params.get("gfade", 0.0))
    cols = panels["cols"]
    col_idx = {s: j for j, s in enumerate(cols)}

    out = np.array(rank, dtype=float, copy=True)
    last: dict[str, tuple[float, int]] = {}  # sym -> (last finite base rank, month)

    def build_row(t, held):
        row = np.array(rank[t], dtype=float, copy=True)
        if inc_b == 0.0 and gfade == 0.0:
            out[t] = row
            return row
        for sym in list(last):
            if sym not in held:
                del last[sym]  # memory only matters while in the book
        for sym, t0 in held.items():
            j = col_idx.get(sym)
            if j is None:
                continue
            if np.isfinite(row[j]):
                last[sym] = (float(row[j]), t)
                if inc_b:
                    row[j] += inc_b
            elif gfade > 0.0 and sym in last:
                sc, ts = last[sym]
                row[j] = sc - gfade * (t - ts)
        out[t] = row
        return row

    replay_book(panels, exposure, book_n, max_hold, build_row)
    return out, exposure
