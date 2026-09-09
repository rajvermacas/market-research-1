#!/usr/bin/env python3
"""Causal indicators over a wide (bars x symbols) price matrix — part of the immutable harness.

Every strategy in this loop reads the same panel shape: `T` rows of dates by `N` columns of
symbols, NaN wherever a symbol had no bar. The functions here are the toolkit for that shape.
They exist so a strategy never writes a second copy of an indicator that can drift from the
first — the repository has already paid for that mistake once.

Two properties hold for everything in this file, and a strategy may rely on them:

  * **Causal.** Row `t` of any output is a function of rows `<= t` only. Nothing reads forward.
  * **Warm-up guarded.** A recursive indicator returns a plausible number from its first bar —
    Wilder's RSI seeded at zero reads exactly 100.0 on bar one — so every recursive function
    here masks its first `warmup` valid bars per symbol to NaN. The default follows the house
    template of `period * 3`. Pass a smaller `warmup` only deliberately.

Missing bars are not repaired. A symbol that lost a session carries a NaN there, which opens a
hole of `window` bars in any rolling statistic and one bar in an EWM one. That is the intended
behaviour: the strategy simply has no signal for that name on those days, which is the truth.

The RSI is `screener.rsi` — the same Wilder implementation validated against a textbook loop —
applied column-wise, rather than a fourth reimplementation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from screener import rsi as _rsi_expr  # noqa: E402


# ------------------------------------------------------------------ matrix <-> frame plumbing


def _frame(a: np.ndarray) -> pl.DataFrame:
    """(T, N) float matrix -> a wide frame with NaN represented as null.

    The distinction matters: polars propagates NaN through `ewm_mean` forever, so one missing
    session would kill a symbol for the rest of the panel. As null, with `ignore_nulls`, the
    EWM skips the gap and resumes.
    """
    if a.ndim != 2:
        raise ValueError(f"expected a 2-D (bars x symbols) matrix, got shape {a.shape}")
    names = [f"c{i}" for i in range(a.shape[1])]
    return pl.from_numpy(np.asarray(a, dtype=np.float64), schema=names).with_columns(
        pl.all().fill_nan(None)
    )


def _values(df: pl.DataFrame) -> np.ndarray:
    """Wide frame -> (T, N) float matrix, nulls back to NaN."""
    return df.select(pl.all().cast(pl.Float64)).to_numpy()


def _apply(a: np.ndarray, expr_for) -> np.ndarray:
    df = _frame(a)
    return _values(df.select([expr_for(c).alias(c) for c in df.columns]))


def _valid_count(a: np.ndarray) -> np.ndarray:
    """Running count of non-NaN observations per column, inclusive of the current row."""
    return np.cumsum(np.isfinite(a), axis=0)


def _mask_warmup(out: np.ndarray, source: np.ndarray, warmup: int) -> np.ndarray:
    """Blank the first `warmup` observed bars of each column — nulls will not save you."""
    if warmup <= 0:
        return out
    return np.where(_valid_count(source) < warmup, np.nan, out)


# ------------------------------------------------------------------------------- indicators


def sma(a: np.ndarray, window: int, min_samples: int | None = None) -> np.ndarray:
    """Simple moving average over `window` bars, requiring `min_samples` real observations."""
    m = window if min_samples is None else min_samples
    return _apply(a, lambda c: pl.col(c).rolling_mean(window, min_samples=m))


def ema(a: np.ndarray, span: int, warmup: int | None = None) -> np.ndarray:
    """Exponential moving average. Warm-up defaults to `span * 3` bars per symbol."""
    out = _apply(a, lambda c: pl.col(c).ewm_mean(span=span, adjust=False, ignore_nulls=True))
    return _mask_warmup(out, a, span * 3 if warmup is None else warmup)


def rsi(a: np.ndarray, period: int = 14, warmup: int | None = None) -> np.ndarray:
    """Wilder's RSI, column-wise, via the validated `screener.rsi` expression."""
    out = _apply(a, lambda c: _rsi_expr(c, period))
    return _mask_warmup(out, a, period * 3 if warmup is None else warmup)


def rolling_max(a: np.ndarray, window: int, min_samples: int | None = None) -> np.ndarray:
    m = window if min_samples is None else min_samples
    return _apply(a, lambda c: pl.col(c).rolling_max(window, min_samples=m))


def rolling_min(a: np.ndarray, window: int, min_samples: int | None = None) -> np.ndarray:
    m = window if min_samples is None else min_samples
    return _apply(a, lambda c: pl.col(c).rolling_min(window, min_samples=m))


def rolling_std(a: np.ndarray, window: int, min_samples: int | None = None) -> np.ndarray:
    m = window if min_samples is None else min_samples
    return _apply(a, lambda c: pl.col(c).rolling_std(window, min_samples=m))


def rolling_median(a: np.ndarray, window: int, min_samples: int | None = None) -> np.ndarray:
    m = window if min_samples is None else min_samples
    return _apply(a, lambda c: pl.col(c).rolling_median(window, min_samples=m))


