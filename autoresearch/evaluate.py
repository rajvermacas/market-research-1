#!/usr/bin/env python3
"""Portfolio simulation, metrics and the score — the part of the harness a strategy may not touch.

Everything that decides whether an idea was an improvement lives here: the cost model, the
benchmark, the split scoring and the look-ahead probe. A strategy supplies weights and nothing
else, so no experiment can improve its score by changing what "improvement" means.

The accounting, stated once so a reader can check it:

    r[t]        asset return from the previous session's mark to this one
    gross[t]    sum(w_held * r[t]) — capital not in a position earns nothing
    drift       held weights after the move, renormalised by the portfolio's own return
    turnover[t] sum |w_target[t] - drift|, so a full swap of one name reads 2 x its weight
    cost[t]     (cost_bps / 2) x turnover[t] — a round trip in one name costs `cost_bps` once
    net[t]      gross[t] - cost[t]

Weights in row `t` are the book held from the close of session `t` to the close of `t + 1`.
The harness applies that shift itself, so a strategy that returns "what I want to own having
seen bar t" is correct by construction and cannot accidentally trade on its own outcome.

The benchmark is an equal-weight buy-and-hold of every name tradable on the window's first
session: the **mean** of normalised prices, never the median. The median is the path of the
median stock — not tradeable, always lower, and it has manufactured an entire apparent edge in
this repository before.

The score is `min(Sharpe on train, Sharpe on validation)`. The minimum, rather than either one
alone or their average, because a configuration fitted to one window is exactly what the loop
will otherwise converge on. Two guards zero the score outright: a book that almost never
trades, and a book that holds almost no capital — both can post a flattering Sharpe while
being nothing anyone could run.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from prepare import Panel


@dataclass(frozen=True)
class Run:
    """The full simulated history, before any window is carved out of it."""

    weights: np.ndarray      # (T, N) after sanitising — what was actually held
    net: np.ndarray          # (T,) net-of-cost portfolio return per session
    gross: np.ndarray        # (T,) before costs
    turnover: np.ndarray     # (T,) sum |dw| at each rebalance
    exposure: np.ndarray     # (T,) fraction of capital invested
    opened: np.ndarray       # (T,) positions opened this session


@dataclass(frozen=True)
class Metrics:
    label: str
    bars: int
    years: float
    cagr: float
    sharpe: float
    max_dd: float
    calmar: float
    exposure: float
    turns_per_year: float
    trades: int
    bench_cagr: float
    bench_sharpe: float
    bench_max_dd: float


def sanitise(weights: np.ndarray, panel: Panel, max_gross: float = 1.0,
             allow_short: bool = False) -> np.ndarray:
    """Force a strategy's output into a book that could actually be held.

    Non-finite weights become zero, weights on names that were not tradable on that bar become
    zero, and a row whose gross exposure exceeds `max_gross` is scaled back rather than
    silently levered. Shorting is off by default: the panel is long-only cash equity.
    """
    w = np.asarray(weights, dtype=np.float64)
    if w.shape != panel.close.shape:
        raise ValueError(f"strategy returned weights of shape {w.shape}, "
                         f"expected {panel.close.shape} (bars x symbols)")
    w = np.where(np.isfinite(w), w, 0.0)
    if not allow_short:
        w = np.maximum(w, 0.0)
    w = np.where(panel.tradable, w, 0.0)
    gross = np.abs(w).sum(axis=1, keepdims=True)
    scale = np.where(gross > max_gross, max_gross / np.maximum(gross, 1e-12), 1.0)
    return w * scale


def simulate(weights: np.ndarray, panel: Panel, cost_bps: float = 25.0) -> Run:
    """Walk the book forward one session at a time. See the module docstring for the algebra."""
    w = weights
    mark = panel.mark
    r = np.zeros_like(mark)
    with np.errstate(invalid="ignore", divide="ignore"):
        r[1:] = mark[1:] / mark[:-1] - 1.0
    r = np.where(np.isfinite(r), r, 0.0)

    n_bars = panel.n_bars
    half = cost_bps / 10_000 / 2
    net = np.zeros(n_bars)
    gross_r = np.zeros(n_bars)
    turn = np.zeros(n_bars)
    opened = np.zeros(n_bars, dtype=np.int64)
    held = np.zeros(panel.n_symbols)

    for t in range(n_bars):
        if t:
            g = float(held @ r[t])
            if 1.0 + g <= 0.0:
                raise RuntimeError(f"the book lost everything on {panel.dates[t]}; "
                                   f"there is nothing left to renormalise")
            held = held * (1.0 + r[t]) / (1.0 + g) if held.any() else held
            gross_r[t] = g
        target = w[t]
        turn[t] = float(np.abs(target - held).sum())
        opened[t] = int(np.count_nonzero((target > 0) & (held <= 0)))
        net[t] = gross_r[t] - half * turn[t]
        held = target.copy()

    return Run(weights=w, net=net, gross=gross_r, turnover=turn,
               exposure=np.abs(w).sum(axis=1), opened=opened)


def _curve_stats(returns: np.ndarray, years: float) -> tuple[float, float, float]:
    """Compound a return series into CAGR, annualised Sharpe and max drawdown."""
    equity = np.cumprod(1.0 + returns)
    cagr = equity[-1] ** (1 / years) - 1 if years > 0 and equity[-1] > 0 else float("nan")
    dd = float((equity / np.maximum.accumulate(equity) - 1).min())
    sd = returns.std(ddof=1)
    # Bars per year is derived from the timestamps by the caller, never assumed: a hard-coded
    # constant overstated every CAGR in this repository once already.
    per_year = len(returns) / years if years > 0 else float("nan")
    sharpe = float(returns.mean() / sd * np.sqrt(per_year)) if sd > 0 else 0.0
    return float(cagr), sharpe, dd


def benchmark_returns(panel: Panel, mask: np.ndarray) -> np.ndarray:
    """Equal-weight buy-and-hold of the names tradable on the window's first session."""
    rows = np.flatnonzero(mask)
    first = rows[0]
    members = panel.tradable[first] & np.isfinite(panel.mark[first])
    if not members.any():
        return np.zeros(len(rows))
    px = panel.mark[rows][:, members]
    base = px[0]
    index = np.nanmean(px / base, axis=1)
    out = np.zeros(len(rows))
    out[1:] = index[1:] / index[:-1] - 1.0
    return np.where(np.isfinite(out), out, 0.0)


