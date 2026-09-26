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

Usage:
    python scripts/strategy_lab.py --candidate strat_momentum \
        --params-json '{"lookback":9,"regime_ma":6,"abs_mom":true}' \
        --universe nse_all --top 10
    python scripts/strategy_lab.py --candidate strat_rsi_pullback \
        --params-json '{}' --universe nse_all --top 10 --best-json .cache/strategy_lab/best.json
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from datetime import datetime, timezone
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
                    ex: dict | None = None) -> dict:
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
    train_cagr, train_dd = seg(curve[: k + 1])
    test_cagr, test_dd = seg(curve[k:] / curve[k])
    btrain_cagr, btrain_dd = seg(bench[: k + 1])
    btest_cagr, btest_dd = seg(bench[k:] / bench[k])
    train = curve[: k + 1]
    mid = len(train) // 2
    h1, _ = seg(train[:mid])
    h2, _ = seg(train[mid - 1:])
    rdd = abs(train_cagr / train_dd) if train_dd else 0.0
    return {**cons, "exec_stats": stats, "cagr": float(train_cagr), "maxdd": float(train_dd), "ret_dd": float(rdd),
            "h1_cagr": float(h1), "h2_cagr": float(h2),
            "bench_cagr": float(btrain_cagr), "bench_dd": float(btrain_dd),
            "invested": float(flags[:k].mean()) if k else 0.0, "months": len(train) - 1,
            "fwd_cagr": float(test_cagr), "fwd_dd": float(test_dd),
            "fwd_bench_cagr": float(btest_cagr), "fwd_bench_dd": float(btest_dd),
            "fwd_months": len(curve) - 1 - k,
            "full_cagr": float(full_cagr), "full_dd": float(full_dd)}