def pct_change(a: np.ndarray, periods: int = 1) -> np.ndarray:
    """Total return over `periods` bars: a[t] / a[t - periods] - 1."""
    if periods < 1:
        raise ValueError("periods must be >= 1")
    out = np.full_like(a, np.nan, dtype=np.float64)
    out[periods:] = a[periods:] / a[:-periods] - 1.0
    return out


def shift(a: np.ndarray, periods: int = 1) -> np.ndarray:
    """Move a matrix `periods` bars into the future, so row `t` reads the value from `t - k`.

    Only forward shifts are allowed. A negative shift would place a future observation on an
    earlier row, which is the exact defect the look-ahead probe exists to catch.
    """
    if periods < 0:
        raise ValueError("shift only moves data forward; a negative shift reads the future")
    if periods == 0:
        return a.copy()
    out = np.full_like(a, np.nan, dtype=np.float64)
    out[periods:] = a[:-periods]
    return out


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14,
        warmup: int | None = None) -> np.ndarray:
    """Average true range, Wilder-smoothed."""
    prev = np.full_like(close, np.nan)
    prev[1:] = close[:-1]
    tr = np.fmax(high - low, np.fmax(np.abs(high - prev), np.abs(low - prev)))
    out = _apply(tr, lambda c: pl.col(c).ewm_mean(alpha=1 / period, adjust=False,
                                                  ignore_nulls=True))
    return _mask_warmup(out, tr, period * 3 if warmup is None else warmup)


def zscore(a: np.ndarray, window: int, min_samples: int | None = None) -> np.ndarray:
    """Distance from the trailing mean in trailing standard deviations."""
    mu = sma(a, window, min_samples)
    sd = rolling_std(a, window, min_samples)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(sd > 0, (a - mu) / sd, np.nan)


# --------------------------------------------------------------------- cross-sectional tools


def cs_rank(a: np.ndarray) -> np.ndarray:
    """Rank each row across symbols into [0, 1]; 1 is the largest value. NaN stays NaN.

    Ranking across the cross-section on a single row reads no other row, so this is causal
    whatever the caller feeds it.
    """
    out = np.full(a.shape, np.nan)
    for t in range(a.shape[0]):
        row = a[t]
        live = np.isfinite(row)
        k = int(live.sum())
        if k > 1:
            out[t, live] = np.argsort(np.argsort(row[live], kind="stable"),
                                      kind="stable") / (k - 1)
        elif k == 1:
            out[t, live] = 0.5
    return out


def top_n(scores: np.ndarray, n: int, eligible: np.ndarray | None = None) -> np.ndarray:
    """Boolean mask of the `n` highest scores in each row, among `eligible` names."""
    s = scores if eligible is None else np.where(eligible, scores, np.nan)
    mask = np.zeros(s.shape, dtype=bool)
    for t in range(s.shape[0]):
        idx = np.flatnonzero(np.isfinite(s[t]))
        if idx.size == 0:
            continue
        take = idx[np.argsort(-s[t][idx], kind="stable")[:min(n, idx.size)]]
        mask[t, take] = True
    return mask


def equal_weight(mask: np.ndarray, slots: int | None = None, gross: float = 1.0) -> np.ndarray:
    """Boolean mask -> equal weights.

    With `slots`, each name gets `gross / slots` and the book holds cash whenever fewer than
    `slots` names qualify. Without it, the row is always fully invested across whatever
    qualified — which quietly concentrates the book into one name on a thin day.
    """
    held = mask.sum(axis=1, keepdims=True)
    divisor = np.full_like(held, float(slots), dtype=np.float64) if slots else held.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        w = np.where(mask, gross / np.maximum(divisor, 1e-12), 0.0)
    return np.where(held > 0, w, 0.0)


def hold_until_rebalance(target: np.ndarray, mark: np.ndarray, every: int,
                         offset: int = 0) -> np.ndarray:
    """Take the target book only every `every`-th session; let it drift in between.

    Re-stating the same equal weights every day looks free and is not: the book has drifted
    since yesterday, so the harness charges turnover for pushing it back. This carries the
    positions instead, growing and shrinking with their prices, which is what actually happens
    to a portfolio nobody touches. Turnover then falls to what the rebalance really costs.

    The rebalance calendar is anchored to the *start* of the panel, never the end, so removing
    future bars cannot move it — the look-ahead probe checks exactly this.
    """
    if every < 1:
        raise ValueError("every must be >= 1")
    r = np.zeros_like(mark)
    with np.errstate(invalid="ignore", divide="ignore"):
        r[1:] = mark[1:] / mark[:-1] - 1.0
    r = np.where(np.isfinite(r), r, 0.0)

    out = np.zeros_like(target)
    current = np.zeros(target.shape[1])
    for t in range(target.shape[0]):
        if t and current.any():
            g = float(current @ r[t])
            if 1.0 + g > 0.0:
                current = current * (1.0 + r[t]) / (1.0 + g)
        if (t - offset) % every == 0:
            current = np.nan_to_num(target[t], nan=0.0)
        out[t] = current
    return out
