"""Candidate: strategy equity-curve state on the champion book (strategy_lab
contract).

Setup in words: the CURRENT champion chain — strat_l15b_insideday (floor-lift
fresh-print rank among short-trend-passing, print-continuity-passing names,
breadth-tier exposure with tier 0.9999, regime-conditional cap cap_weak/
cap_full, eligibility-wobble gw_w 0.15, inside-day tilt ids_w -0.13 / lb 3) —
is imported wholesale via strat_l15b_insideday.score; its scores are capped
inline exactly as the champion caps them and are NOT re-ranked by this
mechanism. What changes is the deployed fraction, scaled by the state of
the STRATEGY'S OWN EQUITY CURVE, measured by an exact causal replay of the
harness pick rule (imported `replay_book` from strat_l12a_incbonus — the
Loop-12-validated replica — never re-implemented here):

    base book   = cap-mirrored imported scores (champion-identical picks)
    held/entry  = replay_book(...) over that book with the champion's own
                  breadth exposure (exact: pick depends on E only through
                  E > 0, and es_floor > 0 keeps E_final > 0 iff breadth > 0)
    dd[t]       = eq / max(eq over the last es_lb month-end equities) - 1
                  (es_lb 0 = all-time running peak), eq accumulated with the
                  harness's own turnover-cost bookkeeping at es_cost_bps
    E_state[t]  = clip(1 + es_w * dd[t], es_floor, 1.0)
    E[t]        = clip(E_breadth[t] * E_state[t], 0.0, 1.0)

es_w > 0 scales the deployed fraction DOWN while the strategy sits under
its recent drawdown and back UP toward full as the curve recovers toward
its rolling peak; the book composition never changes (scores untouched, cap
keyed on the champion's own breadth exposure), so this is purely the
capital-deployment channel — one channel, clean attribution.

Timeline of the state: at decision row t the realized equity includes the
returns of every holding month up to the one ENDING at the decision close
(r_{t-1} = px[t]/px[t-1]-1 was just realized); the pick made at t is known
but unrealized. dd[t] is therefore computed from eq through r_{t-1} —
strictly causal.

Hypothesis: the champion's equity curve is a state NO market-level input
reproduces — its book is a small-cap fresh-high subset with a drawdown
rhythm of its own (86% stop-out rate paid by far-distance winners, per the
LESSONS). If the champion's drawdowns cluster (momentum-crash months follow
momentum-crash months: the same regime that hurt last month hurts next), a
drawdown-scaled exposure cuts the second leg of every double-bottom crash
and improves return-per-drawdown; if instead the champion's DD months are
where the NEXT month's recovery is bought (post-crash bounce), scaling down
in drawdown systematically sells the bottom and the state axis closes.

NOVELTY STATEMENT (vs the dead families this file must be distinguished
from): closest prior art is the DEAD index-DD veto — exposure keyed on the
MARKET index's drawdown/MA state — and the DEAD book-health floors, which
replayed the book but keyed eligibility on PER-NAME gate attrition. The one
thing changed: the input is the STRATEGY'S OWN REPLAYED EQUITY CURVE — a
portfolio-level state that is a function of the champion's picks, costs and
exposure path, not of the market's, and not of any single name's gates.
Neither dead mechanism consumed (or could compute) the strategy's own
drawdown percentile path; the replay is what makes the input exist. It is
NOT a re-shape of vol targeting (input: realized-vol level), not exposure
hysteresis (no enter/exit memory on a market signal — the state here is
level-of-equity, recomputed causally every month), and not a book-health
floor (no eligibility is touched). Loop-16's incumbency family (bonus/
budget/hurdle) changed the BOOK; this changes nothing but the deployed
fraction.

Import chain: strat_l17c_eqstate -> strat_l15b_insideday.score (champion
lift + ids tilt) -> cap step mirrored inline (from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score) ->
strat_l12a_incbonus.replay_book (harness pick-rule replica, imported) for
the causal book.

PIT argument: dd[t] reads eq accumulated from picks at rows <= t-1 and
returns realized through px[t] — nothing future. replay_book's pick mask
touches px[t+1] finiteness (the harness's own conservative quirk, baked
into every recorded number; its VALUE is never read for the decision).
px[t+1] for the CURRENT row is used only to realize r_t for the NEXT
decision's state — which is exactly when it becomes known.

Off-switch identity: es_w = 0.0 (default) forces E_state = 1.0 for every
row, so E = E_breadth bitwise, `out` is bitwise the champion's scores, and
the replay (still executed) cannot influence anything.

Replay validation (DONE, designer smoke): with es_w=0 the replayed equity
accumulation must reproduce strategy_lab.backtest_scores' own curve.
Verified: replay full_cagr +0.7631523339 / full_dd -0.2710664392 ==
backtest_scores on the same (scores, E) == best.json's full-window metrics
(1e-12). One boundary bug was found and fixed on the way: replay_book
never writes the book entering row T-1, but backtest_scores realizes row
T-2's return — _replay_equity now replicates the pick rule for that
boundary row. Re-validation recipe: replay curve seg == backtest_scores
seg to 1e-12, E_final bitwise E.

Exactness conditions (all default-true in this loop's trials): book_n must
equal the harness --top (15); max_hold must be passed via params-json (the
champion's 3) so the replay's hold clock matches; es_floor must be > 0 so
E_final > 0 exactly when breadth > 0 (pick-set equivalence); trail_k is NOT
supported (the replay does not replicate the trail path — no trial here
sets it); es_cost_bps defaults to 25 matching --cost-bps 25.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

Falsifier: if every tested (es_w, es_lb, es_floor) combination trails the
flat base — train +96.882% / DD -17.032% / calmar 5.688 — the strategy's
own drawdown state carries no exposure-relevant information beyond the
breadth tiers, and the strategy-state axis closes at this base. A variant
whose only effect is lower `invested` with unchanged CAGR shape is the
known "buy cash-like returns" trap (LESSONS) — check CAGR before reading
any DD improvement.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key passed via params-json, not consumed by
        the score math directly but REQUIRED for the replay to match)
        + es_w {2, 4, 8} (drawdown sensitivity; 0.0 = off-switch)
        + es_lb {6, 12, 0} (drawdown window in months; 0 = all-time peak)
        + es_floor {0.4, 0.6} (minimum E_state once it fires)
        + book_n {15} (must equal --top) + es_cost_bps {25} (replay cost).
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l15b_insideday import score as _ids_score
from strat_l12a_incbonus import replay_book

NEEDS_DAILY = True  # the delegate's ids term reads the daily panel (ids_w -0.13)

SPACE = {
    # champion keys (pinned, docs only)
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "floor_lb": [19],
    "lookback": [12],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [5],
    "sustain_lo": [3],
    "sustain_hi": [2],
    "tier_lo": [0.9999],
    "tier_mid": [0.9999],
    "cap_weak": [11],
    "cap_full": [20],
    "gf_lb": [12],
    "gf_w": [0.0],
    "gw_w": [0.15],
    "ids_lb": [3],
    "ids_w": [-0.13],
    # this file's keys
    "es_w": [2, 4, 8],
    "es_lb": [6, 12, 0],
    "es_floor": [0.4, 0.6],
    "book_n": [15],
    "es_cost_bps": [25],
}


def _replay_equity(panels, base_scores, E_b, book_n: int, max_hold: int,
                   es_w: float, es_lb: int, es_floor: float, cost: float):
    """Equity-curve replay over the champion-identical book. held_mat/
    entry_mat come from the imported, Loop-12-validated pick-rule replica;
    the equity accumulation mirrors strategy_lab.backtest_scores line for
    line (nanmean holding return, turnover = new entrants / pick size,
    eq * (1 + E*r) * (1 - cost*turnover), unchanged when no pick). Returns
    (E_final, eq_curve) where E_final[t] was decided on equity realized
    strictly before the decision close px[t]."""
    held_mat, entry_mat = replay_book(panels, E_b, book_n, max_hold,
                                      lambda t, held: base_scores[t])
    px = panels["px"]
    start_i = panels["start_i"]
    T = base_scores.shape[0]
    # Boundary fill: replay_book's loop writes held_mat[t] for t <= T-2 only,
    # so the book ENTERING row T-1 (the pick made at the last decision row
    # T-2) is never written — yet backtest_scores DOES realize row T-2's
    # return into the equity curve. Replicate the pick rule for that row.
    t = T - 2
    if t >= start_i:
        s = np.array(base_scores[t], dtype=float, copy=True)
        ok = np.isfinite(s) & np.isfinite(px[t]) & np.isfinite(px[t + 1])
        s[~ok] = np.nan
        for j in np.flatnonzero(held_mat[t]):
            if max_hold and t - int(entry_mat[t, j]) >= max_hold:
                s[j] = np.nan
        idx = np.flatnonzero(np.isfinite(s))
        if E_b[t] > 0 and idx.size >= max(book_n // 2, 3):
            order = idx[np.argsort(-s[idx], kind="stable")[:book_n]]
            for i in order:
                held_mat[t + 1, i] = True
                entry_mat[t + 1, i] = int(entry_mat[t, i]) if held_mat[t, i] else t
    E_final = np.array(E_b, dtype=float, copy=True)
    eq = 1.0
    eq_hist: list[float] = []
    for t in range(start_i, T - 1):
        if es_w != 0.0:
            win = eq_hist[-es_lb:] if es_lb > 0 else eq_hist
            peak_w = max([1.0] + [float(x) for x in win])
            dd = eq / peak_w - 1.0
            E_state = min(1.0, max(es_floor, 1.0 + es_w * dd))
        else:
            E_state = 1.0
        E_final[t] = min(max(E_b[t] * E_state, 0.0), 1.0)
        idx = np.flatnonzero(held_mat[t + 1])
        if idx.size:
            r = np.nanmean(px[t + 1, idx] / px[t, idx]) - 1.0
            new_count = int((entry_mat[t + 1, idx] == t).sum())
            turnover = new_count / idx.size
            eq = eq * (1.0 + E_final[t] * r) * (1.0 - cost * turnover)
        eq_hist.append(eq)
    return E_final, np.array([1.0] + eq_hist)


def score(panels, params):
    lift, exposure = _ids_score(panels, params)

    # cap step mirrored inline from strat_floorhightiershapeconc.score /
    # strat_l13a_concwobble.score — on the UNMODIFIED lift, keyed on the
    # champion's own exposure (book composition champion-identical)
    out = np.array(lift, dtype=float, copy=True)
    E_b = np.asarray(exposure, dtype=float)
    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    for t in range(out.shape[0]):
        r = out[t]
        fin = np.flatnonzero(np.isfinite(r))
        if fin.size == 0:
            continue
        cap = cf if E_b[t] >= 1.0 else cw
        if fin.size <= cap:
            continue
        order = fin[np.argsort(-r[fin], kind="stable")]
        out[t, order[cap:]] = np.nan

    E_final = E_b
    es_w = float(params.get("es_w", 0.0))
    if es_w != 0.0:
        es_lb = int(params.get("es_lb", 12) or 0)
        es_floor = float(params.get("es_floor", 0.4))
        cost = float(params.get("es_cost_bps", 25) or 25) / 10_000.0
        book_n = int(params.get("book_n", 15))
        max_hold = int(params.get("max_hold", 0) or 0)
        E_final, _curve = _replay_equity(panels, out, E_b, book_n, max_hold,
                                         es_w, es_lb, es_floor, cost)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return out, np.clip(E_final, 0.0, 1.0)
