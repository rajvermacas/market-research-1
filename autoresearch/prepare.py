#!/usr/bin/env python3
"""Builds the price panel every experiment in this loop is scored on — immutable harness.

The committed daily parquet is long format, one row per symbol/session. A cross-sectional
strategy wants the other shape: a matrix of dates by symbols. This script does that
conversion once, caches it, and hands back a `Panel` that a strategy reads and cannot write.

What it does, and why each step is the way it is:

  * **Total-return prices.** `open/high/low/close` in the daily panel are split-adjusted;
    `adj_close` is additionally dividend-adjusted. Mixing the two conventions inside one test
    is how a strategy accidentally shorts every dividend. Every price column here is scaled by
    `adj_close / close`, so all four are on one total-return basis.

  * **A causal tradability mask.** Filtering the universe by full-sample average liquidity is
    look-ahead — it selects the names that went on to be liquid. Instead `tradable` is built
    from trailing information only: median rupee turnover over the last `--liquidity-window`
    sessions at or above `--min-turnover`, and at least `--min-history` observed closes. The
    harness zeroes any weight placed on a name that was not tradable on that bar.

  * **Marking prices.** Yahoo drops the odd session for individual symbols. Signals read
    `close`, which carries the NaN, so no signal fires on a bar the data does not have. Open
    positions are marked on `mark` — the forward-filled close — so a gap books zero that day
    and the whole move on the next real bar, rather than manufacturing a return from nothing.

  * **Warm-up room.** `--start` is deliberately earlier than the first scored window. Recursive
    indicators are seeded from that lead-in, so the score windows begin with warm indicators
    instead of a warm-up truncation that silently deletes the earliest regime.

The universe is NSE's *current* index membership, so every result carries survivorship bias:
names that fell out of the index, or delisted, are absent. See the repository README.

Usage:
    python autoresearch/prepare.py                       # build/refresh the default panel
    python autoresearch/prepare.py --universe nifty200 --min-turnover 3e7
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
DAILY_DIR = REPO_ROOT / "data" / "ohlcv" / "daily"
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CACHE_DIR = REPO_ROOT / ".cache" / "autoresearch"

DEFAULTS = dict(
    universe="nifty500",
    start="2004-01-01",
    end=None,
    min_turnover=2e7,      # rupees per day, median over the trailing window (2 crore)
    min_history=250,       # observed closes before a name may be held
    liquidity_window=60,
)


@dataclass(frozen=True)
class Panel:
    """A read-only price panel. Rows are sessions, columns are symbols.

    Every matrix is `(len(dates), len(symbols))` float64 with NaN where the symbol had no bar,
    except `tradable`, which is boolean. `open_/high/low/close` are total-return adjusted.
    """

    dates: np.ndarray            # datetime64[D], ascending, unique
    symbols: tuple[str, ...]
    open_: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray            # NaN on a missing session — signals read this
    mark: np.ndarray             # forward-filled close — positions are marked on this
    volume: np.ndarray
    rupee_volume: np.ndarray     # close * volume, the liquidity proxy
    tradable: np.ndarray         # bool: liquid enough and long enough listed, causally
    meta: dict

    @property
    def n_bars(self) -> int:
        return len(self.dates)

    @property
    def n_symbols(self) -> int:
        return len(self.symbols)

    def head(self, n_bars: int) -> "Panel":
        """The first `n_bars` rows — used by the look-ahead probe, and safe to use anywhere."""
        cut = {f: getattr(self, f)[:n_bars] for f in
               ("dates", "open_", "high", "low", "close", "mark", "volume", "rupee_volume",
                "tradable")}
        return replace(self, **cut)

    def window(self, start: str | None, end: str | None) -> np.ndarray:
        """Boolean row mask for a date window; both ends inclusive."""
        m = np.ones(self.n_bars, dtype=bool)
        if start:
            m &= self.dates >= np.datetime64(start, "D")
        if end:
            m &= self.dates <= np.datetime64(end, "D")
        return m


def _ffill(a: np.ndarray) -> np.ndarray:
    """Forward-fill down each column. Leading NaN stays NaN — there is nothing to carry."""
    idx = np.where(np.isfinite(a), np.arange(a.shape[0])[:, None], 0)
    np.maximum.accumulate(idx, axis=0, out=idx)
    out = np.take_along_axis(a, idx, axis=0)
    seen = np.maximum.accumulate(np.isfinite(a), axis=0)
    return np.where(seen, out, np.nan)


def _fingerprint(cfg: dict) -> str:
    """Cache key: the build settings plus the size and mtime of every daily parquet file."""
    files = sorted(DAILY_DIR.glob("**/*.parquet"))
    stamp = [(str(p.relative_to(REPO_ROOT)), p.stat().st_size, int(p.stat().st_mtime))
             for p in files]
    blob = json.dumps({"cfg": cfg, "files": stamp}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def build(universe: str = DEFAULTS["universe"], start: str = DEFAULTS["start"],
          end: str | None = DEFAULTS["end"], min_turnover: float = DEFAULTS["min_turnover"],
          min_history: int = DEFAULTS["min_history"],
          liquidity_window: int = DEFAULTS["liquidity_window"],
          use_cache: bool = True, verbose: bool = False) -> Panel:
    cfg = dict(universe=universe, start=start, end=end, min_turnover=min_turnover,
               min_history=min_history, liquidity_window=liquidity_window)
    key = _fingerprint(cfg)
    cache = CACHE_DIR / f"panel_{key}.npz"
    if use_cache and cache.exists():
        z = np.load(cache, allow_pickle=False)
        meta = dict(cfg, cache=str(cache.relative_to(REPO_ROOT)), source="cache")
        return Panel(dates=z["dates"], symbols=tuple(z["symbols"].tolist()), open_=z["open"],
                     high=z["high"], low=z["low"], close=z["close"], mark=z["mark"],
                     volume=z["volume"], rupee_volume=z["rupee_volume"],
                     tradable=z["tradable"], meta=meta)

    u = pl.read_parquet(UNIVERSE)
    if universe != "nse_all":
        flag = f"in_{universe}"
        if flag not in u.columns:
            raise SystemExit(f"unknown universe {universe!r}; "
                             f"try nse_all or one of {[c[3:] for c in u.columns if c[:3] == 'in_']}")
        u = u.filter(pl.col(flag))
    syms = sorted(u["symbol"].to_list())

    q = (pl.scan_parquet(DAILY_GLOB, hive_partitioning=True)
         .filter(pl.col("symbol").is_in(syms))
         .filter(pl.col("date") >= pl.lit(start).str.to_date()))
    if end:
        q = q.filter(pl.col("date") <= pl.lit(end).str.to_date())
    # One adjustment convention for every column: scale OHLC onto the dividend-adjusted basis.
    long = (q.with_columns(
                pl.when((pl.col("close") > 0) & pl.col("adj_close").is_not_null())
                .then(pl.col("adj_close") / pl.col("close")).otherwise(None).alias("ratio"))
            .with_columns(
                (pl.col("open") * pl.col("ratio")).alias("o"),
                (pl.col("high") * pl.col("ratio")).alias("h"),
                (pl.col("low") * pl.col("ratio")).alias("l"),
                pl.col("adj_close").alias("c"),
                (pl.col("close") * pl.col("volume")).cast(pl.Float64).alias("rv"),
                pl.col("volume").cast(pl.Float64).alias("v"))
            .select("symbol", "date", "o", "h", "l", "c", "v", "rv")
            .collect())

    dates = np.array(sorted(long["date"].unique().to_list()), dtype="datetime64[D]")
    present = sorted(long["symbol"].unique().to_list())

    def matrix(col: str) -> np.ndarray:
        wide = long.pivot(on="symbol", index="date", values=col).sort("date")
        if wide.height != len(dates):
            raise RuntimeError(f"pivot produced {wide.height} rows for {len(dates)} sessions")
        return wide.select(present).with_columns(pl.all().cast(pl.Float64)).to_numpy()

    o, h, l, c = (matrix(x) for x in ("o", "h", "l", "c"))
    v, rv = matrix("v"), matrix("rv")

    # Tradability, from trailing information only.
    liq = (pl.from_numpy(rv, schema=[f"c{i}" for i in range(rv.shape[1])])
           .with_columns(pl.all().fill_nan(None))
           .select(pl.all().rolling_median(liquidity_window,
                                           min_samples=max(liquidity_window // 2, 5)))
           .to_numpy())
    history = np.cumsum(np.isfinite(c), axis=0)
    tradable = (liq >= min_turnover) & (history >= min_history) & np.isfinite(c)

    panel = Panel(dates=dates, symbols=tuple(present), open_=o, high=h, low=l, close=c,
                  mark=_ffill(c), volume=v, rupee_volume=rv, tradable=tradable,
                  meta=dict(cfg, cache=str(cache.relative_to(REPO_ROOT)), source="built"))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, dates=dates, symbols=np.array(present), open=o, high=h, low=l,
                        close=c, mark=panel.mark, volume=v, rupee_volume=rv, tradable=tradable)
    if verbose:
        describe(panel)
    return panel


def describe(p: Panel) -> None:
    live = np.isfinite(p.close)
    print(f"panel   {p.n_bars} sessions x {p.n_symbols} symbols  "
          f"[{p.dates[0]} .. {p.dates[-1]}]  universe={p.meta['universe']}")
    print(f"        {live.mean() * 100:.1f}% of cells carry a bar; "
          f"{p.tradable.mean() * 100:.1f}% are tradable "
          f"(>= Rs {p.meta['min_turnover'] / 1e7:.1f} cr median turnover over "
          f"{p.meta['liquidity_window']} sessions, >= {p.meta['min_history']} bars of history)")
    years = p.dates.astype("datetime64[Y]").astype(int) + 1970
    print("        tradable names by year: " + "  ".join(
        f"{y}:{int(p.tradable[years == y].sum(axis=1).mean())}"
        for y in range(years.min(), years.max() + 1, max((years.max() - years.min()) // 8, 1))))
    print(f"        cache: {p.meta['cache']} ({p.meta['source']})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--universe", default=DEFAULTS["universe"])
    ap.add_argument("--start", default=DEFAULTS["start"])
    ap.add_argument("--end", default=DEFAULTS["end"])
    ap.add_argument("--min-turnover", type=float, default=DEFAULTS["min_turnover"])
    ap.add_argument("--min-history", type=int, default=DEFAULTS["min_history"])
    ap.add_argument("--liquidity-window", type=int, default=DEFAULTS["liquidity_window"])
    ap.add_argument("--fresh", action="store_true", help="ignore any cached panel")
    a = ap.parse_args()
    build(a.universe, a.start, a.end, a.min_turnover, a.min_history, a.liquidity_window,
          use_cache=not a.fresh, verbose=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
