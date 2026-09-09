#!/usr/bin/env python3
"""The loop: an unattended search over the hourly re-ignition strategy family.

Run it and leave it running. Each iteration proposes one complete strategy — entry
level, regime filters, candle filters, stop rule, target, portfolio size — backtests it
on the Kite hourly panel, scores it, and keeps it. Good ones become parents for the next
proposal; the rest are recorded and never proposed again. Stop it with Ctrl-C, restart it
tomorrow, and it resumes from the trials it has already run.

    proposal ── filter the signal superset ── walk exits ── portfolio ── score ── leaderboard
        ^                                                                            |
        └──────────────────── mutate an elite, or draw a fresh one ──────────────────┘

What it searches: a cross of the hourly RSI above a level while the smoothed RSI sits in
a band, under any subset of daily/weekly/monthly RSI regime filters, any subset of
candle-shape, risk-distance, volume, turnover and timing filters, stopped either at the
entry candle's low or an ATR multiple below the close, targeted at a multiple of that
risk, held in an equal-weight book of N slots with an optional per-symbol cap. The exact
size of that space is printed at startup and is somewhere past 10^24, which is the point:
nobody sweeps it by hand, and no run of any length covers a meaningful fraction of it.

Why the leaderboard is not the answer
-------------------------------------
A search this wide over one 11.5-year window is an overfitting machine. Run it long
enough and it *will* return +40% CAGR at a 3.0 return-per-drawdown, because with enough
draws something fits the noise. Four guards, all of them load-bearing:

  * The score comes from the first `--train-frac` of the window only. The rest is a
    holdout the objective never sees, reported beside every leaderboard row so the decay
    is visible rather than discovered later.
  * A candidate is only eligible if it makes money in *both halves of its train window*
    and takes at least `--min-trades` trades — the rule rsi_combo_search.py already used.
  * `--min-deployed` refuses a book that wins by staying in cash. Return per drawdown
    rewards absence: hold nothing and the drawdown is zero, which is not a strategy.
  * Every run ends with a selection audit: the rank correlation between train and holdout
    score across all trials, and whether the top of the leaderboard beats the base rate
    out of sample. If that correlation is near zero, the loop found nothing and the
    leaderboard is a list of coincidences. Read that block before reading the table.

The benchmark for both windows is printed with the table. A configuration that wins the
search and loses to equal-weight buy-and-hold has still lost.

Conventions this inherits from the repo
---------------------------------------
Trades the corporate-action-adjusted Kite hourly panel; seeds the daily, weekly and
monthly RSI from the deep Yahoo daily panel so the regime filters are converged from the
first Kite bar (see LESSONS in AGENTS.md — warm-up truncation once deleted 3.5 years).
Universe is current Nifty 500 membership, so survivorship bias applies and there is no
market-cap filter or network call. Exits come from rsi_backtest.walk_signals and the
portfolio from rsi_backtest.simulate — the same engine every other script here uses.

Widening it
-----------
The space is the `SPACE` table and nothing else — add a knob there and the proposer, the
mutator, the config hash and the ledger pick it up, provided `signal_mask` knows how to
read it and the column it needs is in the superset that `build_panel` writes. A different
*entry family* (a breakout of an N-bar high, say, rather than an RSI cross) is the one
change that is not just a table entry: the superset is defined by the RSI cross between
CROSS_MIN and CROSS_MAX, so a second family needs its own rows in that frame and a
`family` choice for `signal_mask` to branch on.

Usage:
    python scripts/strategy_loop.py --minutes 30
    python scripts/strategy_loop.py --iterations 500 --objective sharpe
    python scripts/strategy_loop.py --report            # leaderboard from stored trials
    python scripts/strategy_loop.py --replay 1          # full report on the leader
    python scripts/strategy_loop.py --self-check        # fast path vs the shared engine
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import signal as signal_mod
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl

from screener import rsi
from hourly_rsi_screener import ema
from rsi_backtest import (attach_htf, elapsed_years, find_trades, performance, simulate,
                          walk_signals)
from rsi_filter_lab import candle_features

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CACHE = REPO_ROOT / ".cache" / "strategy_loop"

# The superset the search is allowed to draw from. Every candidate entry is a cross of
# the hourly RSI above a level in [CROSS_MIN, CROSS_MAX], so resolving the superset once
# means a candidate is a filter over rows already in memory rather than a re-scan of
# 6.9 million bars.
CROSS_MIN, CROSS_MAX = 50.0, 70.0


# ------------------------------------------------------------------ the search space

# kind: float / int / choice.  "off" is the probability the filter is simply not used;
# a parameter without it is always present. Ranges are inclusive, floats snap to `step`.
SPACE: dict[str, dict] = {
    # entry
    "cross_level":    {"kind": "float", "lo": CROSS_MIN, "hi": CROSS_MAX, "step": 1.0},
    "ema_max":        {"kind": "float", "lo": 40, "hi": 75, "step": 1.0, "off": 0.30},
    "ema_min":        {"kind": "float", "lo": 20, "hi": 55, "step": 1.0, "off": 0.60},
    # regime, read from the last completed bar of each timeframe
    "daily_min":      {"kind": "float", "lo": 40, "hi": 75, "step": 1.0, "off": 0.40},
    "weekly_min":     {"kind": "float", "lo": 40, "hi": 75, "step": 1.0, "off": 0.40},
    "monthly_min":    {"kind": "float", "lo": 40, "hi": 75, "step": 1.0, "off": 0.40},
    # the signal candle
    "close_pos_min":  {"kind": "float", "lo": 0.30, "hi": 0.95, "step": 0.05, "off": 0.50},
    "wick_max":       {"kind": "float", "lo": 0.05, "hi": 0.50, "step": 0.05, "off": 0.60},
    "risk_min":       {"kind": "float", "lo": 0.005, "hi": 0.050, "step": 0.005, "off": 0.50},
    "risk_max":       {"kind": "float", "lo": 0.020, "hi": 0.150, "step": 0.010, "off": 0.70},
    "jump_min":       {"kind": "float", "lo": 2, "hi": 20, "step": 1.0, "off": 0.60},
    # participation and location
    "vol_ratio_min":  {"kind": "float", "lo": 0.8, "hi": 3.0, "step": 0.1, "off": 0.55},
    "turnover_min":   {"kind": "float", "lo": 1, "hi": 100, "step": 1.0, "off": 0.60},
    "above_h50_min":  {"kind": "float", "lo": -0.05, "hi": 0.15, "step": 0.01, "off": 0.60},
    # timing
    "no_repeat":      {"kind": "choice", "choices": [True, False]},
    "skip_edge_hours": {"kind": "choice", "choices": [True, False]},
    # exit
    "stop_mode":      {"kind": "choice", "choices": ["low", "atr"]},
    "atr_k":          {"kind": "float", "lo": 0.5, "hi": 4.0, "step": 0.25},
    "reward_risk":    {"kind": "float", "lo": 1.0, "hi": 12.0, "step": 0.5},
    # portfolio
    "slots":          {"kind": "int", "lo": 3, "hi": 40},
    "per_symbol":     {"kind": "choice", "choices": [1, 2, None]},
}


def space_size() -> float:
    """How many configurations the space holds, before normalise() collapses the inert ones."""
    total = 1.0
    for spec in SPACE.values():
        if spec["kind"] == "choice":
            count = len(spec["choices"])
        elif spec["kind"] == "int":
            count = spec["hi"] - spec["lo"] + 1
        else:
            count = round((spec["hi"] - spec["lo"]) / spec["step"]) + 1
        total *= count + (1 if "off" in spec else 0)
    return total


def _snap(spec: dict, value: float) -> float:
    lo, hi, step = spec["lo"], spec["hi"], spec["step"]
    steps = round((value - lo) / step)
    return round(min(max(lo + steps * step, lo), hi), 6)


def sample_param(name: str, rng: random.Random):
    spec = SPACE[name]
    if "off" in spec and rng.random() < spec["off"]:
        return None
    if spec["kind"] == "choice":
        return rng.choice(spec["choices"])
    if spec["kind"] == "int":
        return rng.randint(spec["lo"], spec["hi"])
    return _snap(spec, rng.uniform(spec["lo"], spec["hi"]))


def normalise(cfg: dict) -> dict:
    """Collapse configurations that differ only where the difference cannot matter."""
    cfg = dict(cfg)
    if cfg["stop_mode"] == "low":
        cfg["atr_k"] = None                      # inert; keeping it would forge new configs
    if cfg["atr_k"] is None and cfg["stop_mode"] == "atr":
        cfg["atr_k"] = 1.0
    if cfg["risk_min"] is not None and cfg["risk_max"] is not None \
            and cfg["risk_max"] <= cfg["risk_min"]:
        cfg["risk_max"] = None                   # an empty band is not a filter
    if cfg["ema_min"] is not None and cfg["ema_max"] is not None \
            and cfg["ema_min"] >= cfg["ema_max"]:
        cfg["ema_min"] = None
    return cfg


def random_config(rng: random.Random) -> dict:
    return normalise({name: sample_param(name, rng) for name in SPACE})


def mutate(parent: dict, rng: random.Random) -> dict:
    """Change one to three knobs of an elite: toggle a filter, or nudge it a few steps."""
    cfg = dict(parent)
    for name in rng.sample(list(SPACE), rng.randint(1, 3)):
        spec = SPACE[name]
        if spec["kind"] == "choice":
            cfg[name] = rng.choice([c for c in spec["choices"] if c != cfg[name]])
        elif cfg[name] is None or rng.random() < 0.20:
            cfg[name] = sample_param(name, rng)   # switch the filter on, or off again
        elif spec["kind"] == "int":
            step = rng.choice([-3, -2, -1, 1, 2, 3])
            cfg[name] = min(max(cfg[name] + step, spec["lo"]), spec["hi"])
        else:
            step = spec["step"] * rng.choice([-3, -2, -1, 1, 2, 3])
            cfg[name] = _snap(spec, cfg[name] + step)
    return normalise(cfg)


def config_key(cfg: dict) -> str:
    payload = json.dumps({k: cfg[k] for k in sorted(SPACE)}, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def describe(cfg: dict) -> str:
    parts = [f"cross>{cfg['cross_level']:g}"]
    for name, fmt in (("ema_min", "emaRSI>{:g}"), ("ema_max", "emaRSI<{:g}"),
                      ("daily_min", "D>{:g}"), ("weekly_min", "W>{:g}"),
                      ("monthly_min", "M>{:g}"), ("close_pos_min", "closePos>={:.2f}"),
                      ("wick_max", "wick<={:.2f}"), ("risk_min", "risk>={:.3f}"),
                      ("risk_max", "risk<={:.3f}"), ("jump_min", "jump>={:g}"),
                      ("vol_ratio_min", "vol>={:.1f}x"), ("turnover_min", "turnover>={:g}cr"),
                      ("above_h50_min", "vs h50>={:+.2f}")):
        if cfg[name] is not None:
            parts.append(fmt.format(cfg[name]))
    if cfg["no_repeat"]:
        parts.append("noRepeat20")
    if cfg["skip_edge_hours"]:
        parts.append("skip 9&15")
    stop = "candle low" if cfg["stop_mode"] == "low" else f"ATR x{cfg['atr_k']:g}"
    parts.append(f"stop {stop}")
    parts.append(f"target 1:{cfg['reward_risk']:g}")
    parts.append(f"{cfg['slots']} slots")
    parts.append(f"{cfg['per_symbol']}/symbol" if cfg["per_symbol"] else "unlimited/symbol")
    return "  ".join(parts)


def signal_mask(cfg: dict) -> pl.Expr:
    """The candidate's entry condition, as a predicate over the signal superset."""
    level = cfg["cross_level"]
    mask = (pl.col("rsi_prev") <= level) & (pl.col("rsi_h") > level)
    # Built one at a time rather than as a table of expressions: an expression for a
    # filter that is switched off would compare a column against None, which polars
    # evaluates to null and warns about, on every candidate.
    tests = (
        ("ema_max", "rsi_ema", "<"), ("ema_min", "rsi_ema", ">"),
        ("daily_min", "rsi_daily", ">"), ("weekly_min", "rsi_weekly", ">"),
        ("monthly_min", "rsi_monthly", ">"), ("close_pos_min", "close_pos", ">="),
        ("wick_max", "upper_wick", "<="), ("risk_min", "risk_pct", ">="),
        ("risk_max", "risk_pct", "<="), ("jump_min", "rsi_jump", ">="),
        ("vol_ratio_min", "vol_ratio", ">="), ("turnover_min", "turnover_cr", ">="),
        ("above_h50_min", "above_h50", ">="),
    )
    for name, column, op in tests:
        value = cfg[name]
        if value is None:
            continue
        col = pl.col(column)
        mask = mask & {"<": col < value, "<=": col <= value,
                       ">": col > value, ">=": col >= value}[op]
    if cfg["no_repeat"]:
        mask = mask & (pl.col("recent_signals") == 0)
    if cfg["skip_edge_hours"]:
        mask = mask & ~pl.col("hour").is_in([9, 15])
    return mask.fill_null(False)


