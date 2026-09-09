#!/usr/bin/env python3
"""Synthetic checks on the harness arithmetic. Run after touching anything in `autoresearch/`.

Four errors once survived repeated self-review in this repository, three of them pointing the
same way — toward a better-looking result. These are the tests that would have caught that
class of mistake: every one builds a panel whose right answer is known by construction and
asserts the harness reproduces it.

    python autoresearch/test_harness.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evaluate  # noqa: E402
import toolkit  # noqa: E402
from prepare import Panel, _ffill  # noqa: E402

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def panel_of(close: np.ndarray, tradable: np.ndarray | None = None,
             step_days: int = 1) -> Panel:
    """A minimal Panel around a price matrix — everything else follows from it."""
    close = np.asarray(close, dtype=np.float64)
    t, n = close.shape
    dates = np.datetime64("2010-01-04", "D") + np.arange(t) * step_days
    mark = _ffill(close)
    ones = np.ones_like(close) if tradable is None else np.asarray(tradable, dtype=bool)
    return Panel(dates=dates, symbols=tuple(f"S{i}" for i in range(n)), open_=close, high=close,
                 low=close, close=close, mark=mark, volume=np.full_like(close, 1e6),
                 rupee_volume=close * 1e6, tradable=ones.astype(bool),
                 meta=dict(universe="synthetic", min_turnover=0, liquidity_window=1,
                           min_history=0, cache="-", source="synthetic"))


def close_to(a: float, b: float, tol: float = 1e-9, what: str = "") -> None:
    if not abs(a - b) <= tol:
        raise AssertionError(f"{what}: {a!r} != {b!r} (tolerance {tol})")


# ------------------------------------------------------------------------------- plumbing


@case
def forward_fill_leaves_the_leading_gap_alone():
    a = np.array([[np.nan, 1.0], [np.nan, np.nan], [3.0, 4.0], [np.nan, np.nan]])
    f = _ffill(a)
    assert np.isnan(f[0, 0]) and np.isnan(f[1, 0]), "nothing to carry forward yet"
    close_to(f[1, 1], 1.0, what="gap carries the last price")
    close_to(f[3, 0], 3.0, what="gap carries the last price")


@case
def an_ewm_survives_a_missing_session():
    a = np.array([[10.0], [11.0], [np.nan], [12.0], [13.0], [14.0]])
    e = toolkit.ema(a, span=2, warmup=0)
    assert np.isnan(e[2, 0]), "the missing bar itself has no value"
    assert np.isfinite(e[3, 0]) and np.isfinite(e[5, 0]), \
        "one NaN must not poison the rest of the column"


@case
def recursive_indicators_are_blanked_until_warm():
    rng = np.random.default_rng(0)
    px = np.cumprod(1 + rng.normal(0, 0.01, size=(200, 3)), axis=0) * 100
    r = toolkit.rsi(px, period=14)
    assert np.isnan(r[:41]).all(), "Wilder's RSI reads 100.0 on bar one; it must be masked"
    assert np.isfinite(r[42:]).all(), "and it must be available once warm"
    e = toolkit.ema(px, span=10)
    assert np.isnan(e[:29]).all() and np.isfinite(e[30:]).all()


@case
def cross_sectional_rank_spans_zero_to_one():
    r = toolkit.cs_rank(np.array([[3.0, 1.0, 2.0, np.nan]]))
    close_to(r[0, 1], 0.0, what="smallest")
    close_to(r[0, 2], 0.5, what="middle")
    close_to(r[0, 0], 1.0, what="largest")
    assert np.isnan(r[0, 3]), "a missing value has no rank"


@case
def equal_weight_holds_cash_when_slots_are_unfilled():
    mask = np.array([[True, True, False, False]])
    close_to(toolkit.equal_weight(mask, slots=4).sum(), 0.5, what="half the book is cash")
    close_to(toolkit.equal_weight(mask).sum(), 1.0, what="without slots it is fully invested")


# ------------------------------------------------------------------------------ accounting


@case
def weights_are_applied_to_the_next_bar_not_this_one():
    close = np.array([[100.0], [110.0], [121.0], [133.1]])
    p = panel_of(close)
    w = np.zeros((4, 1))
    w[1] = 1.0                                   # decided at the close of bar 1
    run = evaluate.simulate(w, p, cost_bps=0.0)
    close_to(run.net[1], 0.0, what="the decision bar earns nothing")
    close_to(run.net[2], 0.10, what="the following bar's move is what it earns")
    close_to(run.net[3], 0.0, 1e-12, what="and the book is flat again after")


@case
def a_round_trip_costs_exactly_the_quoted_spread():
    close = np.ones((6, 2)) * 100.0
    p = panel_of(close)
    w = np.zeros((6, 2))
    w[::2, 0] = 1.0                              # alternate the whole book between two names
    w[1::2, 1] = 1.0
    run = evaluate.simulate(w, p, cost_bps=25.0)
    close_to(run.turnover[1], 2.0, what="out of one name and into another")
    close_to(run.net[1], -25e-4, 1e-12, what="one round trip at 25 bps")
    buy_hold = np.zeros((6, 2))
    buy_hold[:, 0] = 1.0
    only = evaluate.simulate(buy_hold, p, cost_bps=25.0)
    close_to(only.net[0], -12.5e-4, 1e-12, what="a one-way entry is half a round trip")
    close_to(float(np.abs(only.net[1:]).sum()), 0.0, 1e-12, what="and is never charged again")


@case
def drift_is_carried_so_a_flat_book_costs_nothing():
    close = np.array([[100.0], [200.0], [400.0]])
    p = panel_of(close)
    held = evaluate.simulate(np.ones((3, 1)), p, cost_bps=25.0)
    close_to(float(held.turnover[1:].sum()), 0.0, 1e-12,
             what="a fully invested single name never needs rebalancing")
    half = evaluate.simulate(np.full((3, 1), 0.5), p, cost_bps=0.0)
    # 0.5 doubles to 1.0 against 0.5 in cash: the book is now 2/3 stock, and returning it to
    # half costs 1/6 of turnover.
    close_to(half.net[1], 0.5, what="half the book doubled")
    close_to(half.turnover[1], 1 / 6, 1e-12, what="drift back to target")


@case
def cash_earns_nothing_and_dilutes_the_return():
    close = np.array([[100.0], [110.0]])
    p = panel_of(close)
    run = evaluate.simulate(np.full((2, 1), 0.4), p, cost_bps=0.0)
    close_to(run.net[1], 0.04, what="40% invested in a 10% move")


@case
def compounding_and_drawdown_are_what_they_say():
    daily = 0.0004
    close = (1 + daily) ** np.arange(1000).reshape(-1, 1) * 100.0
    p = panel_of(close)
    run = evaluate.simulate(np.ones((1000, 1)), p, cost_bps=0.0)
    m = evaluate.measure("all", run, p, None, None)
    years = (p.dates[-1] - p.dates[0]).astype(int) / 365.25
    close_to(m.cagr, (1 + daily) ** (999 / years) - 1, 1e-6, what="CAGR from the timestamps")
    close_to(m.max_dd, 0.0, 1e-12, what="a monotonic curve never draws down")
    fall = np.concatenate([np.linspace(100, 200, 50), np.linspace(200, 150, 50)])
    p2 = panel_of(fall.reshape(-1, 1))
    run2 = evaluate.simulate(np.ones((100, 1)), p2, cost_bps=0.0)
    close_to(evaluate.measure("all", run2, p2, None, None).max_dd, -0.25, 1e-9,
             what="200 down to 150")


@case
def the_benchmark_is_the_mean_of_normalised_prices_never_the_median():
    close = np.column_stack([
        np.linspace(100, 100, 11),      # flat
        np.linspace(100, 100, 11),      # flat
        np.linspace(100, 400, 11),      # the outlier that the median would throw away
    ])
    p = panel_of(close)
    r = evaluate.benchmark_returns(p, p.window(None, None))
    final = float(np.cumprod(1 + r)[-1])
    close_to(final, (1 + 1 + 4) / 3, 1e-9, what="mean of normalised prices")
    assert final > 1.0, "the median of these three names is 1.0 — that is the bug being tested"


@case
def the_annualisation_is_read_off_the_timestamps():
    rng = np.random.default_rng(3)
    close = np.cumprod(1 + rng.normal(0.0003, 0.01, size=(500, 1)), axis=0) * 100
    daily = panel_of(close, step_days=1)
    weekly = panel_of(close, step_days=7)
    w = np.ones((500, 1))
    a = evaluate.measure("d", evaluate.simulate(w, daily, 0.0), daily, None, None)
    b = evaluate.measure("w", evaluate.simulate(w, weekly, 0.0), weekly, None, None)
    assert a.years < b.years / 6, "the same bars spread over seven times the calendar"
    close_to(a.sharpe / b.sharpe, np.sqrt(7), 1e-6,
             what="Sharpe scales with bars per year, which is derived not assumed")


# ---------------------------------------------------------------------------------- guards


@case
def sanitise_refuses_shorts_leverage_and_untradable_names():
    close = np.ones((3, 3)) * 100.0
    tradable = np.ones((3, 3), dtype=bool)
    tradable[:, 2] = False
    p = panel_of(close, tradable)
    w = np.array([[-0.5, 0.5, 0.5], [0.9, 0.9, 0.0], [np.nan, 0.3, 0.0]])
    s = evaluate.sanitise(w, p, max_gross=1.0)
    close_to(s[0, 0], 0.0, what="no shorting")
    close_to(s[0, 2], 0.0, what="no holding an untradable name")
    close_to(float(s[1].sum()), 1.0, 1e-12, what="1.8 gross is scaled back to 1.0")
    close_to(s[2, 0], 0.0, what="NaN is not a position")


@case
def the_score_is_zeroed_by_a_book_that_barely_trades_or_barely_invests():
    def m(label, sharpe, trades, exposure):
        return evaluate.Metrics(label=label, bars=1000, years=4.0, cagr=0.2, sharpe=sharpe,
                                max_dd=-0.2, calmar=1.0, exposure=exposure, turns_per_year=1.0,
                                trades=trades, bench_cagr=0.1, bench_sharpe=0.5,
                                bench_max_dd=-0.3)
    good = evaluate.score(m("train", 1.2, 200, 0.8), m("val", 0.9, 200, 0.8))
    close_to(good[0], 0.9, what="the score is the weaker of the two windows")
    assert evaluate.score(m("train", 3.0, 5, 0.8), m("val", 3.0, 5, 0.8))[0] == 0.0
    assert evaluate.score(m("train", 3.0, 200, 0.01), m("val", 3.0, 200, 0.01))[0] == 0.0


@case
def the_lookahead_probe_catches_a_strategy_that_reads_forward():
    rng = np.random.default_rng(7)
    close = np.cumprod(1 + rng.normal(0.0005, 0.02, size=(400, 4)), axis=0) * 100
    p = panel_of(close)

    def honest(panel):
        return toolkit.equal_weight(toolkit.top_n(toolkit.pct_change(panel.close, 20), 2), slots=2)

    def cheat(panel):
        # Buys whichever name ends the panel highest — invisible in-sample, fatal out of it.
        best = np.argmax(panel.close[-1])
        w = np.zeros_like(panel.close)
        w[:, best] = 1.0
        return w

    assert evaluate.lookahead_probe(honest, p, cuts=5) == [], "a causal book must pass"
    assert evaluate.lookahead_probe(cheat, p, cuts=5), "a peeking book must not"


@case
def holding_between_rebalances_costs_no_turnover():
    rng = np.random.default_rng(11)
    close = np.cumprod(1 + rng.normal(0.0004, 0.015, size=(300, 6)), axis=0) * 100
    p = panel_of(close)
    target = toolkit.equal_weight(toolkit.top_n(toolkit.pct_change(close, 20), 3), slots=3)
    held = toolkit.hold_until_rebalance(target, p.mark, every=21)
    daily = evaluate.simulate(evaluate.sanitise(target, p), p, cost_bps=25.0)
    monthly = evaluate.simulate(evaluate.sanitise(held, p), p, cost_bps=25.0)
    assert monthly.turnover.sum() < daily.turnover.sum() / 4, \
        "a monthly rebalance must trade far less than a daily one"
    between = [t for t in range(1, 300) if t % 21 != 0]
    close_to(float(monthly.turnover[between].sum()), 0.0, 1e-9,
             what="no trading happens between rebalances")


def main() -> int:
    failed = []
    for fn in CASES:
        name = fn.__name__.replace("_", " ")
        try:
            fn()
        except AssertionError as exc:
            failed.append((name, str(exc)))
            print(f"FAIL  {name}\n      {exc}")
        else:
            print(f"ok    {name}")
    print(f"\n{len(CASES) - len(failed)}/{len(CASES)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