EXEC_PROFILES = {
    # the pre-L22 harness: fill at the signal close, every name fillable, no
    # liquidity floor. Kept so the old ledger stays reproducible — its numbers
    # are an UPPER BOUND, not an achievable return.
    "legacy": {"fill": "close", "lock_block": False, "min_tv": 0.0, "cost_bps": 25.0,
               "charge_exposure": False, "results": ".cache/strategy_lab/results.tsv",
               "best_json": ".cache/strategy_lab/best.json"},
    # next-session open fill, circuit locks refuse entries (and trap exits),
    # INR 50 lakh/day liquidity floor on new entries, 50 bps round trip
    "realistic": {"fill": "next_open", "lock_block": True, "min_tv": 5e6, "cost_bps": 50.0,
                  "charge_exposure": True, "results": ".cache/strategy_lab/results_real.tsv",
                  "best_json": ".cache/strategy_lab/best_real.json"},
}


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
                    help="execution model: 'realistic' (default) fills at the next "
                         "session's open, refuses circuit-locked entries/exits and "
                         "names under the liquidity floor; 'legacy' reproduces the "
                         "pre-L22 harness (fill at the signal close, all fillable). "
                         "Each profile has its own default ledger.")
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
    ap.add_argument("--max-dd", type=float, default=70.0)
    ap.add_argument("--dd-slack", type=float, default=2.0)
    ap.add_argument("--min-delta", type=float, default=0.05,
                    help="required improvement in --select units to accept")
    ap.add_argument("--select", choices=["cagr", "calmar"], default="cagr",
                    help="keep ruler: raw train CAGR or risk-adjusted ret/DD. "
                         "Fixed per ledger so trials stay comparable; the loop "
                         "discovers risk SETTINGS, not the ruler.")
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
                 ("lock_block", args.lock_block), ("cost_bps", args.cost_bps)):
        if v is not None:
            prof[k] = v
    harness = {"exec": args.exec_profile, **prof, "universe": args.universe,
               "start": args.start, "split": args.split, "top": args.top}
    args.results = args.results or prof.pop("results")
    args.best_json = args.best_json or prof.pop("best_json")
    harness.pop("results", None)
    harness.pop("best_json", None)
    legacy_exec = (prof["fill"] == "close" and not prof["lock_block"]
                   and not prof["min_tv"] and not prof["charge_exposure"])
    params = json.loads(args.params_json)
    cost = prof["cost_bps"] / 10_000
    results_path = REPO_ROOT / args.results
    best_path = REPO_ROOT / args.best_json
    results_path.parent.mkdir(parents=True, exist_ok=True)

    mod = importlib.import_module(args.candidate)
    print(f"loading monthly panel ({args.universe} from {args.start}) ...", flush=True)
    px, months, cols, start_i = load_monthly(args.universe, args.start)
    split_i = None
    if args.split:
        split_i = next((i for i, mm in enumerate(months) if str(mm) >= args.split), None)
        if split_i is None or not (start_i < split_i < len(months) - 1):
            raise SystemExit(f"--split {args.split} outside range")
    daily = None
    want_trail = args.trail_k is not None or "trail_k" in params
    if getattr(mod, "NEEDS_DAILY", False) or want_trail or not legacy_exec:
        print("loading daily long panel for candidate ...", flush=True)
        u = pl.read_parquet(REPO_ROOT / "data" / "universe" / "nse_universe.parquet")
        syms = u["symbol"].to_list() if args.universe == "nse_all" else \
            u.filter(pl.col(f"in_{args.universe}"))["symbol"].to_list()
        daily = load_daily(syms)
    panels = {"px": px, "months": months, "cols": cols, "daily": daily, "start_i": start_i}

    print(f"scoring with {args.candidate} {params} ...", flush=True)
    out = mod.score(panels, params)
    scores, regime = out[0], out[1]
    risk = {"trail_k": args.trail_k, "max_hold": args.max_hold}
    if len(out) > 2 and out[2]:
        risk.update(out[2])
    if "trail_k" in params:
        risk["trail_k"] = params["trail_k"]
    if "max_hold" in params:
        risk["max_hold"] = params["max_hold"]
    lows = None
    if risk.get("trail_k") and daily is not None:
        print("building monthly lows for trailing stop ...", flush=True)
        lows = monthly_lows(daily, months, cols)
    ex = None
    if not legacy_exec:
        print(f"building execution panels (fill {prof['fill']}) ...", flush=True)
        ex = exec_panels(daily, months, cols, prof["fill"])
        if not prof["lock_block"]:
            ex["lock_up"] = np.zeros_like(ex["lock_up"])
            ex["lock_dn"] = np.zeros_like(ex["lock_dn"])
        ex["min_tv"] = float(prof["min_tv"] or 0.0)
        ex["charge_exposure"] = bool(prof["charge_exposure"])
    m = backtest_scores(np.asarray(scores, dtype=float), np.asarray(regime, dtype=float),
                        px, months, start_i, split_i, cost, args.top,
                        cols=cols, lows=lows, risk=risk, ex=ex)
    risk_note = "".join(f" {k}={v}" for k, v in risk.items() if v is not None) or " none"
    print(f"TRAIN {m['cagr']*100:+.2f}% DD {m['maxdd']*100:.2f}% ret/DD {m['ret_dd']:.2f} "
          f"H1 {m['h1_cagr']*100:+.1f}% H2 {m['h2_cagr']*100:+.1f}% inv {m['invested']*100:.0f}% "
          f"| FWD {m['fwd_cagr']*100:+.2f}% DD {m['fwd_dd']*100:.2f}% "
          f"(train bench {m['bench_cagr']*100:+.2f}% | fwd bench {m['fwd_bench_cagr']*100:+.2f}%)")
    print("YEARS " + " ".join(f"{y}:{v*100:+.0f}%" for y, v in sorted(m["years"].items()))
          + f" | min {m['year_min']*100:+.1f}% std {m['year_std']*100:.1f}% "
          + f"pos {m['year_pos']}/{m['year_n']} best-share {m['best_share']*100:.0f}%")
    xs = m["exec_stats"]
    exec_tag = (f"exec:{args.exec_profile} fill={prof['fill']} lock={int(bool(prof['lock_block']))} "
                f"min_tv={prof['min_tv']:g} cost={prof['cost_bps']:g}rt "
                f"expo={int(bool(prof['charge_exposure']))}")
    print(f"EXEC {exec_tag} | would-enter {xs['would_enter']} blocked-lock "
          f"{xs['blocked_lock']} blocked-tv {xs['blocked_tv']} stuck-exits {xs['stuck']}")

    status, note = "baseline", "first entry"
    ruler = "ret_dd" if args.select == "calmar" else "cagr"
    unit = "" if args.select == "calmar" else "%"
    if best_path.exists():
        best = json.loads(best_path.read_text())
        # one harness version per ledger: never rank a trial against a best
        # measured under a different execution model, cost, window or top-N
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
        lead_ok = m[ruler] > b[ruler] + args.min_delta / (100 if ruler == "cagr" else 1)
        guard_ok = True
        if args.select == "calmar":
            guard_ok = m["cagr"] >= b["cagr"] - args.cagr_guard / 100
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
            status, note = "keep", f"beats best on {args.select}"
        else:
            if not robust:
                note = "fails train half"
            elif not lead_ok:
                note = (f"TRAIN {m[ruler]*100:.2f}{unit} <= "
                        f"best {b[ruler]*100:.2f}{unit} [{args.select}]")
            elif not guard_ok:
                note = f"CAGR {m['cagr']*100:.2f}% trails best by >{args.cagr_guard:g}pp"
            elif not year_ok:
                note = year_why
            else:
                note = f"DD {m['maxdd']*100:.1f}% breaches floor/slack"
            status = "discard"
    if status in ("baseline", "keep"):
        best_path.write_text(json.dumps(
            {"candidate": args.candidate, "params": params, "top": args.top,
             "harness": harness,
             "select": args.select, "risk": {k: v for k, v in risk.items()
                                             if v is not None},
             "metrics": m}, indent=2))
    if not results_path.exists():
        results_path.write_text("ts\tstatus\tcandidate\tparams\ttop\ttrain_cagr\ttrain_dd\t"
                                "ret_dd\th1\th2\tfwd_cagr\tfwd_dd\tfwd_bench\tnote\n")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(results_path, "a") as f:
        f.write(f"{ts}\t{status}\t{args.candidate}\t{json.dumps(params, sort_keys=True)}\t"
                f"{args.top}\t{m['cagr']*100:.3f}\t{m['maxdd']*100:.3f}\t{m['ret_dd']:.3f}\t"
                f"{m['h1_cagr']*100:.3f}\t{m['h2_cagr']*100:.3f}\t{m['fwd_cagr']*100:.3f}\t"
                f"{m['fwd_dd']*100:.3f}\t{m['fwd_bench_cagr']*100:.3f}\t"
                f"{note} [risk:{risk_note.strip()} select:{args.select} {exec_tag} "
                f"minyr={m['year_min']*100:.1f} ystd={m['year_std']*100:.1f}]\n")
    print(f"{status.upper()}: {note} | forward {'PASSES' if m['fwd_cagr'] > 0 else 'FAILS'} "
          f"(never drove selection)")
    dd_flag = "" if m['fwd_dd'] >= m['fwd_bench_dd'] else " [WARN fwd DD worse than bench]"
    print(f"forward DD {m['fwd_dd']*100:.2f}% vs bench {m['fwd_bench_dd']*100:.2f}%{dd_flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