# ------------------------------------------------------------------------- the panel


class Panel:
    """Everything the loop reads: bars per symbol, the signal superset, the price grid."""

    def __init__(self, bars: pl.DataFrame, signals: pl.DataFrame, train_frac: float):
        self.signals = signals
        self.bars = bars
        self.arrays = {}
        for part in bars.partition_by("symbol", maintain_order=True):
            self.arrays[part["symbol"][0]] = {
                "times": part["datetime"].dt.epoch("us").to_numpy(),
                "open": part["open"].to_numpy(), "high": part["high"].to_numpy(),
                "low": part["low"].to_numpy(), "close": part["close"].to_numpy(),
                "atr": part["atr"].to_numpy(),
            }
        wide = (bars.select("symbol", "datetime", "close")
                .pivot(on="symbol", index="datetime", values="close").sort("datetime"))
        cols = [c for c in wide.columns if c != "datetime"]
        # Two fills, deliberately different. The portfolio needs a price on every bar, so
        # it gets forward *and* backward fill; the benchmark must not see a price before
        # the symbol listed, so it gets forward fill only and is restricted to names that
        # were already trading when its window opened.
        self.prices = wide.with_columns([pl.col(c).forward_fill().backward_fill()
                                         for c in cols])
        self.grid = self.prices["datetime"].dt.epoch("us").to_numpy()
        self.split = int(len(self.grid) * train_frac)
        self.split_us = int(self.grid[self.split])
        self.train_prices = self.prices[: self.split]
        self.holdout_prices = self.prices[self.split:]
        self.stamps = wide["datetime"]

        ff = wide.with_columns([pl.col(c).forward_fill() for c in cols])
        matrix = ff.select(cols).to_numpy()
        self.bench_train = self._benchmark(matrix[: self.split])
        self.bench_holdout = self._benchmark(matrix[self.split:])

    @staticmethod
    def _benchmark(matrix: np.ndarray) -> dict:
        """Equal-weight buy-and-hold: the MEAN of normalised prices, not the median."""
        listed = ~np.isnan(matrix[0])
        norm = matrix[:, listed] / matrix[0, listed]
        step = norm[1:] / np.where(norm[:-1] == 0, np.nan, norm[:-1])
        with np.errstate(invalid="ignore"):
            # An hourly bar moving more than 50% is an unadjusted corporate action, not a
            # traded price. Removed by that defect, never by how the name ended up.
            artefact = np.nanmax(np.abs(step - 1.0), axis=0) > 0.50
        curve = np.nanmean(norm[:, ~artefact], axis=1)
        return {"curve": curve, "symbols": int((~artefact).sum())}


