#!/usr/bin/env python3
"""Daily-resolution strategy lab over the committed daily panel.

One simulator, several strategy families, one honest set of numbers per run:

    CAGR        from elapsed calendar time between the first and last equity mark
    max DD      on the DAILY equity curve, not a month-end sample of it
    invested    mean gross exposure, so a part-time book is not mistaken for a full one
    turnover    annual one-way turnover, which is what costs are paid on

Accounting choices, all conservative by design:

    prices      `adj_close` (total return) for signals and P&L; `open` scaled by the same
                adjustment factor for execution. Bad opens (>50% away from the close) fall
                back to the prior close.
    execution   a signal computed at close t is executed at the OPEN of t+1. Nothing is
                filled at the price that generated it.
    costs       `--cost-bps` per unit of one-way turnover (default 30 bps: brokerage, STT,
                impact). Charged on every rebalance and on every exit.
    cash        earns `--cash-rate` (default 0). Borrowed capital, when `--leverage` > 1,
                pays `--funding-rate`.
    bad ticks   a daily return above +100% or below -90% is treated as a data fault and
                zeroed for that name on that day. The count is reported.

Universes:

    liquidN     point-in-time: on every day, the N names with the highest trailing 126-day
                median turnover among those with at least a year of history, a price >=
                --min-price and a median turnover >= --min-turnover (1 crore/day: in 2007
                that admits ~250 names, in 2025 ~1,300). No index-membership lookahead.
                Delisted names are still absent (see AGENTS.md), so survivorship remains —
                but "today's Nifty 500 held in 2010" is gone.
    nifty500    today's constituents (same turnover floor), for comparison with earlier
                work only.

Strategies (`--strategy`):

    ew          equal-weight universe, rebalanced monthly. The benchmark.
    mom         cross-sectional momentum rotation: rank by trailing return (skip the last
                --skip days), hold the top K equal weight, rebalance monthly/weekly.
    breakout    N-day high breakout entries, Chandelier (ATR) or channel exits, K slots,
                daily management.
    pullback    short-term mean reversion inside an uptrend: RSI(2) oversold above the
                200-day average; exit on strength or after --max-hold days.
    breakout_orders
                the breakout book traded with resting stop orders filled intraday (buy-stop at
                the level, sell-stop at the trail), optional pyramiding. See its docstring.

Every strategy can wear the same overlays: a regime filter on the equal-weight index
(`--regime sma200|sma100|dd10|none`), an own-trend filter per name (`--stock-sma`), an
absolute-momentum filter (`--abs-mom`), a daily regime exit (`--daily-exit`), and
volatility targeting on the final return stream (`--vol-target`).

    python scripts/strategy_lab.py --strategy mom --lookback 252 --top 20 --regime sma200
    python scripts/strategy_lab.py --sweep mom            # parameter grid, ranked
    python scripts/strategy_lab.py --strategy breakout --universe nifty500 --start 2015-01-01
"""

from __future__ import annotations

import argparse
import itertools
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY = REPO_ROOT / "data" / "ohlcv" / "daily"
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CACHE = REPO_ROOT / ".cache" / "strategy_lab"

TRADING_DAYS = 250  # only used to annualise volatility, never to annualise return


# ----------------------------------------------------------------------------- data


@dataclass
class Panel:
    dates: np.ndarray            # (T,) datetime64[D]
    symbols: list[str]
    close: np.ndarray            # adjusted close (T, N), forward-filled over gaps
    open_: np.ndarray            # adjusted open, NaN where unusable
    high: np.ndarray             # adjusted high
    low: np.ndarray              # adjusted low
    raw_close: np.ndarray        # unadjusted close, for the price floor
    turnover: np.ndarray         # close * volume, INR
    ret: np.ndarray              # daily close-to-close return, bad ticks zeroed
    has_bar: np.ndarray          # (T, N) bool: the symbol actually traded that day
    bad_ticks: int
    nifty500: np.ndarray         # (N,) bool
    ind: dict = field(default_factory=dict)  # indicator cache

    @property
    def T(self) -> int:
        return len(self.dates)

    @property
    def N(self) -> int:
        return len(self.symbols)


def load_panel(load_start: str) -> Panel:
    t0 = time.time()
    CACHE.mkdir(parents=True, exist_ok=True)
    stamp = max(f.stat().st_mtime for f in DAILY.glob("**/*.parquet"))
    cache = CACHE / f"panel_v2_{load_start}_{int(stamp)}.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        p = Panel(z["dates"], list(z["symbols"]), z["close"], z["open_"], z["high"], z["low"],
                  z["raw_close"], z["turnover"], z["ret"], z["has_bar"], int(z["bad_ticks"]),
                  z["nifty500"])
        print(f"panel: {p.N} symbols x {p.T} days ({p.dates[0]} -> {p.dates[-1]}), "
              f"{p.bad_ticks} bad ticks zeroed, cached, {time.time() - t0:.1f}s", file=sys.stderr)
        return p
    lf = (pl.scan_parquet(str(DAILY / "**" / "*.parquet"), hive_partitioning=True)
          .filter(pl.col("date") >= pl.lit(pd.Timestamp(load_start).date()))
          .select("symbol", "date", "open", "high", "low", "close", "adj_close", "volume"))
    df = lf.collect()
    # adjustment factor: dividend + split. Guard the handful of non-positive adj_close rows.
    df = df.with_columns(
        pl.when((pl.col("adj_close") > 0) & (pl.col("close") > 0))
        .then(pl.col("adj_close") / pl.col("close")).otherwise(None).alias("f"))
    df = df.sort("symbol", "date").with_columns(
        pl.col("f").fill_null(strategy="forward").fill_null(strategy="backward").over("symbol"))
    df = df.with_columns(
        (pl.col("close") * pl.col("f")).alias("ac"),
        pl.when((pl.col("open") > 0) & ((pl.col("open") / pl.col("close") - 1).abs() <= 0.5))
        .then(pl.col("open") * pl.col("f")).otherwise(None).alias("ao"),
        (pl.col("high") * pl.col("f")).alias("ah"),
        (pl.col("low") * pl.col("f")).alias("al"),
        (pl.col("close") * pl.col("volume")).alias("to"),
    )

    symbols = sorted(df["symbol"].unique().to_list())
    dates_all = df["date"].unique().sort().to_numpy().astype("datetime64[D]")
    sym_ix = {s: i for i, s in enumerate(symbols)}
    rows = np.searchsorted(dates_all, df["date"].to_numpy().astype("datetime64[D]"))
    cols = np.array([sym_ix[s] for s in df["symbol"].to_list()])

    def wide(col: str) -> np.ndarray:
        out = np.full((len(dates_all), len(symbols)), np.nan)
        out[rows, cols] = df[col].to_numpy().astype(np.float64)
        return out

    dates = dates_all
    close = wide("ac")
    open_ = wide("ao")
    high = wide("ah")
    low = wide("al")
    raw_close = wide("close")
    turnover = wide("to")

    # Drop phantom sessions: a handful of Saturdays carry a bar for 3 symbols and nothing
    # else, and a single such row poisons every rolling window for its full length.
    has_bar = np.isfinite(close)
    active = np.isfinite(pd.DataFrame(close).ffill().to_numpy()).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = has_bar.sum(axis=1) / np.maximum(active, 1)
    keep = frac >= 0.5
    dropped = [str(d) for d in dates[~keep]]
    dates, close, open_, high, low, raw_close, turnover, has_bar = (
        x[keep] for x in (dates, close, open_, high, low, raw_close, turnover, has_bar))

    # Indicators run on forward-filled prices, so one missing session for one symbol does
    # not blank its averages for 200 days. Eligibility still requires a bar on the day.
    ffill = pd.DataFrame(close).ffill().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        ret = ffill[1:] / ffill[:-1] - 1
    ret = np.vstack([np.full((1, len(symbols)), np.nan), ret])
    bad = (ret > 1.0) | (ret < -0.9)
    ret[bad] = 0.0
    close = ffill
    high = np.where(np.isnan(high), close, high)
    low = np.where(np.isnan(low), close, low)
    raw_close = pd.DataFrame(raw_close).ffill().to_numpy()

    u = pl.read_parquet(UNIVERSE).select("symbol", "in_nifty500")
    n500 = set(u.filter(pl.col("in_nifty500"))["symbol"].to_list())
    nifty500 = np.array([s in n500 for s in symbols])

    print(f"panel: {len(symbols)} symbols x {len(dates)} days "
          f"({dates[0]} -> {dates[-1]}), {int(bad.sum())} bad ticks zeroed, "
          f"{len(dropped)} phantom sessions dropped ({', '.join(dropped)}), "
          f"{time.time() - t0:.1f}s", file=sys.stderr)
    np.savez(cache, dates=dates, symbols=np.array(symbols), close=close, open_=open_, high=high,
             low=low, raw_close=raw_close, turnover=turnover, ret=ret, has_bar=has_bar,
             bad_ticks=int(bad.sum()), nifty500=nifty500)
    return Panel(dates, symbols, close, open_, high, low, raw_close, turnover, ret, has_bar,
                 int(bad.sum()), nifty500)


