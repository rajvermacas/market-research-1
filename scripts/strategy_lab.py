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
    SPACE = {...}              # param search space (documentation only)
    def score(panels, params) -> (scores, regime)
        panels: px (months x stocks month-end closes), months, cols,
                daily (long symbol/date/close, only if NEEDS_DAILY), start_i
        scores: months x stocks float array, NaN = ineligible, higher = better
        regime: bool array over months, False = sit in cash that month

Point-in-time: a holding month starting at months[m] may only use daily bars
with date < months[m] and month-end closes through px[m]. Costs are charged
per replaced name at each rebalance. Years come from month counts. The
universe is today's listing, so survivorship flatters everything — always read
a candidate against its bench and its forward, never alone.

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
        .select("symbol", "date", "close")
        .collect()
        .sort("symbol", "date")
    )


def backtest_scores(scores: np.ndarray, regime: np.ndarray, px: np.ndarray,
                    months, start_i: int, split_i: int | None,
                    cost: float, top: int) -> dict:
    n_stocks = px.shape[1]
    eq, held, flags = [1.0], set(), []
    for t in range(start_i, len(months) - 1):
        s = scores[t].copy() if t < scores.shape[0] else np.full(n_stocks, np.nan)
        ok = np.isfinite(s) & np.isfinite(px[t]) & np.isfinite(px[t + 1])
        s[~ok] = np.nan
        on = bool(regime[t]) if t < len(regime) else True
        pick = set()
        if on and np.isfinite(s).sum() >= max(top // 2, 3):
            n = min(top, int(np.isfinite(s).sum()))
            pick = set(np.argsort(-np.nan_to_num(s, nan=-1e9))[:n])
        turnover = len(pick - held) / max(len(pick), 1) if pick else 0.0
        if pick:
            r = np.nanmean(px[t + 1, list(pick)] / px[t, list(pick)]) - 1
            eq.append(eq[-1] * (1 + r) * (1 - cost * turnover))
            flags.append(1)
        else:
            eq.append(eq[-1])
            flags.append(0)
        held = pick

    curve = np.array(eq)
    flags = np.array(flags)
    # equal-weight bench of names alive at the test start
    alive = ~np.isnan(px[start_i])
    idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
    bench = idx[start_i:] / idx[start_i]

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
        return {"cagr": float(full_cagr), "maxdd": float(full_dd), "ret_dd": float(rdd),
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
    return {"cagr": float(train_cagr), "maxdd": float(train_dd), "ret_dd": float(rdd),
            "h1_cagr": float(h1), "h2_cagr": float(h2),
            "bench_cagr": float(btrain_cagr), "bench_dd": float(btrain_dd),
            "invested": float(flags[:k].mean()) if k else 0.0, "months": len(train) - 1,
            "fwd_cagr": float(test_cagr), "fwd_dd": float(test_dd),
            "fwd_bench_cagr": float(btest_cagr), "fwd_bench_dd": float(btest_dd),
            "fwd_months": len(curve) - 1 - k,
            "full_cagr": float(full_cagr), "full_dd": float(full_dd)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", required=True, help="strat_* module name, no .py")
    ap.add_argument("--params-json", default="{}")
    ap.add_argument("--universe", default="nse_all")
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--split", default="2022-01-01")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--cost-bps", type=float, default=25.0)
    ap.add_argument("--max-dd", type=float, default=70.0)
    ap.add_argument("--dd-slack", type=float, default=2.0)
    ap.add_argument("--min-delta", type=float, default=0.05)
    ap.add_argument("--results", default=".cache/strategy_lab/results.tsv")
    ap.add_argument("--best-json", default=".cache/strategy_lab/best.json")
    args = ap.parse_args()

    params = json.loads(args.params_json)
    cost = args.cost_bps / 10_000
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
    if getattr(mod, "NEEDS_DAILY", False):
        print("loading daily long panel for candidate ...", flush=True)
        u = pl.read_parquet(REPO_ROOT / "data" / "universe" / "nse_universe.parquet")
        syms = u["symbol"].to_list() if args.universe == "nse_all" else \
            u.filter(pl.col(f"in_{args.universe}"))["symbol"].to_list()
        daily = load_daily(syms)
    panels = {"px": px, "months": months, "cols": cols, "daily": daily, "start_i": start_i}

    print(f"scoring with {args.candidate} {params} ...", flush=True)
    scores, regime = mod.score(panels, params)
    m = backtest_scores(np.asarray(scores, dtype=float), np.asarray(regime, dtype=bool),
                        px, months, start_i, split_i, cost, args.top)
    print(f"TRAIN {m['cagr']*100:+.2f}% DD {m['maxdd']*100:.2f}% ret/DD {m['ret_dd']:.2f} "
          f"H1 {m['h1_cagr']*100:+.1f}% H2 {m['h2_cagr']*100:+.1f}% inv {m['invested']*100:.0f}% "
          f"| FWD {m['fwd_cagr']*100:+.2f}% DD {m['fwd_dd']*100:.2f}% "
          f"(train bench {m['bench_cagr']*100:+.2f}% | fwd bench {m['fwd_bench_cagr']*100:+.2f}%)")

    status, note = "baseline", "first entry"
    if best_path.exists():
        best = json.loads(best_path.read_text())
        b = best["metrics"]
        floor = min(-abs(args.max_dd) / 100, b["maxdd"])
        cagr_ok = m["cagr"] > b["cagr"] + args.min_delta / 100
        dd_ok = m["maxdd"] >= floor and m["maxdd"] >= b["maxdd"] - args.dd_slack / 100
        robust = m["h1_cagr"] > 0 and m["h2_cagr"] > 0
        if cagr_ok and dd_ok and robust:
            status, note = "keep", "beats best on train"
        else:
            if not robust:
                note = "fails train half"
            elif not cagr_ok:
                note = f"TRAIN {m['cagr']*100:.2f}% <= best {b['cagr']*100:.2f}%"
            else:
                note = f"DD {m['maxdd']*100:.1f}% breaches floor/slack"
            status = "discard"
    if status in ("baseline", "keep"):
        best_path.write_text(json.dumps(
            {"candidate": args.candidate, "params": params, "top": args.top,
             "metrics": m}, indent=2))
    if not results_path.exists():
        results_path.write_text("ts\tstatus\tcandidate\tparams\ttop\ttrain_cagr\ttrain_dd\t"
                                "ret_dd\th1\th2\tfwd_cagr\tfwd_dd\tfwd_bench\tnote\n")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(results_path, "a") as f:
        f.write(f"{ts}\t{status}\t{args.candidate}\t{json.dumps(params, sort_keys=True)}\t"
                f"{args.top}\t{m['cagr']*100:.3f}\t{m['maxdd']*100:.3f}\t{m['ret_dd']:.3f}\t"
                f"{m['h1_cagr']*100:.3f}\t{m['h2_cagr']*100:.3f}\t{m['fwd_cagr']*100:.3f}\t"
                f"{m['fwd_dd']*100:.3f}\t{m['fwd_bench_cagr']*100:.3f}\t{note}\n")
    print(f"{status.upper()}: {note} | forward {'PASSES' if m['fwd_cagr'] > 0 else 'FAILS'} "
          f"(never drove selection)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