def build_panel(universe: str, hourly_dir: str, period: int, ema_span: int,
                train_frac: float, rebuild: bool) -> Panel:
    key = f"{universe}_{hourly_dir}_p{period}_e{ema_span}_x{CROSS_MIN:g}-{CROSS_MAX:g}"
    bars_cache, sig_cache = CACHE / f"bars_{key}.parquet", CACHE / f"signals_{key}.parquet"
    if bars_cache.exists() and sig_cache.exists() and not rebuild:
        print(f"panel from cache ({bars_cache.name})", flush=True)
        return Panel(pl.read_parquet(bars_cache), pl.read_parquet(sig_cache), train_frac)

    t0 = time.time()
    uni = pl.read_parquet(UNIVERSE)
    if universe != "nse_all":
        uni = uni.filter(pl.col(f"in_{universe}"))
    symbols = uni["symbol"].to_list()
    daily = (pl.scan_parquet(DAILY_GLOB, hive_partitioning=True)
             .filter(pl.col("symbol").is_in(symbols))
             .select("symbol", "date", "open", "high", "low", "close", "volume").collect())
    hourly_glob = str(REPO_ROOT / "data" / "ohlcv" / hourly_dir / "**" / "*.parquet")
    hourly = (pl.scan_parquet(hourly_glob, hive_partitioning=True)
              .filter(pl.col("symbol").is_in(symbols))
              .select("symbol", "datetime", "open", "high", "low", "close", "volume")
              .collect())
    print(f"universe {uni.height} | daily {daily.height:,} rows | "
          f"hourly {hourly.height:,} rows from {hourly_dir}", flush=True)

    frame = (hourly.sort("symbol", "datetime")
             .with_columns(rsi("close", period).over("symbol").alias("rsi_h")))
    frame = frame.with_columns(ema("rsi_h", ema_span).over("symbol").alias("rsi_ema"),
                               pl.col("rsi_h").shift(1).over("symbol").alias("rsi_prev"))
    # Wilder's RSI is recursive and reads 100.0 on bar 1 from a zero seed, which passes
    # any "RSI above" test for free. period*3 + ema_span is the guard the rest of the
    # repo uses; it is not optional.
    settle = period * 3 + ema_span
    frame = (frame.with_columns(pl.int_range(pl.len()).over("symbol").alias("_seen"))
             .filter(pl.col("_seen") >= settle).drop("_seen"))
    frame = attach_htf(frame, daily, period)

    prev_close = pl.col("close").shift(1).over("symbol")
    true_range = pl.max_horizontal(pl.col("high") - pl.col("low"),
                                   (pl.col("high") - prev_close).abs(),
                                   (pl.col("low") - prev_close).abs())
    frame = (frame.sort("symbol", "datetime")
             .with_columns(true_range.alias("tr"))
             .with_columns(pl.col("tr").rolling_mean(14).over("symbol").alias("atr")))
    frame = frame.with_columns(
        ((pl.col("rsi_prev") <= CROSS_MAX) & (pl.col("rsi_h") > CROSS_MIN)
         & (pl.col("rsi_h") > pl.col("rsi_prev"))).alias("signal_raw"))
    frame = candle_features(frame)
    # The row's position inside its own symbol's bar array. Fixed here, once: it is what
    # lets a candidate hand walk_signals a set of indices instead of a whole frame.
    frame = frame.with_columns(pl.int_range(pl.len()).over("symbol").alias("bar_i"))

    bars = frame.select("symbol", "datetime", "open", "high", "low", "close", "atr")
    signals = frame.filter(pl.col("signal_raw")).select(
        "symbol", "datetime", "bar_i", "rsi_h", "rsi_prev", "rsi_ema", "rsi_daily",
        "rsi_weekly", "rsi_monthly", "close_pos", "upper_wick", "risk_pct", "rsi_jump",
        "vol_ratio", "turnover_cr", "above_h50", "recent_signals", "hour")
    CACHE.mkdir(parents=True, exist_ok=True)
    bars.write_parquet(bars_cache, compression="zstd")
    signals.write_parquet(sig_cache, compression="zstd")
    print(f"panel built in {time.time() - t0:.0f}s and cached "
          f"({bars.height:,} bars, {signals.height:,} superset signals)", flush=True)
    return Panel(bars, signals, train_frac)


