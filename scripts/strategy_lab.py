#!/usr/bin/env python3
"""Agent strategy lab: the harness is fixed, the strategy file is the variable.

Setup in words: every candidate is a monthly long-only signal. The candidate
ranks stocks once per month-end; the lab holds the top-N names through the
next month, charges turnover costs, and scores train vs forward exactly like
auto_research (train selects, forward only judges). The agent changes the
*mechanism* each loop by writing a new `strat_*.py` file, never by touching
this harness.

Candidate contract (`scripts/strat_<name>.py`):
    NEEDS_DAILY = True/False   # whether score() needs the daily long panel
    SPACE = {...}              # signal params this strategy owns (docs only)
    def score(panels, params) -> (scores, regime[, risk])
        panels: px (months x stocks month-end closes), months, cols,
                daily (long symbol/date/OHLCV, only if NEEDS_DAILY), start_i
        scores: months x stocks float array, NaN = ineligible, higher = better
        regime: exposure in [0,1] per month (bool still works: 0/1 cash-or-full,
                so partial tiers like 0.4/0.7/1.0 are expressible per trial)
        risk:   optional dict {trail_k, max_hold} — position exits THIS trial
                tests. Risk settings are searched, never hardcoded doctrine:
                pass them in --params-json or --trail-k/--max-hold flags.

Point-in-time: a holding month starting at months[m] may only use daily bars
with date < months[m] and month-end closes through px[m]. Costs are charged
per replaced name at each rebalance. Years come from month counts. The
universe is today's listing, so survivorship flatters everything — always read
a candidate against its bench and its forward, never alone.

Execution (`--exec`, added after the Loop-21 champion review): the legacy
harness filled every rebalance at the SAME month-end close the signal read and
assumed any name could be bought. On the full board that let the book buy
upper-circuit-locked, illiquid small caps no trader could fill, and the L21
champion's +55% forward fell to about +21% / -39% DD once only those locked
entries were refused. The default `realistic` profile therefore fills at the
next session's open, refuses entries whose execution bar is up-locked
(high == low above the prior close) or traded zero volume, traps exits whose
execution bar is down-locked, requires a INR 50 lakh 20-session median traded
value for new entries, and charges 50 bps round trip plus half a round trip
on exposure changes. `--exec legacy` reproduces the old ledger bit-exactly.
Each profile keeps its own ledger and every best.json is stamped with the
harness (execution model, cost, universe, window, top) it was measured under;
a trial against a best with a different stamp is refused, not ranked.
Known residual: eligibility still requires a finite next-month price (a
look-ahead the L20 audit measured as inert on the legacy champion).

Scoring (Loop-23): the realistic profile ranks on `robust`, the median of 4
contiguous train-fold calmars (DD floored at 5%), so one boom year cannot
carry a candidate; a keep must beat the ledger best by more than its own
noise (sd over 16 reruns that refuse a random 10% of new entries) and beat
the bench on train CAGR. The forward window is blind unless --reveal is
passed, and every reveal is logged; promote_gate.py is the one place a
candidate's forward is revealed and a champion is crowned. Monthly and
execution panels are cached under .cache/strategy_lab/panels/.

Usage:
    python scripts/strategy_lab.py --candidate strat_momentum \
        --params-json '{"lookback":9,"regime_ma":6,"abs_mom":true}' \
        --universe nse_all --top 10
    python scripts/strategy_lab.py --candidate strat_rsi_pullback \
        --params-json '{}' --universe nse_all --top 10 --best-json .cache/strategy_lab/best.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl

from momentum_rotation import performance

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[0]
sys.path.insert(0, str(SCRIPT_DIR))

from auto_research import load_monthly  # reuse the panel loader, not a second one


def load_daily(syms: list[str]) -> pl.DataFrame:
    return (
        pl.scan_parquet(str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet"),
                        hive_partitioning=True)
        .filter(pl.col("symbol").is_in(syms))
        .select("symbol", "date", "open", "high", "low", "close", "volume")
        .collect()
        .sort("symbol", "date")
    )


def monthly_lows(daily: pl.DataFrame, months, cols: list[str]) -> np.ndarray:
    """Intra-month low per (holding month m, stock): daily bars with date in
    [months[m], months[m+1]). Point-in-time safe: month m's low is only read
    while holding through month m, never for the entry decision at months[m].
    """
    lo = (daily.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("low").min()).sort("symbol", "date"))
    piv = lo.pivot(on="symbol", index="date", values="low").sort("date")
    mind = {m: i for i, m in enumerate(months)}
    out = np.full((len(months), len(cols)), np.nan)
    for row in piv.iter_rows(named=True):
        i = mind.get(row["date"])
        if i is None:
            continue
        for j, s in enumerate(cols):
            v = row.get(s)
            if v is not None:
                out[i, j] = v
    return out


def _yearly_returns(curve: np.ndarray, labels) -> dict:
    """Calendar-year returns and month counts from an equity curve. curve[0] is
    the start value; labels[j-1] is the holding month of the step into curve[j]."""
    buckets: dict = {}
    for j in range(1, len(curve)):
        y = labels[j - 1].year
        buckets.setdefault(y, []).append(curve[j] / curve[j - 1] - 1.0)
    return {y: (float(np.prod([1.0 + r for r in rs]) - 1.0), len(rs))
            for y, rs in buckets.items()}


def _consistency(yrs: dict) -> dict:
    """Consistency of a yearly return series. The metrics (worst year,
    dispersion, positive years, best-year share of the window's log-return) are
    computed on COMPLETE calendar years (>= 12 monthly steps) so window-edge
    partial years cannot fake a bad year; every year is still listed in
    `years`."""
    full = {y: v for y, (v, n) in yrs.items() if n >= 12}
    use = full if full else {y: v for y, (v, n) in yrs.items()}
    vals = list(use.values())
    if not vals:
        return {"year_min": 0.0, "year_max": 0.0, "year_std": 0.0,
                "year_pos": 0, "year_n": 0, "best_share": 0.0, "years": {}}
    logs = [float(np.log1p(v)) for v in vals if 1.0 + v > 0]
    best_share = (max(logs) / sum(logs)) if logs and sum(logs) > 0 else 0.0
    return {"year_min": float(min(vals)), "year_max": float(max(vals)),
            "year_std": float(np.std(vals)),
            "year_pos": int(sum(1 for v in vals if v > 0)), "year_n": len(vals),
            "best_share": float(best_share),
            "years": {int(y): float(v) for y, (v, n) in sorted(yrs.items())}}


def exec_panels(daily: pl.DataFrame, months, cols: list[str], fill: str) -> dict:
    """Execution-side panels (months x stocks) for a rebalance DECIDED at the
    close of month t (the bar px[t] is read from):

        price[t]    the price the rebalance trades at. `close` = px[t] itself
                    (same bar as the signal); `next_open` / `next_close` = the
                    open / close of the FIRST trading day of month t+1. A name
                    held across a rebalance is marked price[t] -> price[t+1],
                    so entries, exits and marks all use the same fill clock.
        lock_up[t]  the execution bar cannot be BOUGHT: it printed one price
                    all day (high == low) above the previous close — an
                    upper-circuit lock with no sellers — or traded zero volume.
        lock_dn[t]  the execution bar cannot be SOLD: high == low below the
                    previous close (lower-circuit lock) or zero volume.
        tv20[t]     20-session median traded value (close x volume, INR) as of
                    the last bar of month t — known at decision time.

    high == low is the conservative lock test: a name that trades a range and
    then locks at the band is NOT flagged, so these masks under-count locks.
    """
    d = (daily.sort("symbol", "date")
         .with_columns(pl.col("close").shift(1).over("symbol").alias("pc"),
                       (pl.col("close") * pl.col("volume")).cast(pl.Float64)
                       .rolling_median(20).over("symbol").alias("tv20"),
                       pl.col("date").dt.truncate("1mo").alias("mo"))
         .with_columns(
             (((pl.col("high") == pl.col("low")) & (pl.col("close") > pl.col("pc")))
              | (pl.col("volume") == 0)).fill_null(False).alias("up"),
             (((pl.col("high") == pl.col("low")) & (pl.col("close") < pl.col("pc")))
              | (pl.col("volume") == 0)).fill_null(False).alias("dn")))
    agg = d.group_by("symbol", "mo", maintain_order=True).agg(
        pl.col("open").first().alias("f_open"), pl.col("close").first().alias("f_close"),
        pl.col("up").first().alias("f_up"), pl.col("dn").first().alias("f_dn"),
        pl.col("up").last().alias("l_up"), pl.col("dn").last().alias("l_dn"),
        pl.col("tv20").last().alias("tv20"))
    agg = (agg.join(pl.DataFrame({"mo": months, "i": np.arange(len(months))}), on="mo")
           .join(pl.DataFrame({"symbol": cols, "j": np.arange(len(cols))}), on="symbol"))
    I, J = agg["i"].to_numpy(), agg["j"].to_numpy()
    shape = (len(months), len(cols))

    def mat(col: str, fill_value=np.nan) -> np.ndarray:
        out = np.full(shape, fill_value, dtype=float)
        out[I, J] = agg[col].cast(pl.Float64).fill_null(np.nan).to_numpy()
        return out

    def nxt(a: np.ndarray, fill_value) -> np.ndarray:
        out = np.full_like(a, fill_value)
        out[:-1] = a[1:]
        return out

    tv20 = mat("tv20")
    if fill == "close":
        return {"price": None, "lock_up": mat("l_up", 0.0) > 0.5,
                "lock_dn": mat("l_dn", 0.0) > 0.5, "tv20": tv20}
    key = {"next_open": "f_open", "next_close": "f_close"}[fill]
    return {"price": nxt(mat(key), np.nan), "lock_up": nxt(mat("f_up", 0.0), 0.0) > 0.5,
            "lock_dn": nxt(mat("f_dn", 0.0), 0.0) > 0.5, "tv20": tv20}


def backtest_scores(scores: np.ndarray, regime: np.ndarray, px: np.ndarray,
                    months, start_i: int, split_i: int | None,
                    cost: float, top: int, cols=None,
                    lows: np.ndarray | None = None, risk: dict | None = None,
                    ex: dict | None = None, extra_block: np.ndarray | None = None,
                    folds: int = 0, record_picks: bool = False) -> dict:
    """Monthly book with searchable risk. `regime` is exposure in [0,1] per
    month (bool arrays still work as 0/1 cash-or-full). `risk` selects the
    position machinery for THIS trial — the loop discovers it, nothing here
    is a hardcoded house view:
        trail_k   exit a name whose month low prints below its running
                  month-end-close peak x (1-k). Needs `lows` (months x stocks
                  intra-month lows). Composition effect at monthly marks;
                  fills are NOT modeled tick-by-tick.
        max_hold  drop a name after N months held, however it ranks.

    `ex` is the execution model (None = legacy: fill at the signal close, every
    name fillable, no liquidity floor). Keys: `price` (exec_panels price or
    None for px), `lock_up`/`lock_dn`/`tv20` (exec_panels masks), `min_tv`
    (INR floor on tv20 for NEW entries), `charge_exposure` (charge half a round
    trip on exposure changes of continuing names). With `ex`:
      - a name not already held cannot be ENTERED if its execution bar is
        up-locked or its tv20 is below `min_tv`; the slot goes to the next
        rank, exactly as a trader who could not fill would do;
      - a held name the book wants to drop but whose execution bar is
        down-locked is STUCK: it stays in the book at its previous weight for
        another month, and new picks share only the exposure left over;
      - costs stay a ROUND TRIP per newly bought slot (`cost`), plus
        0.5 x cost x |E - E_prev| on the continuing slots when enabled.

    `extra_block` (months x stocks bool) refuses NEW entries exactly like an
    up-lock — the noise probe uses it to knock out a random share of entries.
    `folds` splits the TRAIN curve into that many contiguous blocks and scores
    each as CAGR / max(|DD|, 5%); `robust` is the median block score (the
    ruler of the realistic profile), `robust_min` the worst. `record_picks`
    adds the held book per decision row (for footprint diffs; never written
    to a ledger).
    """
    risk = risk or {}
    trail_k = risk.get("trail_k")
    max_hold = risk.get("max_hold")
    col_idx = {s: j for j, s in enumerate(cols)} if cols is not None else {}
    n_stocks = px.shape[1]
    if ex is not None and cols is None:
        raise ValueError("an execution model needs `cols`")
    pxe = ex["price"] if ex is not None and ex.get("price") is not None else px
    # a next-day fill needs month t+2's first bar to mark month t+1: the last
    # decision row has no exit price, so the walk stops one row earlier
    t_end = len(months) - 1 if pxe is px else len(months) - 2
    stats = {"would_enter": 0, "blocked_lock": 0, "blocked_tv": 0, "stuck": 0}
    picks_log: dict = {}
    eq, held, peaks, flags = [1.0], {}, {}, []
    weights: dict = {}
    E_prev = 0.0
    for t in range(start_i, t_end):
        E = float(np.clip(regime[t] if t < len(regime) else 1.0, 0.0, 1.0))
        s = scores[t].copy() if t < scores.shape[0] else np.full(n_stocks, np.nan)
        ok = np.isfinite(s) & np.isfinite(pxe[t]) & np.isfinite(pxe[t + 1])
        s[~ok] = np.nan
        excl = set()
        for sym, t0 in held.items():
            j = col_idx.get(sym)
            if j is None or not np.isfinite(pxe[t, j]):
                excl.add(sym)
                continue
            peaks[sym] = max(peaks.get(sym, float("-inf")), float(px[t, j]))
            if max_hold and t - t0 >= max_hold:
                excl.add(sym)
            elif (trail_k and lows is not None and np.isfinite(lows[t, j])
                    and lows[t, j] < peaks[sym] * (1 - trail_k)):
                excl.add(sym)
        for sym in excl:
            j = col_idx.get(sym)
            if j is not None:
                s[j] = np.nan
        if ex is not None:
            held_j = np.array([col_idx[x] for x in held], dtype=int)
            lock = ex["lock_up"][t].copy()
            thin = (~(ex["tv20"][t] >= ex["min_tv"]) if ex.get("min_tv")
                    else np.zeros(n_stocks, dtype=bool))
            lock[held_j] = False
            thin[held_j] = False
            idx0 = np.flatnonzero(np.isfinite(s))
            if E > 0 and len(idx0) >= max(top // 2, 3):
                nat = idx0[np.argsort(-s[idx0], kind="stable")[:top]]
                new_nat = [i for i in nat if cols[i] not in held]
                stats["would_enter"] += len(new_nat)
                stats["blocked_lock"] += int(sum(lock[i] for i in new_nat))
                stats["blocked_tv"] += int(sum(thin[i] and not lock[i] for i in new_nat))
            s[lock | thin] = np.nan
        if extra_block is not None:
            eb = extra_block[t].copy()
            for sym in held:
                eb[col_idx[sym]] = False
            s[eb] = np.nan
        idx = np.flatnonzero(np.isfinite(s))
        pick = set()
        if E > 0 and len(idx) >= max(top // 2, 3):
            order = idx[np.argsort(-s[idx], kind="stable")[:top]]
            pick = {cols[i] for i in order} if cols is not None else set(order.tolist())
        stuck = set()
        if ex is not None:
            for sym in set(held) - pick:
                j = col_idx[sym]
                if (ex["lock_dn"][t, j] and np.isfinite(pxe[t, j])
                        and np.isfinite(pxe[t + 1, j])):
                    stuck.add(sym)
            stats["stuck"] += len(stuck)
        turnover = len(pick - set(held)) / max(len(pick), 1) if pick else 0.0
        c = cost * turnover
        if ex is not None and ex.get("charge_exposure") and pick:
            cont = len(pick & set(held)) / len(pick)
            c += 0.5 * cost * abs(E - E_prev) * cont
        new_w: dict = {}
        if stuck:
            w_stuck = {x: weights.get(x, 0.0) for x in stuck}
            room = max(E - sum(w_stuck.values()), 0.0)
            new_w = {**{x: room / len(pick) for x in pick}, **w_stuck} if pick else w_stuck
            r = sum(w * (pxe[t + 1, col_idx[x]] / pxe[t, col_idx[x]] - 1)
                    for x, w in new_w.items())
            eq.append(eq[-1] * (1 + r) * (1 - c))
            flags.append(sum(new_w.values()))
        elif pick:
            js = [col_idx.get(x, x) for x in pick] if cols is not None else list(pick)
            r = np.nanmean(pxe[t + 1, js] / pxe[t, js]) - 1
            eq.append(eq[-1] * (1 + E * r) * (1 - c))
            flags.append(E)
            new_w = {x: E / len(pick) for x in pick}
        else:
            eq.append(eq[-1])
            flags.append(0.0)
        weights = new_w
        E_prev = E if pick else 0.0
        new_held = {}
        for sym in pick | stuck:
            j = col_idx.get(sym) if cols is not None else sym
            new_held[sym] = held.get(sym, t)
            if np.isfinite(px[t, j]):
                peaks[sym] = max(peaks.get(sym, float("-inf")), float(px[t, j]))
        for sym in list(peaks):
            if sym not in new_held:
                del peaks[sym]
        held = new_held
        if record_picks:  # (book, exposure): a regime change is a footprint too
            picks_log[t] = (sorted(new_held), round(flags[-1], 6))

    curve = np.array(eq)
    flags = np.array(flags)
    labels = [months[start_i + j] for j in range(1, len(curve))]
    if split_i is None:
        cons = _consistency(_yearly_returns(curve, labels))
    else:
        k0 = split_i - start_i
        cons = _consistency(_yearly_returns(curve[:k0 + 1], labels[:k0]))
    # equal-weight bench of names alive at the test start
    alive = ~np.isnan(px[start_i])
    idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
    bench = idx[start_i:] / idx[start_i]
    bench = bench[:len(curve)]  # same window as the book (next-day fills end a row early)

    def seg(x: np.ndarray):
        normed = x / x[0]
        n = len(normed) - 1
        return performance(normed, n / 12) if n > 0 else (0.0, 0.0)

    full_cagr, full_dd = seg(curve)
    bench_cagr, bench_dd = seg(bench)
    if split_i is None:
        mid = len(curve) // 2
        h1, _ = seg(curve[:mid])
        h2, _ = seg(curve[mid - 1:])
        rdd = abs(full_cagr / full_dd) if full_dd else 0.0
        return {**cons, "exec_stats": stats, "cagr": float(full_cagr), "maxdd": float(full_dd), "ret_dd": float(rdd),
                "h1_cagr": float(h1), "h2_cagr": float(h2),
                "bench_cagr": float(bench_cagr), "bench_dd": float(bench_dd),
                "invested": float(flags.mean()) if len(flags) else 0.0,
                "months": len(curve) - 1, "fwd_cagr": float(full_cagr),
                "fwd_dd": float(full_dd), "fwd_bench_cagr": float(bench_cagr),
                "fwd_bench_dd": float(bench_dd), "fwd_months": len(curve) - 1,
                "full_cagr": float(full_cagr), "full_dd": float(full_dd)}

    k = split_i - start_i
    extra: dict = {}
    if record_picks:
        extra["picks"] = picks_log
    if folds:
        edges = np.linspace(0, k, folds + 1).round().astype(int)
        fc, fd, fs, bsc = [], [], [], []
        for a, b in zip(edges[:-1], edges[1:]):
            c_, d_ = seg(curve[a:b + 1])
            bc_, bd_ = seg(bench[a:b + 1])
            fc.append(float(c_))
            fd.append(float(d_))
            fs.append(float(c_ / max(abs(d_), 0.05)))
            bsc.append(float(bc_ / max(abs(bd_), 0.05)))
        extra.update({"fold_cagr": fc, "fold_dd": fd, "fold_score": fs,
                      "robust": float(np.median(fs)), "robust_min": float(min(fs)),
                      "bench_robust": float(np.median(bsc))})
    train_cagr, train_dd = seg(curve[: k + 1])
    test_cagr, test_dd = seg(curve[k:] / curve[k])
    btrain_cagr, btrain_dd = seg(bench[: k + 1])
    btest_cagr, btest_dd = seg(bench[k:] / bench[k])
    train = curve[: k + 1]
    mid = len(train) // 2
    h1, _ = seg(train[:mid])
    h2, _ = seg(train[mid - 1:])
    rdd = abs(train_cagr / train_dd) if train_dd else 0.0
    return {**cons, **extra, "exec_stats": stats, "cagr": float(train_cagr), "maxdd": float(train_dd), "ret_dd": float(rdd),
            "h1_cagr": float(h1), "h2_cagr": float(h2),
            "bench_cagr": float(btrain_cagr), "bench_dd": float(btrain_dd),
            "invested": float(flags[:k].mean()) if k else 0.0, "months": len(train) - 1,
            "fwd_cagr": float(test_cagr), "fwd_dd": float(test_dd),
            "fwd_bench_cagr": float(btest_cagr), "fwd_bench_dd": float(btest_dd),
            "fwd_months": len(curve) - 1 - k,
            "full_cagr": float(full_cagr), "full_dd": float(full_dd)}


EXEC_PROFILES = {
    # the pre-L22 harness: fill at the signal close, every name fillable, no
    # liquidity floor, train-CAGR ruler, forward printed on every trial. Kept
    # so the old ledger stays reproducible — its numbers are an UPPER BOUND,
    # not an achievable return.
    "legacy": {"fill": "close", "lock_block": False, "min_tv": 0.0, "cost_bps": 25.0,
               "charge_exposure": False, "select": "cagr", "folds": 0,
               "noise_seeds": 0, "noise_rate": 0.10, "noise_k": 0.0, "blind": False,
               "results": ".cache/strategy_lab/results.tsv",
               "best_json": ".cache/strategy_lab/best.json"},
    # next-session open fill, circuit locks refuse entries (and trap exits),
    # INR 50 lakh/day liquidity floor on new entries, 50 bps round trip.
    # Ruler = median of 4 train-fold calmars (DD floored at 5%); a keep must
    # beat the best by its own perturbation noise; forward is BLIND unless
    # --reveal is passed (and every reveal is logged).
    "realistic": {"fill": "next_open", "lock_block": True, "min_tv": 5e6, "cost_bps": 50.0,
                  "charge_exposure": True, "select": "robust", "folds": 4,
                  "noise_seeds": 16, "noise_rate": 0.10, "noise_k": 1.0, "blind": True,
                  "results": ".cache/strategy_lab/results_real.tsv",
                  "best_json": ".cache/strategy_lab/best_real.json"},
}
STAMP_KEYS = ("fill", "lock_block", "min_tv", "cost_bps", "charge_exposure", "select",
              "folds", "noise_seeds", "noise_rate", "noise_k")
RULER = {"cagr": "cagr", "calmar": "ret_dd", "robust": "robust"}
PANEL_CACHE = REPO_ROOT / ".cache" / "strategy_lab" / "panels"
REVEALS = REPO_ROOT / ".cache" / "strategy_lab" / "reveals.tsv"


def is_legacy_exec(prof: dict) -> bool:
    return (prof["fill"] == "close" and not prof["lock_block"]
            and not prof["min_tv"] and not prof["charge_exposure"])


def data_fingerprint() -> str:
    """Cheap identity of the committed inputs: path + size of every daily
    partition and the universe file. A data refresh changes it, so a stale
    panel cache can never be read against new data."""
    h = hashlib.sha1()
    files = sorted((REPO_ROOT / "data" / "ohlcv" / "daily").glob("year=*/*.parquet"))
    files.append(REPO_ROOT / "data" / "universe" / "nse_universe.parquet")
    for f in files:
        h.update(f"{f.relative_to(REPO_ROOT)}:{f.stat().st_size};".encode())
    return h.hexdigest()[:12]


def load_monthly_cached(universe: str, start: str):
    """auto_research.load_monthly, memoised to .cache/strategy_lab/panels/
    (the monthly pivot is ~12 s of every trial). Bit-identical arrays."""
    PANEL_CACHE.mkdir(parents=True, exist_ok=True)
    f = PANEL_CACHE / f"monthly_{universe}_{data_fingerprint()}.npz"
    if f.exists():
        z = np.load(f, allow_pickle=False)
        px = z["px"]
        months = [date.fromordinal(int(o)) for o in z["months"]]
        cols = z["cols"].tolist()
    else:
        px, months, cols, _ = load_monthly(universe, "1900-01-01")
        np.savez(f, px=px, months=np.array([m.toordinal() for m in months]),
                 cols=np.array(cols))
    start_i = next(i for i, mm in enumerate(months) if str(mm) >= start)
    return px, months, cols, start_i


def exec_panels_cached(daily, months, cols, fill: str, universe: str) -> dict:
    PANEL_CACHE.mkdir(parents=True, exist_ok=True)
    f = PANEL_CACHE / f"exec_{universe}_{data_fingerprint()}_{fill}.npz"
    if f.exists():
        z = np.load(f, allow_pickle=False)
        return {"price": z["price"] if z["price"].size else None, "lock_up": z["lock_up"],
                "lock_dn": z["lock_dn"], "tv20": z["tv20"]}
    ex = exec_panels(daily, months, cols, fill)
    np.savez(f, price=ex["price"] if ex["price"] is not None else np.empty(0),
             lock_up=ex["lock_up"], lock_dn=ex["lock_dn"], tv20=ex["tv20"])
    return ex


def build_context(universe: str, start: str, split: str | None, prof: dict,
                  need_daily: bool) -> dict:
    """Everything a trial needs that does not depend on the candidate."""
    px, months, cols, start_i = load_monthly_cached(universe, start)
    split_i = None
    if split:
        split_i = next((i for i, mm in enumerate(months) if str(mm) >= split), None)
        if split_i is None or not (start_i < split_i < len(months) - 1):
            raise SystemExit(f"--split {split} outside range")
    legacy_exec = is_legacy_exec(prof)
    daily = None
    if need_daily or not legacy_exec:
        u = pl.read_parquet(REPO_ROOT / "data" / "universe" / "nse_universe.parquet")
        syms = u["symbol"].to_list() if universe == "nse_all" else \
            u.filter(pl.col(f"in_{universe}"))["symbol"].to_list()
        daily = load_daily(syms)
    ex = None
    if not legacy_exec:
        ex = dict(exec_panels_cached(daily, months, cols, prof["fill"], universe))
        if not prof["lock_block"]:
            ex["lock_up"] = np.zeros_like(ex["lock_up"])
            ex["lock_dn"] = np.zeros_like(ex["lock_dn"])
        ex["min_tv"] = float(prof["min_tv"] or 0.0)
        ex["charge_exposure"] = bool(prof["charge_exposure"])
    return {"px": px, "months": months, "cols": cols, "start_i": start_i,
            "split_i": split_i, "daily": daily, "ex": ex, "universe": universe}


def score_candidate(mod, params: dict, ctx: dict, risk_cli: dict | None = None):
    panels = {"px": ctx["px"], "months": ctx["months"], "cols": ctx["cols"],
              "daily": ctx["daily"], "start_i": ctx["start_i"]}
    out = mod.score(panels, params)
    risk = dict(risk_cli or {"trail_k": None, "max_hold": None})
    if len(out) > 2 and out[2]:
        risk.update(out[2])
    for k in ("trail_k", "max_hold"):
        if k in params:
            risk[k] = params[k]
    lows = None
    if risk.get("trail_k"):
        if ctx["daily"] is None:
            raise SystemExit("trail_k needs the daily panel")
        lows = monthly_lows(ctx["daily"], ctx["months"], ctx["cols"])
    return np.asarray(out[0], dtype=float), np.asarray(out[1], dtype=float), risk, lows


def run_book(scored, ctx: dict, top: int, cost: float, folds: int, **kw) -> dict:
    scores, regime, risk, lows = scored
    return backtest_scores(scores, regime, ctx["px"], ctx["months"], ctx["start_i"],
                           ctx["split_i"], cost, top, cols=ctx["cols"], lows=lows,
                           risk=risk, ex=ctx["ex"], folds=folds, **kw)


def noise_probe(scored, ctx: dict, top: int, cost: float, folds: int, key: str,
                seeds: int, rate: float) -> list[float]:
    """Re-run the book `seeds` times with a random `rate` share of cells
    refused as NEW entries (held names untouched) and return the ruler value
    of each run. Its spread is the trial's own noise floor: a gain smaller
    than it is indistinguishable from a different random pick set."""
    vals = []
    for sd in range(seeds):
        mask = np.random.default_rng(sd).random(ctx["px"].shape) < rate
        vals.append(float(run_book(scored, ctx, top, cost, folds, extra_block=mask)[key]))
    return vals


def log_reveal(candidate: str, params: dict, ledger: str, why: str) -> int:
    """Append one forward reveal to the reveal log and return the running
    count. The forward window is a holdout only while this stays small."""
    REVEALS.parent.mkdir(parents=True, exist_ok=True)
    if not REVEALS.exists():
        REVEALS.write_text("ts\tcandidate\tparams\tledger\twhy\n")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(REVEALS, "a") as f:
        f.write(f"{ts}\t{candidate}\t{json.dumps(params, sort_keys=True)}\t{ledger}\t{why}\n")
    return sum(1 for _ in open(REVEALS)) - 1


def strip_forward(m: dict) -> dict:
    return {k: v for k, v in m.items() if not k.startswith(("fwd_", "full_"))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", required=True, help="strat_* module name, no .py")
    ap.add_argument("--params-json", default="{}")
    ap.add_argument("--universe", default="nse_all")
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--split", default="2022-01-01")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--exec", dest="exec_profile", choices=sorted(EXEC_PROFILES),
                    default="realistic",
                    help="execution + scoring profile: 'realistic' (default) fills at "
                         "the next session's open, refuses circuit-locked entries/exits "
                         "and names under the liquidity floor, ranks on the median "
                         "train-fold calmar with a noise-calibrated margin, and keeps "
                         "the forward window blind; 'legacy' reproduces the pre-L22 "
                         "harness. Each profile has its own default ledger.")
    ap.add_argument("--fill", choices=["close", "next_open", "next_close"], default=None,
                    help="override the profile's fill price")
    ap.add_argument("--min-tv", type=float, default=None,
                    help="override the profile's liquidity floor: minimum 20-session "
                         "median traded value (INR) for a NEW entry; 0 disables")
    ap.add_argument("--lock-block", action=argparse.BooleanOptionalAction, default=None,
                    help="override the profile's circuit-lock handling")
    ap.add_argument("--cost-bps", type=float, default=None,
                    help="ROUND-TRIP cost per newly bought slot, bps (profile default: "
                         "legacy 25, realistic 50 = ~22 statutory STT/stamp/exchange + "
                         "~28 spread/impact)")
    ap.add_argument("--select", choices=sorted(RULER), default=None,
                    help="keep ruler (profile default: legacy cagr, realistic robust = "
                         "median train-fold calmar). Stamped into the ledger.")
    ap.add_argument("--folds", type=int, default=None,
                    help="contiguous train folds for the robust ruler (profile default)")
    ap.add_argument("--noise-seeds", type=int, default=None,
                    help="random-entry-block reruns that measure the trial's noise "
                         "floor (0 disables; profile default)")
    ap.add_argument("--reveal", action="store_true",
                    help="print and store forward numbers for this trial. Logged to "
                         f"{REVEALS.relative_to(REPO_ROOT)}; loops should leave it off "
                         "and let promote_gate.py reveal once per promotion.")
    ap.add_argument("--reveal-why", default="manual",
                    help="reason recorded in the reveal log")
    ap.add_argument("--max-dd", type=float, default=70.0)
    ap.add_argument("--dd-slack", type=float, default=2.0)
    ap.add_argument("--min-delta", type=float, default=0.05,
                    help="minimum improvement in ruler units (cagr: pp); the "
                         "realistic profile also requires noise_k x the trial's "
                         "noise sd, whichever is larger")
    ap.add_argument("--cagr-guard", type=float, default=0.5,
                    help="calmar mode only: reject if train CAGR trails best by "
                         "more than Xpp (stops cash-like winners)")
    ap.add_argument("--year-floor", type=float, default=None,
                    help="consistency guard: reject a keep whose WORST calendar-year "
                         "train return is below X percent (e.g. 0 = no losing years).")
    ap.add_argument("--year-std-max", type=float, default=None,
                    help="consistency guard: reject a keep whose calendar-year train "
                         "return stdev exceeds X percent.")
    ap.add_argument("--trail-k", type=float, default=None,
                    help="default trailing-stop fraction, overridden per trial by "
                         "params-json trail_k or the candidate's risk dict")
    ap.add_argument("--max-hold", type=int, default=None,
                    help="default max months held, overridden like --trail-k")
    ap.add_argument("--results", default=None,
                    help="default: the profile's ledger (legacy results.tsv, "
                         "realistic results_real.tsv)")
    ap.add_argument("--best-json", default=None,
                    help="default: the profile's best (legacy best.json, realistic "
                         "best_real.json)")
    args = ap.parse_args()

    prof = dict(EXEC_PROFILES[args.exec_profile])
    for k, v in (("fill", args.fill), ("min_tv", args.min_tv),
                 ("lock_block", args.lock_block), ("cost_bps", args.cost_bps),
                 ("select", args.select), ("folds", args.folds),
                 ("noise_seeds", args.noise_seeds)):
        if v is not None:
            prof[k] = v
    if prof["select"] == "robust" and not prof["folds"]:
        raise SystemExit("--select robust needs --folds > 0")
    harness = {"exec": args.exec_profile, **{k: prof[k] for k in STAMP_KEYS},
               "universe": args.universe, "start": args.start, "split": args.split,
               "top": args.top}
    if args.exec_profile == "legacy":
        # the legacy stamp predates the ruler/fold/noise keys; keep it as it was
        for k in ("select", "folds", "noise_seeds", "noise_rate", "noise_k"):
            harness.pop(k)
    args.results = args.results or prof["results"]
    args.best_json = args.best_json or prof["best_json"]
    legacy_exec = is_legacy_exec(prof)
    blind = prof["blind"] and not args.reveal
    params = json.loads(args.params_json)
    cost = prof["cost_bps"] / 10_000
    results_path = REPO_ROOT / args.results
    best_path = REPO_ROOT / args.best_json
    results_path.parent.mkdir(parents=True, exist_ok=True)

    mod = importlib.import_module(args.candidate)
    print(f"loading panels ({args.universe} from {args.start}) ...", flush=True)
    want_trail = args.trail_k is not None or "trail_k" in params
    ctx = build_context(args.universe, args.start, args.split, prof,
                        getattr(mod, "NEEDS_DAILY", False) or want_trail)
    print(f"scoring with {args.candidate} {params} ...", flush=True)
    scored = score_candidate(mod, params, ctx,
                             {"trail_k": args.trail_k, "max_hold": args.max_hold})
    risk = scored[2]
    folds = int(prof["folds"] or 0)
    m = run_book(scored, ctx, args.top, cost, folds)
    ruler = RULER[prof["select"]]
    noise = []
    if prof["noise_seeds"] and ctx["split_i"] is not None:
        noise = noise_probe(scored, ctx, args.top, cost, folds, ruler,
                            int(prof["noise_seeds"]), float(prof["noise_rate"]))
        m["noise_sd"] = float(np.std(noise, ddof=1))
        m["noise_p10"] = float(np.percentile(noise, 10))
    n_trial = (sum(1 for _ in open(results_path)) if results_path.exists() else 1)
    if not blind and prof["blind"]:
        n_rev = log_reveal(args.candidate, params, str(args.results), args.reveal_why)
        print(f"REVEAL logged (#{n_rev} in {REVEALS.relative_to(REPO_ROOT)})")

    risk_note = "".join(f" {k}={v}" for k, v in risk.items() if v is not None) or " none"
    fwd_txt = ("FWD [blind]" if blind else
               f"FWD {m['fwd_cagr']*100:+.2f}% DD {m['fwd_dd']*100:.2f}%")
    bench_txt = (f"train bench {m['bench_cagr']*100:+.2f}%" if blind else
                 f"train bench {m['bench_cagr']*100:+.2f}% | fwd bench "
                 f"{m['fwd_bench_cagr']*100:+.2f}%")
    print(f"TRAIN {m['cagr']*100:+.2f}% DD {m['maxdd']*100:.2f}% ret/DD {m['ret_dd']:.2f} "
          f"H1 {m['h1_cagr']*100:+.1f}% H2 {m['h2_cagr']*100:+.1f}% inv {m['invested']*100:.0f}% "
          f"| {fwd_txt} ({bench_txt})")
    print("YEARS " + " ".join(f"{y}:{v*100:+.0f}%" for y, v in sorted(m["years"].items()))
          + f" | min {m['year_min']*100:+.1f}% std {m['year_std']*100:.1f}% "
          + f"pos {m['year_pos']}/{m['year_n']} best-share {m['best_share']*100:.0f}%")
    if folds:
        print("FOLDS " + " ".join(f"{c*100:+.1f}/{d*100:.1f}({sc:.2f})" for c, d, sc in
                                  zip(m["fold_cagr"], m["fold_dd"], m["fold_score"]))
              + f" | robust {m['robust']:.3f} min {m['robust_min']:.3f} "
              + f"(bench {m['bench_robust']:.3f})")
    if noise:
        print(f"NOISE {len(noise)} seeds x {prof['noise_rate']:.0%} entry block | "
              f"{prof['select']} sd {m['noise_sd']:.3f} p10 {m['noise_p10']:.3f} "
              f"| trial #{n_trial} in this ledger")
    xs = m["exec_stats"]
    exec_tag = (f"exec:{args.exec_profile} fill={prof['fill']} lock={int(bool(prof['lock_block']))} "
                f"min_tv={prof['min_tv']:g} cost={prof['cost_bps']:g}rt "
                f"expo={int(bool(prof['charge_exposure']))}")
    print(f"EXEC {exec_tag} | would-enter {xs['would_enter']} blocked-lock "
          f"{xs['blocked_lock']} blocked-tv {xs['blocked_tv']} stuck-exits {xs['stuck']}")

    status, note = "baseline", "first entry"
    unit = "%" if ruler == "cagr" else ""
    scale = 100 if ruler == "cagr" else 1
    if best_path.exists():
        best = json.loads(best_path.read_text())
        # one harness version per ledger: never rank a trial against a best
        # measured under a different execution model, cost, ruler, window or top-N
        if best.get("harness") is None and not (legacy_exec and prof["cost_bps"] == 25.0):
            raise SystemExit(f"{best_path} has no harness stamp (a pre-L22 legacy "
                             f"ledger); only the unmodified legacy harness may rank against it — "
                             f"use another --best-json")
        if best.get("harness") is not None and best["harness"] != harness:
            raise SystemExit(f"{best_path} was measured under harness "
                             f"{best['harness']}, this run is {harness} — "
                             f"use a matching ledger")
        b = best["metrics"]
        floor = min(-abs(args.max_dd) / 100, b["maxdd"])
        margin = args.min_delta / scale
        if noise:
            margin = max(margin, float(prof["noise_k"]) * m["noise_sd"])
        lead_ok = m[ruler] > b[ruler] + margin
        guard_ok = True
        if prof["select"] == "calmar":
            guard_ok = m["cagr"] >= b["cagr"] - args.cagr_guard / 100
        elif prof["select"] == "robust":
            guard_ok = m["cagr"] > m["bench_cagr"]  # a cash-like book cannot win
        dd_ok = m["maxdd"] >= floor and m["maxdd"] >= b["maxdd"] - args.dd_slack / 100
        robust = m["h1_cagr"] > 0 and m["h2_cagr"] > 0
        year_ok, year_why = True, ""
        if args.year_floor is not None and m["year_min"] < args.year_floor / 100:
            year_ok, year_why = False, (f"worst year {m['year_min']*100:+.1f}% < "
                                        f"floor {args.year_floor:g}%")
        elif args.year_std_max is not None and m["year_std"] > args.year_std_max / 100:
            year_ok, year_why = False, (f"year std {m['year_std']*100:.1f}% > "
                                        f"{args.year_std_max:g}%")
        if lead_ok and guard_ok and dd_ok and robust and year_ok:
            status, note = "keep", (f"beats best on {prof['select']} by "
                                    f"{(m[ruler]-b[ruler])*scale:.3f}{unit} > margin "
                                    f"{margin*scale:.3f}{unit}")
        else:
            if not robust:
                note = "fails train half"
            elif not lead_ok:
                note = (f"TRAIN {m[ruler]*scale:.3f}{unit} <= best "
                        f"{b[ruler]*scale:.3f}{unit} + margin {margin*scale:.3f}{unit} "
                        f"[{prof['select']}]")
            elif not guard_ok:
                note = (f"CAGR {m['cagr']*100:.2f}% trails best by >{args.cagr_guard:g}pp"
                        if prof["select"] == "calmar" else
                        f"CAGR {m['cagr']*100:.2f}% <= bench {m['bench_cagr']*100:.2f}%")
            elif not year_ok:
                note = year_why
            else:
                note = f"DD {m['maxdd']*100:.1f}% breaches floor/slack"
            status = "discard"
    stored = strip_forward(m) if blind else m
    if status in ("baseline", "keep"):
        best_path.write_text(json.dumps(
            {"candidate": args.candidate, "params": params, "top": args.top,
             "harness": harness,
             "select": prof["select"], "risk": {k: v for k, v in risk.items()
                                                if v is not None},
             "metrics": stored}, indent=2))
    if not results_path.exists():
        results_path.write_text("ts\tstatus\tcandidate\tparams\ttop\ttrain_cagr\ttrain_dd\t"
                                "ret_dd\th1\th2\tfwd_cagr\tfwd_dd\tfwd_bench\tnote\n")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fwd_cols = ("blind\tblind\tblind" if blind else
                f"{m['fwd_cagr']*100:.3f}\t{m['fwd_dd']*100:.3f}\t{m['fwd_bench_cagr']*100:.3f}")
    extra_note = ""
    if folds:
        extra_note += f" robust={m['robust']:.3f} rmin={m['robust_min']:.3f}"
    if noise:
        extra_note += f" noise_sd={m['noise_sd']:.3f}"
    with open(results_path, "a") as f:
        f.write(f"{ts}\t{status}\t{args.candidate}\t{json.dumps(params, sort_keys=True)}\t"
                f"{args.top}\t{m['cagr']*100:.3f}\t{m['maxdd']*100:.3f}\t{m['ret_dd']:.3f}\t"
                f"{m['h1_cagr']*100:.3f}\t{m['h2_cagr']*100:.3f}\t{fwd_cols}\t"
                f"{note} [risk:{risk_note.strip()} select:{prof['select']} {exec_tag} "
                f"minyr={m['year_min']*100:.1f} ystd={m['year_std']*100:.1f}{extra_note}]\n")
    if blind:
        print(f"{status.upper()}: {note} | forward blind — promote_gate.py reveals it once")
    else:
        print(f"{status.upper()}: {note} | forward {'PASSES' if m['fwd_cagr'] > 0 else 'FAILS'} "
              f"(never drove selection)")
        dd_flag = "" if m['fwd_dd'] >= m['fwd_bench_dd'] else " [WARN fwd DD worse than bench]"
        print(f"forward DD {m['fwd_dd']*100:.2f}% vs bench {m['fwd_bench_dd']*100:.2f}%{dd_flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