def measure(label: str, run: Run, panel: Panel, start: str | None, end: str | None) -> Metrics:
    """Metrics for one date window, rebased to that window."""
    mask = panel.window(start, end)
    if mask.sum() < 2:
        raise ValueError(f"window {label} ({start}..{end}) holds {int(mask.sum())} sessions")
    dates = panel.dates[mask]
    years = (dates[-1] - dates[0]).astype("timedelta64[D]").astype(float) / 365.25
    net = run.net[mask]
    cagr, sharpe, dd = _curve_stats(net, years)
    b_cagr, b_sharpe, b_dd = _curve_stats(benchmark_returns(panel, mask), years)
    return Metrics(
        label=label, bars=int(mask.sum()), years=years, cagr=cagr, sharpe=sharpe, max_dd=dd,
        calmar=float(cagr / abs(dd)) if dd < 0 else float("inf"),
        exposure=float(run.exposure[mask].mean()),
        turns_per_year=float(run.turnover[mask].sum() / 2 / years) if years > 0 else 0.0,
        trades=int(run.opened[mask].sum()),
        bench_cagr=b_cagr, bench_sharpe=b_sharpe, bench_max_dd=b_dd)


def score(train: Metrics, validation: Metrics, min_trades: int = 100,
          min_exposure: float = 0.20) -> tuple[float, str]:
    """The single number the keep/revert decision reads. Returns (score, reason-if-zeroed)."""
    trades = train.trades + validation.trades
    if trades < min_trades:
        return 0.0, f"only {trades} positions opened across train+validation (floor {min_trades})"
    exposure = (train.exposure * train.bars + validation.exposure * validation.bars) / \
               (train.bars + validation.bars)
    if exposure < min_exposure:
        return 0.0, (f"average exposure {exposure:.1%} is below the {min_exposure:.0%} floor — "
                     f"a book that holds no capital is not a strategy")
    return float(min(train.sharpe, validation.sharpe)), ""


def lookahead_probe(generate, panel: Panel, cuts: int = 4, seed: int = 0,
                    tol: float = 1e-9) -> list[str]:
    """Re-run the strategy on truncated history and check its last row did not move.

    A causal strategy asked "what would you hold having seen bars 0..t" must give the same
    answer whether or not bars after `t` exist. Anything that reads forward — a full-sample
    mean, a centred window, a `.max()` over the whole column, a threshold fitted on the panel
    it trades — changes its answer when the future is removed, and this is what catches it.
    """
    full = np.asarray(generate(panel), dtype=np.float64)
    rng = np.random.default_rng(seed)
    lo = int(panel.n_bars * 0.55)
    picks = sorted(rng.choice(np.arange(lo, panel.n_bars - 1), size=min(cuts, panel.n_bars - lo - 1),
                              replace=False).tolist())
    failures = []
    for t in picks:
        partial = np.asarray(generate(panel.head(t + 1)), dtype=np.float64)
        a = np.nan_to_num(full[t], nan=0.0)
        b = np.nan_to_num(partial[t], nan=0.0)
        gap = float(np.abs(a - b).max()) if a.size else 0.0
        if gap > tol:
            failures.append(f"{panel.dates[t]}: weights differ by up to {gap:.2e} when the "
                            f"panel is truncated there")
    return failures