# --------------------------------------------------------------------- one evaluation


def resolve(cfg: dict, sig: pl.DataFrame, arrays: dict, cost: float) -> pl.DataFrame:
    """Walk every candidate signal forward to its stop or target — the shared engine."""
    rows: list[dict] = []
    for (symbol,), part in sig.group_by("symbol", maintain_order=True):
        a = arrays[symbol]
        stops = (a["low"] if cfg["stop_mode"] == "low"
                 else a["close"] - cfg["atr_k"] * a["atr"])
        rows.extend(walk_signals(symbol, a["times"], a["open"], a["high"], a["low"],
                                 a["close"], stops, part["bar_i"].to_numpy(),
                                 cost, cfg["reward_risk"]))
    return pl.DataFrame(rows).sort("entry_time") if rows else pl.DataFrame()


def run_window(trades: pl.DataFrame, prices: pl.DataFrame, cfg: dict, cost: float) -> dict:
    """Portfolio pass over one window, and the numbers that describe the equity curve."""
    traded = trades["symbol"].unique().to_list()
    frame = prices.select(["datetime"] + traded)
    equity, taken, skipped, blocked, stacked, unrealised, extra = simulate(
        trades, frame, cfg["slots"], cost, cfg["per_symbol"], detail=True)
    grid = frame["datetime"].dt.epoch("us").to_numpy()
    years = elapsed_years(grid)
    cagr, maxdd = performance(equity, years)
    step = np.diff(np.log(equity))
    bars_per_year = len(equity) / years
    vol = float(step.std(ddof=1) * np.sqrt(bars_per_year)) if step.size > 1 else 0.0
    # Zero risk-free rate, and the drift is of log equity — so this is a ratio of the
    # curve's own growth to its own noise, not a comparison against cash.
    sharpe = float(step.mean() * bars_per_year / vol) if vol > 0 else 0.0
    half = len(equity) // 2
    per_trade = extra["taken_returns"]
    return {
        "years": years, "roi": float(equity[-1] - 1), "cagr": float(cagr),
        "maxdd": float(maxdd), "ret_dd": float(cagr / max(abs(maxdd), 0.01)),
        "sharpe": sharpe, "vol": vol, "signals": trades.height, "taken": int(taken),
        "skipped": int(skipped), "deployed": extra["deployed"],
        "per_trade": float(per_trade.mean()) if per_trade.size else 0.0,
        "win_rate": float((per_trade > 0).mean()) if per_trade.size else 0.0,
        "h1": float(equity[half] - 1),
        "h2": float(equity[-1] / equity[half] - 1) if equity[half] > 0 else -1.0,
        "unrealised": float(unrealised), "max_stacked": int(stacked),
        "final": float(equity[-1]),
    }