# ------------------------------------------------------------------------ indicators


def _pd(a: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(a)


def indicator(p: Panel, name: str, *args) -> np.ndarray:
    """Memoised indicator matrices. All are computed on adjusted prices."""
    key = (name, *args)
    if key in p.ind:
        return p.ind[key]
    px = _pd(p.close)
    if name == "sma":
        v = px.rolling(args[0], min_periods=args[0]).mean().to_numpy()
    elif name == "ret":            # total return from t-lb to t-skip
        lb, skip = args
        v = (px.shift(skip) / px.shift(lb) - 1).to_numpy()
    elif name == "vol":            # annualised std of daily returns
        v = (_pd(p.ret).rolling(args[0], min_periods=args[0] // 2).std()
             .to_numpy() * np.sqrt(TRADING_DAYS))
    elif name == "hh":             # highest high over the previous n bars (excluding today)
        v = _pd(p.high).rolling(args[0], min_periods=args[0]).max().shift(1).to_numpy()
    elif name == "ll":             # lowest low over the previous n bars (excluding today)
        v = _pd(p.low).rolling(args[0], min_periods=args[0]).min().shift(1).to_numpy()
    elif name == "atr":
        c1 = px.shift(1)
        tr = pd.concat([_pd(p.high) - _pd(p.low), (_pd(p.high) - c1).abs(),
                        (_pd(p.low) - c1).abs()]).groupby(level=0).max()
        v = tr.rolling(args[0], min_periods=args[0]).mean().to_numpy()
    elif name == "rsi":
        n = args[0]
        d = px.diff()
        up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n * 5).mean()
        dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n * 5).mean()
        v = (100 - 100 / (1 + up / dn)).to_numpy()
    elif name == "bars":           # bars of history so far
        v = p.has_bar.cumsum(axis=0).astype(float)
    elif name == "turnover_med":
        v = _pd(p.turnover).rolling(args[0], min_periods=args[0] // 2).median().to_numpy()
    elif name == "turnover_mean":
        v = _pd(p.turnover).rolling(args[0], min_periods=args[0] // 2).mean().to_numpy()
    elif name == "range":          # (n-day high - n-day low) / close, a base-tightness measure
        hi = _pd(p.high).rolling(args[0], min_periods=args[0]).max()
        lo = _pd(p.low).rolling(args[0], min_periods=args[0]).min()
        v = ((hi - lo) / px).to_numpy()
    elif name == "hh_incl":        # highest high over the last n bars including today
        v = _pd(p.high).rolling(args[0], min_periods=args[0]).max().to_numpy()
    elif name == "clv":            # close within the day's range: 0 low .. 1 high
        rng = p.high - p.low
        with np.errstate(invalid="ignore", divide="ignore"):
            v = np.where(rng > 0, (p.close - p.low) / rng, 0.0)   # a locked bar is not a strong close
    else:
        raise KeyError(name)
    p.ind[key] = v
    return v


# -------------------------------------------------------------------------- universe


def eligibility(p: Panel, universe: str, min_price: float, min_bars: int,
                min_turnover: float = 1e7) -> np.ndarray:
    """(T, N) bool: may this name be bought at the close of day t?"""
    ok = (p.has_bar & (p.raw_close >= min_price) & (indicator(p, "bars") >= min_bars)
          & (indicator(p, "turnover_med", 126) >= min_turnover))
    if universe == "nifty500":
        return ok & p.nifty500[None, :]
    if universe.startswith("liquid"):
        n = int(universe[len("liquid"):])
        tmed = np.where(ok, indicator(p, "turnover_med", 126), np.nan)
        # rank each day's turnover descending; keep the top n
        order = np.argsort(-np.nan_to_num(tmed, nan=-1.0), axis=1)
        rank = np.empty_like(order)
        rows = np.arange(p.T)[:, None]
        rank[rows, order] = np.arange(p.N)[None, :]
        return ok & ~np.isnan(tmed) & (rank < n)
    if universe == "nse_all":
        return ok
    raise ValueError(universe)


def ew_index(p: Panel, elig: np.ndarray) -> np.ndarray:
    """Equal-weight total-return index of the eligible names (membership lagged a day)."""
    m = np.vstack([np.zeros((1, p.N), bool), elig[:-1]])
    r = np.where(m & ~np.isnan(p.ret), p.ret, 0.0)
    cnt = (m & ~np.isnan(p.ret)).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        daily = np.where(cnt > 0, r.sum(axis=1) / np.maximum(cnt, 1), 0.0)
    return np.cumprod(1 + daily)


def regime_on(p: Panel, idx: np.ndarray, rule: str, elig: np.ndarray | None = None) -> np.ndarray:
    """Rules joined with '+' must all hold: e.g. sma200+breadth40."""
    if "+" in rule:
        out = np.ones(p.T, bool)
        for r in rule.split("+"):
            out &= regime_on(p, idx, r, elig)
        return out
    s = pd.Series(idx)
    if rule == "none":
        return np.ones(p.T, bool)
    if rule.startswith("sma"):
        n = int(rule[3:])
        return (s > s.rolling(n, min_periods=n).mean()).to_numpy()
    if rule.startswith("dd"):       # index within x% of its trailing 1-year high
        x = float(rule[2:]) / 100
        return (s / s.rolling(252, min_periods=60).max() > 1 - x).to_numpy()
    if rule.startswith("cross"):    # fast SMA above slow SMA, e.g. cross50_200
        a, b = (int(v) for v in rule[5:].split("_"))
        return (s.rolling(a).mean() > s.rolling(b).mean()).to_numpy()
    if rule.startswith("breadth"):  # share of eligible names above their own 200-day average
        x = float(rule[7:]) / 100
        above = (p.close > indicator(p, "sma", 200)) & elig
        with np.errstate(invalid="ignore", divide="ignore"):
            frac = above.sum(axis=1) / np.maximum(elig.sum(axis=1), 1)
        return frac > x
    if rule.startswith("rising"):   # index 200-day average rising over the last n days
        n = int(rule[6:])
        ma = s.rolling(200, min_periods=200).mean()
        return (ma > ma.shift(n)).to_numpy()
    raise ValueError(rule)


def rebalance_days(p: Panel, freq: str) -> np.ndarray:
    d = pd.DatetimeIndex(p.dates)
    if freq == "daily":
        return np.ones(p.T, bool)
    key = d.to_period("M" if freq == "monthly" else "W")
    last = pd.Series(np.arange(p.T)).groupby(key.astype(str)).max().to_numpy()
    m = np.zeros(p.T, bool)
    m[last] = True
    return m


# ------------------------------------------------------------------------- simulator


@dataclass
class Result:
    equity: np.ndarray
    gross: np.ndarray
    turnover: np.ndarray
    dates: np.ndarray

    def metrics(self) -> dict:
        eq = self.equity
        years = (self.dates[-1] - self.dates[0]).astype("timedelta64[D]").astype(int) / 365.25
        cagr = eq[-1] ** (1 / years) - 1
        dd = eq / np.maximum.accumulate(eq) - 1
        r = np.diff(eq) / eq[:-1]
        vol = r.std() * np.sqrt(TRADING_DAYS)
        yr = pd.Series(eq, index=pd.DatetimeIndex(self.dates)).resample("YE").last()
        yr = (yr / yr.shift(1).fillna(1.0) - 1)
        return {
            "cagr": cagr, "max_dd": dd.min(), "calmar": abs(cagr / dd.min()) if dd.min() else np.nan,
            "vol": vol, "sharpe": (r.mean() / r.std() * np.sqrt(TRADING_DAYS)) if r.std() else np.nan,
            "invested": self.gross.mean(), "turnover": self.turnover.sum() / years,
            "years": years, "worst_year": yr.min(), "yearly": yr,
            "dd_series": dd, "final": eq[-1],
        }


def simulate(p: Panel, W: np.ndarray, start_i: int, cost_bps: float, cash_rate: float,
             funding_rate: float, gross_cap: float) -> Result:
    """W[t] = target weights decided at the close of day t (NaN = keep what is held).

    Executed at the open of t+1. Between rebalances positions drift with price.
    """
    T, N = W.shape
    cost = cost_bps / 10_000
    w = np.zeros(N)
    eq = 1.0
    equity = np.empty(T - start_i)
    gross = np.empty(T - start_i)
    turn = np.zeros(T - start_i)
    equity[0] = 1.0
    gross[0] = 0.0
    open_ok = ~np.isnan(p.open_)
    pending = np.zeros(N, bool)          # sells waiting for a bar that actually trades
    for t in range(start_i + 1, T):
        k = t - start_i
        # split the day into an overnight leg (prior close -> open) and an intraday leg
        c_prev = p.close[t - 1]
        with np.errstate(invalid="ignore", divide="ignore"):
            r_on = np.where(open_ok[t], p.open_[t] / c_prev - 1, 0.0)
            r_id = np.where(open_ok[t], p.close[t] / p.open_[t] - 1, p.ret[t])
        r_on = np.where(np.isnan(r_on) | np.isnan(p.ret[t]), 0.0, r_on)
        r_id = np.where(np.isnan(r_id) | np.isnan(p.ret[t]), 0.0, r_id)
        # bad-tick guard applies to the full day: if the day's return was zeroed, zero both legs
        zeroed = (p.ret[t] == 0.0) & (c_prev != p.close[t])
        r_on[zeroed] = 0.0
        r_id[zeroed] = 0.0

        # carry / funding on yesterday's book
        g = w.sum()
        eq *= 1 + cash_rate / TRADING_DAYS * max(1 - g, 0.0) - funding_rate / TRADING_DAYS * max(g - 1, 0.0)

        rp = w @ r_on
        eq *= 1 + rp
        w = w * (1 + r_on) / (1 + rp)

        tgt = W[t - 1].copy()
        # a bar with no range is a circuit lock: nothing can be bought at that open, and a
        # sell there fills only in the model. Drop buys; carry sells to the next bar with range.
        locked = (p.high[t] == p.low[t]) & ~np.isnan(p.close[t])
        if pending.any():
            tgt[pending & ~locked] = 0.0
            pending &= locked
        sells = ~np.isnan(tgt) & (tgt < w) & locked
        buys_locked = ~np.isnan(tgt) & (tgt > w) & locked
        pending |= sells
        tgt[sells | buys_locked] = np.nan
        m = ~np.isnan(tgt)
        if m.any():
            new = w.copy()
            new[m] = tgt[m]
            excess = new.sum() - gross_cap
            if excess > 1e-12:
                buys = m & (new > w)
                amt = (new - w)[buys].sum()
                if amt > 0:
                    new[buys] = w[buys] + (new - w)[buys] * max(1 - excess / amt, 0.0)
            to = np.abs(new - w).sum()
            eq *= 1 - cost * to
            turn[k] = to / 2
            w = new

        rp = w @ r_id
        eq *= 1 + rp
        w = w * (1 + r_id) / (1 + rp)
        equity[k] = eq
        gross[k] = w.sum()
    return Result(equity, gross, turn, p.dates[start_i:])


def _rescale(res: Result, m: np.ndarray, cost_bps: float, funding_rate: float) -> Result:
    """Apply a daily exposure multiplier m (decided with information up to the prior close)
    to the strategy's return stream, charging turnover on every change in m."""
    r = np.diff(res.equity) / res.equity[:-1]
    g = res.gross[:-1]
    switch = np.abs(np.diff(np.concatenate([[1.0], m]))) * g
    r2 = (m * r - np.maximum(m * g - 1, 0) * funding_rate / TRADING_DAYS
          - switch * cost_bps / 10_000)
    eq = np.concatenate([[1.0], np.cumprod(1 + r2)])
    return Result(eq, res.gross * np.concatenate([[1.0], m]),
                  res.turnover + np.concatenate([[0.0], switch / 2]), res.dates)


def vol_target(res: Result, target: float, window: int, cap: float, funding_rate: float,
               cost_bps: float) -> Result:
    """Scale the daily return stream to a target volatility using trailing realised vol."""
    r = np.diff(res.equity) / res.equity[:-1]
    rv = pd.Series(r).rolling(window, min_periods=window // 2).std().to_numpy() * np.sqrt(TRADING_DAYS)
    m = np.clip(target / np.where(rv > 0, rv, np.nan), 0.0, cap)
    m = np.nan_to_num(np.roll(m, 1), nan=1.0)   # yesterday's vol decides today's exposure
    m[0] = 1.0
    return _rescale(res, m, cost_bps, funding_rate)


def equity_curve_filter(res: Result, window: int, scale: float, cost_bps: float,
                        band: float = 0.0, boost: float = 1.0, dd_stop: float = 0.0,
                        funding_rate: float = 0.0, hedge: float = 0.0,
                        hedge_ret: np.ndarray | None = None) -> Result:
    """Run at `scale` exposure while the strategy's own equity sits below its moving average
    (or, with `dd_stop`, more than that far below its running peak), and at `boost` otherwise.

    `band` adds hysteresis: cut once equity is `band` below the average, restore only once
    it is `band` above. Without it the filter flips every few days while equity hugs the
    average, and each flip costs turnover. All states are read off the UNSCALED curve, so
    the filter cannot trap itself flat.
    """
    eq = res.equity
    ma = pd.Series(eq).rolling(window, min_periods=window).mean().to_numpy()
    peak = np.maximum.accumulate(eq)
    cut = np.zeros(len(eq), bool)
    state = False
    for i in range(len(eq)):
        if np.isnan(ma[i]):
            continue
        if not state and (eq[i] < ma[i] * (1 - band) or (dd_stop and eq[i] < peak[i] * (1 - dd_stop))):
            state = True
        elif state and eq[i] > ma[i] * (1 + band):
            state = False
        cut[i] = state
    m = np.where(cut[:-1], scale, boost)     # yesterday's state decides today's exposure
    out = _rescale(res, m, cost_bps, funding_rate)
    if hedge and hedge_ret is not None:
        # short `hedge` x gross of the large-cap index (Nifty futures in practice) while cut
        g = res.gross[:-1] * m
        h = np.where(cut[:-1], hedge * g, 0.0)
        r = np.diff(out.equity) / out.equity[:-1]
        switch = np.abs(np.diff(np.concatenate([[0.0], h])))
        r2 = r - h * hedge_ret[1:] - switch * 5 / 10_000
        eq = np.concatenate([[1.0], np.cumprod(1 + r2)])
        out = Result(eq, out.gross, out.turnover, out.dates)
    return out


def dd_budget_filter(res: Result, start: float, budget: float, floor: float,
                     cost_bps: float) -> Result:
    """Scale exposure by the managed curve's own drawdown: 1.0 until the drawdown reaches
    `start`, then linearly down to `floor` as it approaches `budget`, and back up as it
    heals. No leverage: the multiplier never exceeds 1. Steps of 0.05 keep churn down."""
    r = np.diff(res.equity) / res.equity[:-1]
    g = res.gross[:-1]
    n = len(r)
    m = np.ones(n)
    eq = 1.0
    peak = 1.0
    prev = 1.0
    out = np.empty(n + 1)
    out[0] = 1.0
    for i in range(n):
        dd = 1 - eq / peak
        raw = 1.0 - max(0.0, dd - start) / max(budget - start, 1e-9)
        mi = float(np.clip(np.round(raw / 0.05) * 0.05, floor, 1.0))
        m[i] = mi
        eq *= 1 + mi * r[i] - abs(mi - prev) * g[i] * cost_bps / 10_000
        prev = mi
        peak = max(peak, eq)
        out[i + 1] = eq
    switch = np.abs(np.diff(np.concatenate([[1.0], m]))) * g
    return Result(out, res.gross * np.concatenate([[1.0], m]),
                  res.turnover + np.concatenate([[0.0], switch / 2]), res.dates)


# ------------------------------------------------------------------------ strategies


def top_k(scores: np.ndarray, k: int) -> np.ndarray:
    """Indices of the k largest finite scores."""
    ok = np.isfinite(scores)
    n = min(k, int(ok.sum()))
    if n == 0:
        return np.array([], dtype=int)
    return np.argsort(-np.where(ok, scores, -np.inf))[:n]


def strat_ew(p: Panel, a, elig, regime) -> np.ndarray:
    W = np.full((p.T, p.N), np.nan)
    for t in np.flatnonzero(rebalance_days(p, "monthly")):
        m = elig[t]
        W[t] = 0.0
        if m.any():
            W[t, m] = 1.0 / m.sum()
    return W


def _filters(p: Panel, a, elig: np.ndarray, t: int, scores: np.ndarray) -> np.ndarray:
    s = np.where(elig[t], scores, np.nan)
    if a.stock_sma:
        s[~(p.close[t] > indicator(p, "sma", a.stock_sma)[t])] = np.nan
    if a.abs_mom:
        s[~(indicator(p, "ret", a.lookback, a.skip)[t] > 0)] = np.nan
    if a.max_vol:
        s[~(indicator(p, "vol", 63)[t] < a.max_vol)] = np.nan
    return s


def strat_mom(p: Panel, a, elig, regime) -> np.ndarray:
    W = np.full((p.T, p.N), np.nan)
    mom = indicator(p, "ret", a.lookback, a.skip)
    if a.rank == "sharpe":
        # floor the vol so a name pinned at an upper circuit (tiny vol) cannot top the list
        score_all = mom / np.maximum(indicator(p, "vol", 63), 0.10)
    elif a.rank == "mom2":       # blend of 12-1 and 6-1
        score_all = 0.5 * mom + 0.5 * indicator(p, "ret", a.lookback // 2, a.skip)
    else:
        score_all = mom
    reb = rebalance_days(p, a.rebalance)
    held = np.zeros(p.N, bool)
    for t in range(p.T):
        if reb[t]:
            W[t] = 0.0
            held[:] = False
            if regime[t]:
                s = _filters(p, a, elig, t, score_all[t])
                pick = top_k(s, a.top)
                if len(pick) >= max(a.top // 3, 2):
                    if a.weighting == "invvol":
                        iv = 1 / np.maximum(indicator(p, "vol", 63)[t, pick], 0.05)
                        W[t, pick] = iv / iv.sum() * a.exposure
                    else:
                        W[t, pick] = a.exposure / len(pick)
                    held[pick] = True
        elif a.daily_exit and held.any():
            out = np.zeros(p.N, bool)
            if not regime[t]:
                out = held.copy()
            if a.stock_sma and a.daily_exit == "stock":
                out |= held & ~(p.close[t] > indicator(p, "sma", a.stock_sma)[t])
            if a.stop:
                out |= held & (indicator(p, "ret", a.stop_window, 0)[t] < -a.stop)
            if out.any():
                W[t, out] = 0.0
                held[out] = False
    return W


def strat_breakout(p: Panel, a, elig, regime) -> np.ndarray:
    W = np.full((p.T, p.N), np.nan)
    t0 = getattr(a, "_start_i", 0)
    hh = indicator(p, "hh", a.entry_n)
    ll = indicator(p, "ll", a.exit_n) if a.exit_n else None
    atr = indicator(p, "atr", 20)
    mom = indicator(p, "ret", a.lookback, a.skip)
    vol = indicator(p, "vol", 63)
    held = np.zeros(p.N, bool)
    peak = np.full(p.N, np.nan)
    entry = np.full(p.N, np.nan)
    init_stop = np.full(p.N, np.nan)
    age = np.zeros(p.N, int)
    weekly = rebalance_days(p, "weekly") if a.exit_weekly else np.ones(p.T, bool)
    if a.late_entry:
        # a qualifying breakout bar (regime and slots aside); late entries may take it for
        # --late-entry days afterwards while the close still sits at or above that bar's close
        sig = (p.close >= hh) & ~np.isnan(hh) & (p.high > p.low)
        if a.clv:
            sig &= indicator(p, "clv") >= a.clv
    if a.turnover_trend:
        to_trend = indicator(p, "turnover_mean", 50) / indicator(p, "turnover_mean", 200)
    if a.vol_surge:
        surge = p.turnover / indicator(p, "turnover_mean", 50)
    if a.base_tight:
        tight = indicator(p, "range", 20)
    if a.near_high:
        near = p.close / indicator(p, "hh_incl", 252)
    if a.rank == "rs":
        # relative strength: the name's 6-month return minus the universe's
        rs6 = indicator(p, "ret", 126, 0)
        idx_ret = np.nanmedian(np.where(elig, rs6, np.nan), axis=1)
        mom = rs6 - idx_ret[:, None]
    for t in range(t0, p.T):
        c = p.close[t]
        if held.any():
            age[held] += 1
            peak[held] = np.fmax(peak[held], c[held])
            stop = peak - a.atr_mult * atr[t]
            if a.init_atr:
                stop = np.fmax(stop, init_stop)      # tighter stop until the trade has moved
            out = held & ~np.isnan(c) & (c < stop) & weekly[t]
            if ll is not None:
                out |= held & ~np.isnan(c) & (c < ll[t])
            if a.time_stop:
                out |= held & (age >= a.time_stop) & (c < entry)
            if a.stock_sma:
                out |= held & ~(c > indicator(p, "sma", a.stock_sma)[t])
            if not regime[t] and a.daily_exit:
                if a.keep_winners:
                    # a position with this much cushion keeps its trail through a regime exit
                    out |= held & ~(c / entry - 1 >= a.keep_winners)
                else:
                    out |= held
            if out.any():
                W[t, out] = 0.0
                held[out] = False
        free = a.top - held.sum()
        if free > 0 and regime[t]:
            cand = elig[t] & ~held & (c >= hh[t]) & ~np.isnan(hh[t]) & (p.high[t] > p.low[t])
            if a.late_entry and t > a.late_entry:
                k = a.late_entry
                recent = (sig[t - k:t] & (c[None, :] >= p.close[t - k:t])).any(axis=0)
                late = elig[t] & ~held & recent
                if a.clv:
                    late &= p.high[t] > p.low[t]
                cand_late = late & ~cand
            else:
                cand_late = np.zeros(p.N, bool)
            if a.turnover_trend:
                cand &= to_trend[t] >= a.turnover_trend
                cand_late &= to_trend[t] >= a.turnover_trend
            if a.stock_sma:
                cand &= c > indicator(p, "sma", a.stock_sma)[t]
            if a.max_vol:
                cand &= vol[t] < a.max_vol
            if a.clv:
                cand &= indicator(p, "clv")[t] >= a.clv
            if a.vol_surge:
                cand &= surge[t] >= a.vol_surge
            if a.base_tight:
                cand &= tight[t] <= a.base_tight
            if a.near_high:
                cand &= near[t] >= a.near_high
            if a.late_entry:
                if a.stock_sma:
                    cand_late &= c > indicator(p, "sma", a.stock_sma)[t]
                cand |= cand_late
            if cand.any():
                s = np.where(cand, mom[t] if a.rank != "sharpe" else mom[t] / np.maximum(vol[t], 0.10), np.nan)
                if a.clv_first:
                    # two tiers: strong-close breakouts rank ahead of ordinary ones
                    s = s + np.where(indicator(p, "clv")[t] >= a.clv_first, 1e3, 0.0)
                pick = top_k(s, free)
                if len(pick):
                    if a.weighting == "risk":
                        # size so that atr_mult ATRs of adverse move costs --risk of equity
                        risk_frac = a.atr_mult * atr[t, pick] / c[pick]
                        W[t, pick] = np.minimum(a.risk / np.maximum(risk_frac, 1e-6), a.exposure / a.top * 2)
                    else:
                        W[t, pick] = a.exposure / a.top
                    held[pick] = True
                    peak[pick] = c[pick]
                    entry[pick] = c[pick]
                    init_stop[pick] = c[pick] - a.init_atr * atr[t, pick]
                    age[pick] = 0
    return W


def strat_pullback(p: Panel, a, elig, regime) -> np.ndarray:
    W = np.full((p.T, p.N), np.nan)
    rsi = indicator(p, "rsi", 2)
    sma_l = indicator(p, "sma", a.stock_sma or 200)
    sma_x = indicator(p, "sma", a.exit_n or 5)
    mom = indicator(p, "ret", a.lookback, a.skip)
    held = np.zeros(p.N, bool)
    age = np.zeros(p.N, int)
    for t in range(p.T):
        c = p.close[t]
        if held.any():
            age[held] += 1
            out = held & ((c > sma_x[t]) | (age > a.max_hold) | (c < sma_l[t] * (1 - a.stop)))
            if not regime[t] and a.daily_exit:
                out |= held
            if out.any():
                W[t, out] = 0.0
                held[out] = False
        free = a.top - held.sum()
        if free > 0 and regime[t]:
            cand = elig[t] & ~held & (rsi[t] < a.rsi_entry) & (c > sma_l[t])
            if a.abs_mom:
                cand &= mom[t] > 0
            if cand.any():
                pick = top_k(np.where(cand, mom[t], np.nan), free)
                W[t, pick] = a.exposure / a.top
                held[pick] = True
                age[pick] = 0
    return W


def simulate_breakout_orders(p: Panel, a, elig: np.ndarray, regime: np.ndarray, start_i: int,
                             end_i: int) -> Result:
    """Breakout trend following traded with STOP ORDERS instead of next-open market orders.

    At the close of t-1 the book knows: its trailing stops (peak close minus --atr-mult ATRs,
    held at the entry stop while --init-atr is set and the trade has not moved), and a list of
    buy-stop orders at the prior --entry-n-day high for the best-ranked eligible names that
    closed within --order-band of that level. On day t:

        sell stop   open <= stop -> fill at open (gap through); low <= stop -> fill at the
                    stop less --slip-bps. Regime and own-trend exits are market-on-open.
        buy stop    open >= level -> fill at open unless it gapped more than --order-band
                    above the level (skip); high >= level -> fill at the level plus slip.
        pyramid     with --pyramid-units > 1 each entry buys one unit; a further unit is
                    bought at the next open each time the close is --pyramid-step ATRs above
                    the last fill, up to the unit count.

    P&L is per position: a name exited at F earns F/C_prev - 1 for the day, a name entered
    at F earns C/F - 1 on its new weight, holds earn C/C_prev - 1. Costs are --cost-bps on
    the value traded. No leverage: gross is capped at --leverage (1.0).
    """
    T = end_i
    cost = a.cost_bps / 10_000
    slip = a.slip_bps / 10_000
    hh = indicator(p, "hh", a.entry_n)
    atr = indicator(p, "atr", 20)
    mom = indicator(p, "ret", a.lookback, a.skip)
    if a.rank == "mom2":
        score_all = 0.5 * mom + 0.5 * indicator(p, "ret", a.lookback // 2, a.skip)
    elif a.rank == "sharpe":
        score_all = mom / np.maximum(indicator(p, "vol", 63), 0.10)
    else:
        score_all = mom
    sma_s = indicator(p, "sma", a.stock_sma) if a.stock_sma else None
    vol = indicator(p, "vol", 63) if a.max_vol else None
    unit_w = a.exposure / a.top / max(a.pyramid_units, 1)

    N = p.N
    w = np.zeros(N)
    held = np.zeros(N, bool)
    peak = np.full(N, np.nan)
    stop = np.full(N, np.nan)
    last_fill = np.full(N, np.nan)
    units = np.zeros(N, int)
    eq = 1.0
    equity = np.empty(T - start_i)
    gross = np.empty(T - start_i)
    turn = np.zeros(T - start_i)
    equity[0] = 1.0
    gross[0] = 0.0
    for t in range(start_i + 1, T):
        k = t - start_i
        c_prev = p.close[t - 1]
        o = np.where(np.isnan(p.open_[t]), c_prev, p.open_[t])
        hi = p.high[t]
        lo = p.low[t]
        c = p.close[t]
        tradable = p.has_bar[t] & ~np.isnan(c_prev)
        bad = (p.ret[t] == 0.0) & (c_prev != c)        # bad tick: freeze the name for the day
        day_ret = 0.0
        traded = 0.0
        new_w = w.copy()

        # ---- exits, decided on yesterday's close or triggered intraday today
        if held.any():
            idx = np.flatnonzero(held)
            for i in idx:
                if bad[i] or not tradable[i]:
                    continue
                fill = np.nan
                if (not regime[t - 1] and a.daily_exit) or (sma_s is not None and not c_prev[i] > sma_s[t - 1, i]):
                    fill = o[i]
                elif a.exit_mode == "close":
                    if c_prev[i] < stop[i]:
                        fill = o[i]
                elif o[i] <= stop[i]:
                    fill = o[i]
                elif lo[i] <= stop[i]:
                    fill = stop[i] * (1 - slip)
                if not np.isnan(fill):
                    r = fill / c_prev[i] - 1
                    day_ret += w[i] * r
                    traded += w[i] * (1 + r)
                    new_w[i] = 0.0
                    held[i] = False
                    units[i] = 0
        # holds earn the full day
        hold_mask = held & tradable & ~bad
        r_hold = np.where(hold_mask, c / c_prev - 1, 0.0)
        day_ret += float(w @ np.nan_to_num(r_hold))
        # ---- pyramids: add a unit at the open when yesterday's close cleared the step
        if a.pyramid_units > 1 and held.any():
            for i in np.flatnonzero(held & tradable & ~bad):
                if units[i] < a.pyramid_units and c_prev[i] >= last_fill[i] + a.pyramid_step * atr[t - 1, i]:
                    if new_w.sum() + unit_w <= a.leverage + 1e-9:
                        day_ret += unit_w * (c[i] / o[i] - 1)
                        traded += unit_w
                        new_w[i] += unit_w
                        units[i] += 1
                        last_fill[i] = o[i]
        # ---- entries via buy stops
        free = a.top - int(held.sum())
        if free > 0 and regime[t - 1]:
            lvl = hh[t]
            if a.entry_mode == "close":       # closed above the prior high: buy at the open
                prior = hh[t - 1]
                cand = (elig[t - 1] & ~held & tradable & ~bad & ~np.isnan(prior) & (c_prev >= prior)
                        & (p.high[t - 1] > p.low[t - 1]))
                if a.clv:
                    cand &= indicator(p, "clv")[t - 1] >= a.clv
            else:                             # buy stop resting at the level
                cand = (elig[t - 1] & ~held & tradable & ~bad & ~np.isnan(lvl)
                        & (c_prev >= lvl * (1 - a.order_band)) & (c_prev < lvl))
            if sma_s is not None:
                cand &= c_prev > sma_s[t - 1]
            if vol is not None:
                cand &= vol[t - 1] < a.max_vol
            if cand.any():
                order = np.argsort(-np.where(cand, np.nan_to_num(score_all[t - 1], nan=-1e9), -np.inf))
                for j in order[:cand.sum()]:
                    if free == 0:
                        break
                    fill = np.nan
                    if hi[j] == lo[j]:                # locked all day: nothing to buy
                        continue
                    if a.entry_mode == "close":
                        fill = o[j]
                    elif o[j] >= lvl[j]:
                        if o[j] <= lvl[j] * (1 + a.order_band):
                            fill = o[j]
                    elif hi[j] >= lvl[j]:
                        fill = lvl[j] * (1 + slip)
                    if np.isnan(fill) or new_w.sum() + unit_w > a.leverage + 1e-9:
                        continue
                    day_ret += unit_w * (c[j] / fill - 1)
                    traded += unit_w
                    new_w[j] = unit_w
                    held[j] = True
                    units[j] = 1
                    last_fill[j] = fill
                    peak[j] = c[j]
                    stop[j] = fill - (a.init_atr or a.atr_mult) * atr[t - 1, j]
                    free -= 1
        # ---- carry and bookkeeping
        g_prev = w.sum()
        eq *= 1 + a.cash_rate / TRADING_DAYS * max(1 - g_prev, 0.0)
        eq *= (1 + day_ret) * (1 - cost * traded)
        # weights as fractions of the new equity: each name's end-of-day value / equity
        val = np.zeros(N)
        hm = held & (new_w > 0)
        entered = hm & (units == 1) & (last_fill == last_fill) & np.isnan(peak) == False
        # value of holds and adds: weight * C/C_prev for carried units, unit * C/fill for new
        val[hm] = new_w[hm]
        # approximate: carried units scale by C/C_prev, new fills by C/fill — recompute exactly
        for i in np.flatnonzero(hm):
            if w[i] > 0 and new_w[i] > w[i]:            # carried plus an added unit at the open
                val[i] = w[i] * (c[i] / c_prev[i]) + (new_w[i] - w[i]) * (c[i] / o[i])
            elif w[i] > 0:
                val[i] = w[i] * (c[i] / c_prev[i]) if (tradable[i] and not bad[i]) else w[i]
            else:
                val[i] = new_w[i] * (c[i] / last_fill[i])
        w = val / (1 + day_ret)
        # trailing stops for tomorrow
        for i in np.flatnonzero(held):
            if tradable[i] and not bad[i]:
                peak[i] = max(peak[i], c[i]) if not np.isnan(peak[i]) else c[i]
                trail = peak[i] - a.atr_mult * atr[t, i]
                stop[i] = max(stop[i], trail) if a.init_atr else trail
        turn[k] = traded / 2
        equity[k] = eq
        gross[k] = w.sum()
    return Result(equity, gross, turn, p.dates[start_i:T])


STRATEGIES = {"ew": strat_ew, "mom": strat_mom, "breakout": strat_breakout,
              "pullback": strat_pullback, "breakout_orders": None}


# --------------------------------------------------------------------------- driver


def run(p: Panel, a) -> tuple[Result, dict]:
    elig = eligibility(p, a.universe, a.min_price, a.min_bars, a.min_turnover)
    idx = ew_index(p, elig)
    reg = regime_on(p, idx, a.regime, elig)
    start_i = int(np.searchsorted(p.dates, np.datetime64(a.start)))
    a._start_i = start_i
    if a.end:
        end_i = int(np.searchsorted(p.dates, np.datetime64(a.end), side="right"))
    else:
        end_i = p.T
    if a.strategy == "breakout_orders":
        res = simulate_breakout_orders(p, a, elig, reg, start_i, end_i)
    else:
        W = STRATEGIES[a.strategy](p, a, elig, reg)
        q = Panel(p.dates[:end_i], p.symbols, p.close[:end_i], p.open_[:end_i], p.high[:end_i],
                  p.low[:end_i], p.raw_close[:end_i], p.turnover[:end_i], p.ret[:end_i],
                  p.has_bar[:end_i], p.bad_ticks, p.nifty500, p.ind)
        res = simulate(q, W[:end_i], start_i, a.cost_bps, a.cash_rate, a.funding_rate, a.leverage)
    if a.eq_curve:
        hedge_ret = None
        if a.hedge:
            big = ew_index(p, eligibility(p, "liquid200", a.min_price, a.min_bars, a.min_turnover))
            hedge_ret = np.diff(big[start_i:end_i]) / big[start_i:end_i - 1]
            hedge_ret = np.concatenate([[0.0], hedge_ret])
        res = equity_curve_filter(res, a.eq_curve, a.eq_scale, a.cost_bps, a.eq_band,
                                  a.eq_boost, a.dd_stop, a.funding_rate, a.hedge, hedge_ret)
    if a.dd_budget:
        res = dd_budget_filter(res, a.dd_start, a.dd_budget, a.dd_floor, a.cost_bps)
    if a.vol_target:
        res = vol_target(res, a.vol_target, a.vol_window, a.leverage, a.funding_rate, a.cost_bps)
    m = res.metrics()
    # benchmark: the equal-weight index over the same window
    b = idx[start_i:end_i] / idx[start_i]
    m["bench_cagr"] = b[-1] ** (1 / m["years"]) - 1
    m["bench_dd"] = (b / np.maximum.accumulate(b) - 1).min()
    return res, m


def fmt_row(label: str, m: dict) -> str:
    return (f"{label:<58}{m['cagr'] * 100:>8.2f}{m['max_dd'] * 100:>8.2f}{m['calmar']:>7.2f}"
            f"{m['sharpe']:>7.2f}{m['invested'] * 100:>6.0f}%{m['turnover']:>7.1f}"
            f"{m['worst_year'] * 100:>8.1f}")


HEADER = (f"{'strategy':<58}{'CAGR%':>8}{'maxDD%':>8}{'Calmar':>7}{'Sharpe':>7}{'inv':>7}"
          f"{'turn':>7}{'worstY':>8}")


def label(a) -> str:
    bits = [a.strategy, a.universe]
    if a.strategy in ("mom",):
        bits += [f"lb{a.lookback}", f"top{a.top}", a.rebalance, a.rank]
    if a.strategy in ("breakout", "breakout_orders"):
        bits += [f"n{a.entry_n}", f"top{a.top}", f"atr{a.atr_mult:g}", a.weighting]
        if a.pyramid_units > 1:
            bits.append(f"pyr{a.pyramid_units}x{a.pyramid_step:g}")
        if a.strategy == "breakout_orders":
            bits.append(f"in:{a.entry_mode}/out:{a.exit_mode}")
        if a.exit_n:
            bits.append(f"ll{a.exit_n}")
        if a.init_atr:
            bits.append(f"init{a.init_atr:g}")
        if a.vol_surge:
            bits.append(f"vs{a.vol_surge:g}")
        if a.base_tight:
            bits.append(f"bt{a.base_tight:g}")
        if a.near_high:
            bits.append(f"nh{a.near_high:g}")
        if a.exit_weekly:
            bits.append("wkexit")
        if a.clv:
            bits.append(f"clv{a.clv:g}")
        if a.clv_first:
            bits.append(f"clv1st{a.clv_first:g}")
        if a.late_entry:
            bits.append(f"late{a.late_entry}")
        if a.keep_winners:
            bits.append(f"keep{a.keep_winners:g}")
        if a.turnover_trend:
            bits.append(f"tot{a.turnover_trend:g}")
        bits.append(a.rank)
        if a.time_stop:
            bits.append(f"ts{a.time_stop}")
    if a.strategy == "pullback":
        bits += [f"rsi{a.rsi_entry:g}", f"top{a.top}", f"hold{a.max_hold}"]
    if a.regime != "none":
        bits.append(a.regime)
    if a.stock_sma:
        bits.append(f"sma{a.stock_sma}")
    if a.abs_mom:
        bits.append("abs")
    if a.daily_exit:
        bits.append(f"dx:{a.daily_exit}")
    if a.stop:
        bits.append(f"stop{a.stop:g}")
    if a.max_vol:
        bits.append(f"vol<{a.max_vol:g}")
    if a.eq_curve:
        bits.append(f"ec{a.eq_curve}@{a.eq_scale:g}" + (f"±{a.eq_band:g}" if a.eq_band else "")
                    + (f"/{a.eq_boost:g}" if a.eq_boost != 1 else "") + (f" dd{a.dd_stop:g}" if a.dd_stop else "") + (f" hedge{a.hedge:g}" if a.hedge else ""))
    if a.dd_budget:
        bits.append(f"ddb{a.dd_start:g}-{a.dd_budget:g}@{a.dd_floor:g}")
    if a.vol_target:
        bits.append(f"vt{a.vol_target:g}")
    if a.leverage != 1:
        bits.append(f"x{a.leverage:g}")
    return " ".join(bits)


SWEEPS = {
    "mom": dict(lookback=[126, 252], top=[10, 20], rebalance=["monthly"],
                regime=["sma200", "cross50_200", "dd10"], stock_sma=[100, 200],
                abs_mom=[True], daily_exit=["regime"], rank=["sharpe", "mom2"]),
    "breakout": dict(entry_n=[100, 250], top=[10, 15, 20], atr_mult=[3.0, 4.0, 5.0],
                     regime=["sma200", "cross50_200", "sma100"], stock_sma=[200],
                     daily_exit=["regime"], weighting=["equal", "risk"]),
    "pullback": dict(rsi_entry=[5, 10, 20], top=[10, 20], max_hold=[5, 10],
                     regime=["none", "sma200"], abs_mom=[False, True]),
}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strategy", default="mom", choices=list(STRATEGIES))
    ap.add_argument("--sweep", help="run the parameter grid for this strategy instead")
    ap.add_argument("--universe", default="liquid1000")
    ap.add_argument("--start", default="2007-01-01")
    ap.add_argument("--end", default="")
    ap.add_argument("--load-start", default="2004-01-01", help="history loaded for warm-up")
    ap.add_argument("--min-price", type=float, default=10.0)
    ap.add_argument("--min-bars", type=int, default=252)
    ap.add_argument("--min-turnover", type=float, default=1e7,
                    help="floor on trailing 126-day median daily turnover, INR (default 1 crore)")
    ap.add_argument("--cost-bps", type=float, default=30.0)
    ap.add_argument("--cash-rate", type=float, default=0.0)
    ap.add_argument("--funding-rate", type=float, default=0.09)
    ap.add_argument("--leverage", type=float, default=1.0, help="gross exposure cap")
    ap.add_argument("--exposure", type=float, default=1.0, help="target gross when fully invested")
    # overlays
    ap.add_argument("--regime", default="none")
    ap.add_argument("--stock-sma", type=int, default=0)
    ap.add_argument("--abs-mom", action="store_true")
    ap.add_argument("--daily-exit", default="", choices=["", "regime", "stock"])
    ap.add_argument("--stop", type=float, default=0.0, help="exit if the trailing --stop-window return is below -stop")
    ap.add_argument("--stop-window", type=int, default=21)
    ap.add_argument("--max-vol", type=float, default=0.0)
    ap.add_argument("--vol-target", type=float, default=0.0)
    ap.add_argument("--vol-window", type=int, default=20)
    ap.add_argument("--eq-curve", type=int, default=0,
                    help="cut exposure while equity is below its N-day average")
    ap.add_argument("--eq-scale", type=float, default=0.5, help="exposure while cut")
    ap.add_argument("--eq-band", type=float, default=0.0, help="hysteresis band around the average")
    ap.add_argument("--eq-boost", type=float, default=1.0,
                    help="exposure multiplier while NOT cut (>1 borrows at --funding-rate)")
    ap.add_argument("--dd-budget", type=float, default=0.0,
                    help="drawdown at which exposure reaches --dd-floor (0 disables)")
    ap.add_argument("--dd-start", type=float, default=0.10,
                    help="drawdown at which exposure starts shrinking")
    ap.add_argument("--dd-floor", type=float, default=0.25, help="minimum exposure multiplier")
    ap.add_argument("--hedge", type=float, default=0.0,
                    help="while cut, short this fraction of gross in the large-cap index proxy")
    ap.add_argument("--dd-stop", type=float, default=0.0,
                    help="also cut once the strategy's own equity is this far below its peak")
    # momentum
    ap.add_argument("--lookback", type=int, default=252)
    ap.add_argument("--skip", type=int, default=21)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--rebalance", default="monthly", choices=["daily", "weekly", "monthly"])
    ap.add_argument("--rank", default="mom", choices=["mom", "sharpe", "mom2", "rs"])
    ap.add_argument("--weighting", default="equal", choices=["equal", "invvol", "risk"])
    # breakout
    ap.add_argument("--entry-n", type=int, default=100)
    ap.add_argument("--exit-n", type=int, default=0)
    ap.add_argument("--atr-mult", type=float, default=4.0)
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--clv", type=float, default=0.0,
                    help="require the breakout bar to close at least this far up its range (1.0 = at the high)")
    ap.add_argument("--late-entry", type=int, default=0,
                    help="also enter names whose qualifying breakout was within this many days, if still at or above it")
    ap.add_argument("--keep-winners", type=float, default=0.0,
                    help="on a regime exit keep positions with at least this open gain (0 = sell all)")
    ap.add_argument("--turnover-trend", type=float, default=0.0,
                    help="require 50-day mean turnover / 200-day mean turnover >= this")
    ap.add_argument("--clv-first", type=float, default=0.0,
                    help="rank breakouts closing above this CLV ahead of all others (two-tier book)")
    ap.add_argument("--vol-surge", type=float, default=0.0,
                    help="require the breakout day's turnover to be this multiple of its 50-day mean")
    ap.add_argument("--base-tight", type=float, default=0.0,
                    help="require the prior 20-day range / close to be at most this")
    ap.add_argument("--near-high", type=float, default=0.0,
                    help="require close >= this fraction of the 252-day high")
    ap.add_argument("--exit-weekly", action="store_true",
                    help="evaluate trailing-stop exits only on the last day of each week")
    ap.add_argument("--slip-bps", type=float, default=10.0, help="slippage on stop-order fills")
    ap.add_argument("--entry-mode", default="stop", choices=["stop", "close"])
    ap.add_argument("--exit-mode", default="stop", choices=["stop", "close"])
    ap.add_argument("--order-band", type=float, default=0.03,
                    help="place buy stops only on names closing within this of the level; skip gaps beyond it")
    ap.add_argument("--pyramid-units", type=int, default=1)
    ap.add_argument("--pyramid-step", type=float, default=1.0, help="ATRs between pyramid units")
    ap.add_argument("--init-atr", type=float, default=0.0,
                    help="initial stop in ATRs below entry (0 = use --atr-mult)")
    ap.add_argument("--time-stop", type=int, default=0,
                    help="exit a position still under water after this many days")
    # pullback
    ap.add_argument("--rsi-entry", type=float, default=10.0)
    ap.add_argument("--max-hold", type=int, default=10)
    ap.add_argument("--target-cagr", type=float, default=30.0)
    ap.add_argument("--target-dd", type=float, default=25.0)
    ap.add_argument("--yearly", action="store_true", help="print calendar-year returns")
    ap.add_argument("--save", default="", help="write the equity curve to this CSV")
    return ap


def main() -> int:
    a = build_parser().parse_args()

    p = load_panel(a.load_start)
    CACHE.mkdir(parents=True, exist_ok=True)

    if a.sweep:
        a.strategy = a.sweep
        grid = SWEEPS[a.sweep]
        keys = list(grid)
        rows = []
        print(HEADER)
        for combo in itertools.product(*(grid[k] for k in keys)):
            for k, v in zip(keys, combo):
                setattr(a, k, v)
            t0 = time.time()
            res, m = run(p, a)
            row = {k: getattr(a, k) for k in keys}
            row.update({k: (float(v) if isinstance(v, (float, np.floating)) else v)
                        for k, v in m.items() if k not in ("yearly", "dd_series")})
            row["label"] = label(a)
            rows.append(row)
            hit = " <==" if m["cagr"] * 100 >= a.target_cagr and m["max_dd"] * 100 >= -a.target_dd else ""
            print(fmt_row(label(a), m) + hit, flush=True)
        out = pd.DataFrame(rows).sort_values("calmar", ascending=False)
        path = CACHE / f"sweep_{a.sweep}_{a.universe}_{a.start}.csv"
        out.to_csv(path, index=False)
        hits = out[(out.cagr * 100 >= a.target_cagr) & (out.max_dd * 100 >= -a.target_dd)]
        print(f"\n{len(hits)} of {len(out)} meet CAGR >= {a.target_cagr}% and DD <= {a.target_dd}%; "
              f"written {path}")
        print("\ntop by Calmar:")
        print(HEADER)
        for _, r in out.head(15).iterrows():
            print(fmt_row(r["label"], r))
        return 0

    res, m = run(p, a)
    print(HEADER)
    print(fmt_row(label(a), m))
    print(fmt_row(f"benchmark: equal-weight {a.universe}", {
        "cagr": m["bench_cagr"], "max_dd": m["bench_dd"],
        "calmar": abs(m["bench_cagr"] / m["bench_dd"]), "sharpe": np.nan, "invested": 1.0,
        "turnover": np.nan, "worst_year": np.nan}))
    print(f"window {res.dates[0]} -> {res.dates[-1]} ({m['years']:.1f}y), final equity x{m['final']:.1f}, "
          f"annual vol {m['vol'] * 100:.1f}%")
    ok = m["cagr"] * 100 >= a.target_cagr and m["max_dd"] * 100 >= -a.target_dd
    print(f"target CAGR >= {a.target_cagr}% and max DD <= {a.target_dd}%: {'MET' if ok else 'not met'}")
    if a.yearly:
        yr = m["yearly"]
        print("\nyear    return%")
        for d, v in yr.items():
            print(f"{d.year}  {v * 100:>8.1f}")
    if a.save:
        pd.DataFrame({"date": res.dates, "equity": res.equity, "gross": res.gross,
                      "drawdown": m["dd_series"]}).to_csv(a.save, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