def evaluate(cfg: dict, panel: Panel, args) -> dict:
    """One candidate: filter, walk, run both windows, score on the train window only."""
    sig = panel.signals.filter(signal_mask(cfg))
    if sig.height < args.min_signals:
        return {"status": "too_few_signals", "signals": sig.height}
    if sig.height > args.max_signals:
        return {"status": "too_many_signals", "signals": sig.height}

    trades = resolve(cfg, sig, panel.arrays, args.cost_bps / 10_000)
    if trades.is_empty():
        return {"status": "no_trades", "signals": sig.height}
    train_trades = trades.filter(pl.col("entry_time") < panel.split_us)
    hold_trades = trades.filter(pl.col("entry_time") >= panel.split_us)
    if train_trades.height < args.min_trades or hold_trades.is_empty():
        return {"status": "too_few_trades", "signals": sig.height}

    # A position still open when the train window closes is marked to market there and
    # not carried across: the holdout portfolio starts flat, as a live one would have.
    train = run_window(train_trades, panel.train_prices, cfg, args.cost_bps / 10_000)
    holdout = run_window(hold_trades, panel.holdout_prices, cfg, args.cost_bps / 10_000)
    if train["taken"] < args.min_trades:
        return {"status": "too_few_taken", "signals": sig.height}

    eligible = True
    if not args.no_half_guard and (train["h1"] <= 0 or train["h2"] <= 0):
        eligible = False
    if train["deployed"] < args.min_deployed:
        eligible = False
    return {"status": "ok", "eligible": eligible, "signals": sig.height,
            "score": train[args.objective], "train": train, "holdout": holdout}


# ------------------------------------------------------------------------- the ledger


def load_trials(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:      # a run killed mid-write leaves a half line
                continue
    return out


def rescore(trials: list[dict], args) -> None:
    """Re-derive score and eligibility from the flags of *this* run.

    The ledger stores every window metric, so a run resumed under a different objective
    or a tighter guard re-ranks its own history instead of carrying forward numbers that
    answer a question nobody is asking any more.
    """
    for trial in trials:
        if trial["status"] != "ok":
            continue
        train = trial["train"]
        trial["score"] = train[args.objective]
        trial["eligible"] = bool(
            (args.no_half_guard or (train["h1"] > 0 and train["h2"] > 0))
            and train["deployed"] >= args.min_deployed
            and train["taken"] >= args.min_trades)


def leaderboard(trials: list[dict], top: int) -> list[dict]:
    ok = [t for t in trials if t["status"] == "ok" and t.get("eligible")]
    return sorted(ok, key=lambda t: t["score"], reverse=True)[:top]


class Elites:
    """The parent pool, kept sorted as records arrive.

    Re-ranking the whole ledger once per iteration is quadratic, and a loop meant to run
    for days reaches tens of thousands of trials — at which point the search spends more
    time sorting its own history than backtesting.
    """

    def __init__(self, size: int, seed: list[dict]):
        self.size = size
        self.rows = list(seed)[:size]

    @staticmethod
    def _fingerprint(record: dict) -> tuple:
        return record["train"]["taken"], round(record["train"]["roi"], 6)

    def add(self, record: dict) -> bool:
        """Returns True when this record took the top spot."""
        if record["status"] != "ok" or not record["eligible"]:
            return False
        # Two configurations that produce the same book are one candidate. Without this
        # the pool fills with a knob that binds nothing, and every parent is the same
        # strategy wearing a different hat.
        mark = self._fingerprint(record)
        for i, row in enumerate(self.rows):
            if self._fingerprint(row) == mark:
                if record["score"] <= row["score"]:
                    return False
                self.rows[i] = record
                break
        else:
            self.rows.append(record)
        self.rows.sort(key=lambda t: t["score"], reverse=True)
        del self.rows[self.size:]
        return self.rows[0] is record


def print_table(rows: list[dict], panel: Panel | None, args) -> None:
    if not rows:
        print("no eligible candidate yet")
        return
    head = (f"{'#':>3} {'iter':>6} {'RR':>5} {'slots':>6} {'ROI %':>9} {'CAGR %':>8} "
            f"{'MaxDD %':>8} {'Ret/DD':>7} {'Sharpe':>7} {'Vol %':>6} {'Trades':>7} "
            f"{'%/trade':>8} {'Dep %':>6} │ {'ROI %':>9} {'CAGR %':>8} {'Ret/DD':>7} "
            f"{'Trades':>7}")
    print(f"\n{' ' * 88}train (searched){' ' * 8}│{' ' * 8}holdout (never scored)")
    print(head)
    print("─" * len(head))
    for i, t in enumerate(rows, 1):
        a, b = t["train"], t["holdout"]
        print(f"{i:>3} {t['iter']:>6} {t['config']['reward_risk']:>5g} "
              f"{t['config']['slots']:>6} {a['roi'] * 100:>9,.1f} {a['cagr'] * 100:>8.2f} "
              f"{a['maxdd'] * 100:>8.2f} {a['ret_dd']:>7.2f} {a['sharpe']:>7.2f} "
              f"{a['vol'] * 100:>6.1f} {a['taken']:>7,} {a['per_trade'] * 100:>8.2f} "
              f"{a['deployed'] * 100:>6.0f} │ {b['roi'] * 100:>9,.1f} "
              f"{b['cagr'] * 100:>8.2f} {b['ret_dd']:>7.2f} {b['taken']:>7,}")
    if panel is not None:
        for label, bench, prices in (("train  ", panel.bench_train, panel.train_prices),
                                     ("holdout", panel.bench_holdout, panel.holdout_prices)):
            years = elapsed_years(prices["datetime"].dt.epoch("us").to_numpy())
            cagr, dd = performance(bench["curve"], years)
            print(f"benchmark {label} equal-weight buy-and-hold, {bench['symbols']} names, "
                  f"fully invested: ROI {(bench['curve'][-1] - 1) * 100:+,.1f}%  "
                  f"CAGR {cagr * 100:+.2f}%  maxDD {dd * 100:.2f}%  "
                  f"ret/DD {abs(cagr / dd):.2f}")
    print("Trades = positions the book actually took; %/trade is their mean return. "
          "Dep % = average share of slots in use.")


def _ranks(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), float)
    ranks[order] = np.arange(len(x), dtype=float)
    vals, inverse, counts = np.unique(x, return_inverse=True, return_counts=True)
    sums = np.zeros(len(vals))
    np.add.at(sums, inverse, ranks)
    return (sums / counts)[inverse]


def print_audit(trials: list[dict], panel: Panel | None, args) -> None:
    """Did the search find an edge, or did it fit noise? This block answers that."""
    ok = [t for t in trials if t["status"] == "ok"]
    if len(ok) < 5:
        print("\ntoo few evaluations for a selection audit")
        return
    train = np.array([t["score"] for t in ok])
    hold = np.array([t["holdout"][args.objective] for t in ok])
    rho = float(np.corrcoef(_ranks(train), _ranks(hold))[0, 1]) if len(ok) > 2 else float("nan")
    # The top block is the leaderboard's, not merely the best-scoring rows: a candidate the
    # guards rejected is not something the search would ever hand you, so including it here
    # would audit a selection nobody makes.
    ranked = sorted([t for t in ok if t.get("eligible")],
                    key=lambda t: t["score"], reverse=True)
    if not ranked:
        print("\nno candidate passed the guards — nothing to audit")
        return
    top = ranked[:args.top]
    top_hold = np.array([t["holdout"]["cagr"] for t in top])
    all_hold = np.array([t["holdout"]["cagr"] for t in ok])
    counted = {s: sum(1 for t in trials if t["status"] == s)
               for s in sorted({t["status"] for t in trials})}

    print(f"\n{'=' * 96}\nSELECTION AUDIT — read this before the table\n{'=' * 96}")
    print(f"trials {len(trials):,}  ({', '.join(f'{k} {v:,}' for k, v in counted.items())})")
    print(f"train-vs-holdout rank correlation of the objective across all {len(ok):,} "
          f"evaluations: {rho:+.3f}")
    print("  near zero means the leaderboard ordering carries no information out of "
          "sample — the search fitted the train window and nothing else.")
    top_train_obj = np.median([t["score"] for t in top])
    top_hold_obj = np.median([t["holdout"][args.objective] for t in top])
    print(f"{args.objective} of the top {len(top)}: median {top_train_obj:+.2f} on the train "
          f"window → {top_hold_obj:+.2f} out of sample "
          f"({(top_hold_obj - top_train_obj) / abs(top_train_obj) * 100:+.0f}%)")
    print(f"holdout CAGR, top {len(top)} by train score : median {np.median(top_hold) * 100:+.2f}%  "
          f"positive {int((top_hold > 0).sum())}/{len(top_hold)}")
    print(f"holdout CAGR, all {len(ok)} evaluations{'':>5}: median "
          f"{np.median(all_hold) * 100:+.2f}%  positive "
          f"{int((all_hold > 0).sum())}/{len(all_hold)}")
    print("  the top block has to beat the base rate underneath it, or selection did "
          "nothing.")
    if panel is not None:
        years = elapsed_years(panel.holdout_prices["datetime"].dt.epoch("us").to_numpy())
        bench_cagr, _ = performance(panel.bench_holdout["curve"], years)
        beat = int((all_hold > bench_cagr).sum())
        beat_top = int((top_hold > bench_cagr).sum())
        print(f"beat equal-weight buy-and-hold ({bench_cagr * 100:+.2f}% CAGR) out of "
              f"sample: {beat_top}/{len(top_hold)} of the top block, "
              f"{beat}/{len(all_hold)} of everything")
    best = ranked[0]
    print(f"\nleader  {describe(best['config'])}")
    print(f"        train   CAGR {best['train']['cagr'] * 100:+.2f}%  maxDD "
          f"{best['train']['maxdd'] * 100:.2f}%  ret/DD {best['train']['ret_dd']:.2f}  "
          f"halves {best['train']['h1'] * 100:+.1f}% / {best['train']['h2'] * 100:+.1f}%")
    print(f"        holdout CAGR {best['holdout']['cagr'] * 100:+.2f}%  maxDD "
          f"{best['holdout']['maxdd'] * 100:.2f}%  ret/DD {best['holdout']['ret_dd']:.2f}  "
          f"trades {best['holdout']['taken']:,}")
    print(f"        replay it with:  python scripts/strategy_loop.py --replay 1"
          f"{'' if args.tag == 'default' else f' --tag {args.tag}'}")


# -------------------------------------------------------------------------- self-check


REFERENCE = {"cross_level": 60.0, "ema_max": 53.0, "daily_min": 60.0, "weekly_min": 60.0,
             "monthly_min": 60.0, "stop_mode": "low", "reward_risk": 5.0, "slots": 10}


def self_check(panel: Panel, args) -> int:
    """Does the fast path still agree with the engine everything else in the repo uses?

    The loop resolves exits from per-symbol arrays it holds in memory; rsi_backtest.py walks
    the panel frame. Both call walk_signals, so they cannot disagree about a trade — unless
    the indices, the ordering or the stop column have drifted, which is exactly the kind of
    break that produces plausible numbers rather than an error. This makes it fail loudly.

    The configuration is the hourly RSI re-ignition setup as the README describes it, so the
    printed numbers can also be read against:

        python scripts/rsi_backtest.py --universe nifty500 \
            --hourly-dir 60minute_kite_clean --skip-market-cap --reward-risk 5 --slots 10
    """
    cfg = normalise({name: None for name in SPACE} | {"no_repeat": False,
                                                      "skip_edge_hours": False,
                                                      "per_symbol": None} | REFERENCE)
    cost = args.cost_bps / 10_000
    sig = panel.signals.filter(signal_mask(cfg))
    fast = resolve(cfg, sig, panel.arrays, cost)

    flags = sig.select("symbol", "datetime").with_columns(pl.lit(True).alias("signal"))
    frame = (panel.bars.join(flags, on=["symbol", "datetime"], how="left")
             .with_columns(pl.col("signal").fill_null(False)).sort("symbol", "datetime"))
    slow = find_trades(frame, cost, cfg["reward_risk"])

    order = ["symbol", "entry_time"]
    same = fast.sort(order).equals(slow.sort(order))
    print(f"\n{describe(cfg)}")
    print(f"  fast path (walk_signals over cached arrays): {fast.height:,} trades")
    print(f"  engine    (find_trades over the panel)     : {slow.height:,} trades")
    print(f"  identical: {same}")
    metrics = run_window(fast, panel.prices, cfg, cost)
    print(f"  full window {metrics['years']:.2f} yrs | {metrics['taken']:,} taken | "
          f"CAGR {metrics['cagr'] * 100:+.2f}% | maxDD {metrics['maxdd'] * 100:.2f}% | "
          f"final x{metrics['final']:.3f}")
    if not same:
        print("  the two paths disagree — do not trust anything this loop has produced",
              file=sys.stderr)
        return 1
    return 0


# ------------------------------------------------------------------------------ replay


def replay(trials: list[dict], panel: Panel, args, rank: int) -> int:
    rows = leaderboard(trials, max(rank, args.top))
    if len(rows) < rank:
        print(f"rank {rank} does not exist — {len(rows)} eligible candidates stored")
        return 1
    entry = rows[rank - 1]
    cfg = normalise(entry["config"])
    print(f"\nrank {rank}  {describe(cfg)}\n{'─' * 96}")
    cost = args.cost_bps / 10_000
    sig = panel.signals.filter(signal_mask(cfg))
    trades = resolve(cfg, sig, panel.arrays, cost)
    windows = (
        ("train  ", trades.filter(pl.col("entry_time") < panel.split_us), panel.train_prices),
        ("holdout", trades.filter(pl.col("entry_time") >= panel.split_us), panel.holdout_prices),
        ("full   ", trades, panel.prices),
    )
    print(f"{'window':<9}{'years':>7}{'signals':>9}{'taken':>8}{'ROI %':>10}{'CAGR %':>9}"
          f"{'maxDD %':>9}{'ret/DD':>8}{'Sharpe':>8}{'win %':>7}{'%/trade':>9}{'dep %':>7}")
    for label, part, prices in windows:
        if part.is_empty():
            print(f"{label:<9}{'no trades':>7}")
            continue
        m = run_window(part, prices, cfg, cost)
        print(f"{label:<9}{m['years']:>7.2f}{m['signals']:>9,}{m['taken']:>8,}"
              f"{m['roi'] * 100:>10,.1f}{m['cagr'] * 100:>9.2f}{m['maxdd'] * 100:>9.2f}"
              f"{m['ret_dd']:>8.2f}{m['sharpe']:>8.2f}{m['win_rate'] * 100:>7.1f}"
              f"{m['per_trade'] * 100:>9.2f}{m['deployed'] * 100:>7.0f}")
    outcomes = trades.group_by("outcome").len().sort("len", descending=True)
    print("outcome mix: " + "  ".join(f"{r['outcome']} {r['len']:,}"
                                      for r in outcomes.iter_rows(named=True)))
    closed = trades.filter(pl.col("outcome") != "open")
    ranked = closed["ret"].sort(descending=True)
    gross = float(ranked.filter(ranked > 0).sum())
    if gross > 0:
        print(f"concentration: the top 10 winners are "
              f"{float(ranked.head(10).sum()) / gross:.0%} of all gains — "
              f"a result that rests on a handful of trades is one window's luck")
    for label, bench, prices in (("train  ", panel.bench_train, panel.train_prices),
                                 ("holdout", panel.bench_holdout, panel.holdout_prices)):
        years = elapsed_years(prices["datetime"].dt.epoch("us").to_numpy())
        cagr, dd = performance(bench["curve"], years)
        print(f"benchmark {label}: CAGR {cagr * 100:+.2f}%  maxDD {dd * 100:.2f}%")
    print(json.dumps(cfg, sort_keys=True))
    return 0


# -------------------------------------------------------------------------------- main


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--universe", default="nifty500")
    p.add_argument("--hourly-dir", default="60minute_kite_clean",
                   help="panel to trade (default the cleaned, adjusted Kite hourly panel)")
    p.add_argument("--rsi-period", type=int, default=14)
    p.add_argument("--ema-span", type=int, default=21)
    p.add_argument("--cost-bps", type=float, default=10.0,
                   help="one-way cost in basis points (default 10 = 0.20%% round trip)")
    p.add_argument("--train-frac", type=float, default=0.70,
                   help="share of the window the search may score on (default 0.70)")
    p.add_argument("--objective", default="ret_dd", choices=["ret_dd", "cagr", "sharpe"])
    p.add_argument("--min-trades", type=int, default=100,
                   help="a candidate the book takes fewer times than this is noise")
    p.add_argument("--min-deployed", type=float, default=0.0,
                   help="minimum average share of slots in use, 0-1. The default lets "
                        "the search win by staying in cash: return per drawdown rewards "
                        "absence, and a book that is 90%% flat has a small drawdown "
                        "because it holds nothing. Set it to compare like with like")
    p.add_argument("--min-signals", type=int, default=60)
    p.add_argument("--max-signals", type=int, default=20_000,
                   help="a setup that fires more often than this is rationed away by the "
                        "slot count, so the test would measure the slots, not the setup")
    p.add_argument("--no-half-guard", action="store_true",
                   help="rank candidates that lose money in one half of the train window")
    p.add_argument("--iterations", type=int, default=0, help="0 = until stopped")
    p.add_argument("--minutes", type=float, default=0, help="0 = no time limit")
    p.add_argument("--random-iters", type=int, default=60,
                   help="draws taken at random before mutation of the elites begins")
    p.add_argument("--explore", type=float, default=0.25,
                   help="chance of a fresh random draw once seeding is over")
    p.add_argument("--elite", type=int, default=10, help="size of the parent pool")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--print-every", type=int, default=100,
                   help="trials between progress lines; the leader is always announced")
    p.add_argument("--table-every", type=int, default=1000,
                   help="trials between full leaderboard prints")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--tag", default="default", help="name this run's ledger")
    p.add_argument("--rebuild", action="store_true", help="ignore the cached panel")
    p.add_argument("--no-resume", action="store_true", help="start a fresh ledger")
    p.add_argument("--report", action="store_true", help="print the stored leaderboard "
                                                         "and exit")
    p.add_argument("--replay", type=int, default=0, metavar="RANK",
                   help="re-run one leaderboard entry and report it in full")
    p.add_argument("--self-check", action="store_true",
                   help="prove the fast path still agrees with rsi_backtest's engine")
    args = p.parse_args()

    ledger = CACHE / args.tag / "trials.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    trials = [] if args.no_resume else load_trials(ledger)
    rescore(trials, args)

    panel = build_panel(args.universe, args.hourly_dir, args.rsi_period, args.ema_span,
                        args.train_frac, args.rebuild)
    print(f"window {panel.stamps[0]} → {panel.stamps[-1]}  "
          f"({len(panel.grid):,} bars, {len(panel.arrays)} symbols, "
          f"{panel.signals.height:,} superset signals)")
    print(f"train {panel.stamps[0].date()} → {panel.stamps[panel.split - 1].date()}  "
          f"({panel.split:,} bars)   holdout {panel.stamps[panel.split].date()} → "
          f"{panel.stamps[-1].date()}  ({len(panel.grid) - panel.split:,} bars)")
    print(f"search space {space_size():.3g} configurations")

    if args.report:
        print(f"ledger {ledger} — {len(trials):,} trials")
        print_table(leaderboard(trials, args.top), panel, args)
        print_audit(trials, panel, args)
        return 0

    if args.self_check:
        return self_check(panel, args)
    if args.replay:
        return replay(trials, panel, args, args.replay)

    rng = random.Random(args.seed + len(trials))
    elites = Elites(max(args.elite, args.top), leaderboard(trials, max(args.elite, args.top)))
    seen = {t["key"] for t in trials}
    stop = {"now": False}

    def handle(signum, frame):                      # noqa: ARG001 - signal handler shape
        if stop["now"]:
            raise KeyboardInterrupt
        stop["now"] = True
        print("\nstopping after this iteration (Ctrl-C again to abort)", flush=True)

    signal_mod.signal(signal_mod.SIGINT, handle)
    signal_mod.signal(signal_mod.SIGTERM, handle)

    deadline = time.time() + args.minutes * 60 if args.minutes else None
    started, evaluated = time.time(), 0
    print(f"\nledger {ledger} — resuming with {len(trials):,} trials\n"
          f"objective {args.objective} on the train window; the holdout is never scored")

    with ledger.open("a") as sink:
        while not stop["now"]:
            if args.iterations and evaluated >= args.iterations:
                break
            if deadline and time.time() > deadline:
                break

            cfg = None
            for _ in range(50):                    # a duplicate is not an evaluation
                if len(trials) < args.random_iters or not elites.rows \
                        or rng.random() < args.explore:
                    candidate = random_config(rng)
                else:
                    candidate = mutate(rng.choice(elites.rows)["config"], rng)
                if config_key(candidate) not in seen:
                    cfg = candidate
                    break
            if cfg is None:
                print("the proposer keeps returning configurations already tried — "
                      "widen the space or stop")
                break

            key = config_key(cfg)
            seen.add(key)
            result = evaluate(cfg, panel, args)
            record = {"iter": len(trials) + 1, "key": key, "config": cfg,
                      "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      **result}
            trials.append(record)
            sink.write(json.dumps(record, default=str) + "\n")
            sink.flush()
            evaluated += 1

            if elites.add(record):
                print(f"★ {record['iter']:>7,}  score {result['score']:>6.2f}  "
                      f"train {result['train']['cagr'] * 100:>+7.2f}%  holdout "
                      f"{result['holdout']['cagr'] * 100:>+7.2f}%  "
                      f"{result['train']['taken']:>5,} trades\n            "
                      f"{describe(cfg)}", flush=True)
            if args.print_every and evaluated % args.print_every == 0:
                ok = sum(1 for t in trials if t["status"] == "ok")
                rate = evaluated / max(time.time() - started, 1e-9) * 60
                best = elites.rows[0]["score"] if elites.rows else float("nan")
                print(f"  {len(trials):>7,} trials  {ok:>6,} scored  "
                      f"{len(elites.rows):>3} eligible  best {best:>6.2f}  "
                      f"{rate:>6.0f}/min", flush=True)
            if args.table_every and evaluated % args.table_every == 0:
                print_table(elites.rows[:args.top], panel, args)

    minutes = (time.time() - started) / 60
    print(f"\n{evaluated:,} candidates tried in {minutes:.1f} min "
          f"({evaluated / max(minutes, 1e-9):.1f}/min)")
    print_table(elites.rows[:args.top], panel, args)
    print_audit(trials, panel, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
