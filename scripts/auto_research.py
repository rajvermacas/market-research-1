#!/usr/bin/env python3
"""Hill-climbing auto-research loop for momentum rotation: CAGR up, drawdown floored.

Setup in words: hold the top-N names by trailing return (skipping the most
recent month), rebalanced monthly, with an optional regime overlay that sits in
cash while an equal-weight index of the universe is below its own average.
Each loop proposes one random neighbour of the current best parameters,
backtests it on the daily panel, and keeps it ONLY if train-window CAGR
strictly improves without breaching the drawdown floor or slipping more than
--dd-slack past the best drawdown so far. Selection never sees the forward
window: --split divides train (search) from test (holdout), and the forward
numbers are logged for overfit detection only. The book therefore improves
monotonically on train CAGR by construction; anything else is logged as discard.

Point-in-time: ranking at month t uses returns through t-1 only (most recent
month skipped); regime reads the index average through t. Costs charged per
name replaced at each rebalance. Years derived from month count, never a
bars-per-year constant. Universe is today's index members, so survivorship
bias flatters every number here — read against the equal-weight buy-and-hold
control printed on the same window, not as an absolute.

Usage:
    python scripts/auto_research.py --iterations 50
    python scripts/auto_research.py --iterations 100 --max-dd 20 --seed 7
    python scripts/auto_research.py --split 2022-01-01 --iterations 50
    python scripts/auto_research.py --split "" --iterations 50  # no holdout
    python scripts/auto_research.py --resume --iterations 50
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import polars as pl

from momentum_rotation import performance

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY = REPO_ROOT / "data" / "ohlcv" / "daily"
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"

SEARCH_SPACE = {
    "lookback": [3, 6, 9, 12, 15],
    "top": [10, 15, 25, 40, 50],
    "regime_ma": [0, 6, 8, 10, 12],
    "stock_ma": [0, 6, 10],
    "abs_mom": [False, True],
}


def load_monthly(universe: str, start: str):
    u = pl.read_parquet(UNIVERSE)
    if universe != "nse_all":
        u = u.filter(pl.col(f"in_{universe}"))
    syms = u["symbol"].to_list()
    d = (
        pl.scan_parquet(str(DAILY / "**" / "*.parquet"), hive_partitioning=True)
        .filter(pl.col("symbol").is_in(syms))
        .select("symbol", "date", "close")
        .collect()
        .sort("symbol", "date")
    )
    m = (
        d.with_columns(pl.col("date").dt.truncate("1mo").alias("mo"))
        .group_by("symbol", "mo")
        .agg(pl.col("close").last())
        .sort("symbol", "mo")
    )
    wide = m.pivot(on="symbol", index="mo", values="close").sort("mo")
    months = wide["mo"].to_list()
    cols = [c for c in wide.columns if c != "mo"]
    px = wide.select(cols).to_numpy()
    start_i = next(i for i, mm in enumerate(months) if str(mm) >= start)
    return px, months, cols, start_i


def evaluate(params: dict, px, months, start_i: int, cost: float,
               split_i: int | None = None) -> dict:
    lb, top, ma = params["lookback"], params["top"], params["regime_ma"]
    sma, absmom = params["stock_ma"], params["abs_mom"]

    mom = np.full_like(px, np.nan)
    mom[lb + 1 :] = px[1:-lb] / px[: -lb - 1] - 1

    alive = ~np.isnan(px[start_i])
    idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
    idx_ma = pl.Series(idx).rolling_mean(ma).to_numpy() if ma else None

    eq, held = [1.0], set()
    invested_flags: list[int] = []
    for t in range(start_i, len(months) - 1):
        on = True if not ma else bool(idx[t] > idx_ma[t]) if not np.isnan(idx_ma[t]) else False
        scores = mom[t].copy()
        scores[np.isnan(px[t]) | np.isnan(px[t + 1])] = np.nan
        if sma and t >= sma:
            own = np.nanmean(px[t - sma + 1 : t + 1], axis=0)
            scores[~(px[t] > own)] = np.nan
        if absmom:
            scores[~(scores > 0)] = np.nan
        pick = set()
        if on and np.isfinite(scores).sum() >= max(top // 2, 3):
            n = min(top, int(np.isfinite(scores).sum()))
            pick = set(np.argsort(-np.nan_to_num(scores, nan=-1e9))[:n])
        turnover = len(pick - held) / max(len(pick), 1) if pick else 0.0
        if pick:
            r = np.nanmean(px[t + 1, list(pick)] / px[t, list(pick)]) - 1
            eq.append(eq[-1] * (1 + r) * (1 - cost * turnover))
            invested_flags.append(1)
        else:
            eq.append(eq[-1])
            invested_flags.append(0)
        held = pick

    curve = np.array(eq)
    flags = np.array(invested_flags)
    bench = idx[start_i:] / idx[start_i]

    def seg(curve_seg: np.ndarray):
        normed = curve_seg / curve_seg[0]
        n = len(normed) - 1
        c, d = performance(normed, n / 12) if n > 0 else (0.0, 0.0)
        return c, d

    full_cagr, full_dd = seg(curve)
    bench_cagr, bench_dd = seg(bench)

    if split_i is None:
        mid = len(curve) // 2
        h1_cagr, _ = seg(curve[:mid])
        h2_cagr, _ = seg(curve[mid - 1 :])
        ret_dd = abs(full_cagr / full_dd) if full_dd else 0.0
        return {
            # selection keys (= full window when no split)
            "cagr": float(full_cagr),
            "maxdd": float(full_dd),
            "ret_dd": float(ret_dd),
            "h1_cagr": float(h1_cagr),
            "h2_cagr": float(h2_cagr),
            "bench_cagr": float(bench_cagr),
            "bench_dd": float(bench_dd),
            "invested": float(flags.mean()) if len(flags) else 0.0,
            "months": len(curve) - 1,
            # forward = full when no split, so old TSV readers still work
            "fwd_cagr": float(full_cagr),
            "fwd_dd": float(full_dd),
            "fwd_bench_cagr": float(bench_cagr),
            "fwd_bench_dd": float(bench_dd),
            "fwd_months": len(curve) - 1,
            "full_cagr": float(full_cagr),
            "full_dd": float(full_dd),
        }

    k = split_i - start_i  # eq[k] is the first forward month
    train, test = curve[: k + 1], curve[k:] / curve[k]
    bench_train, bench_test = bench[: k + 1], bench[k:] / bench[k]
    train_flags, test_flags = flags[:k], flags[k:]
    train_cagr, train_dd = seg(train)
    test_cagr, test_dd = seg(test)
    bench_train_cagr, bench_train_dd = seg(bench_train)
    bench_test_cagr, bench_test_dd = seg(bench_test)

    mid = len(train) // 2
    h1_cagr, _ = seg(train[:mid])
    h2_cagr, _ = seg(train[mid - 1 :])
    ret_dd = abs(train_cagr / train_dd) if train_dd else 0.0
    return {
        # selection keys (= train window when split)
        "cagr": float(train_cagr),
        "maxdd": float(train_dd),
        "ret_dd": float(ret_dd),
        "h1_cagr": float(h1_cagr),
        "h2_cagr": float(h2_cagr),
        "bench_cagr": float(bench_train_cagr),
        "bench_dd": float(bench_train_dd),
        "invested": float(train_flags.mean()) if len(train_flags) else 0.0,
        "months": len(train) - 1,
        # holdout, never used for selection
        "fwd_cagr": float(test_cagr),
        "fwd_dd": float(test_dd),
        "fwd_bench_cagr": float(bench_test_cagr),
        "fwd_bench_dd": float(bench_test_dd),
        "fwd_months": len(test) - 1,
        "full_cagr": float(full_cagr),
        "full_dd": float(full_dd),
    }


def mutate(params: dict, rng: random.Random) -> dict:
    key = rng.choice(list(SEARCH_SPACE))
    choices = [v for v in SEARCH_SPACE[key] if v != params[key]]
    if not choices:
        return dict(params)
    out = dict(params)
    out[key] = rng.choice(choices)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--universe", default="nifty500")
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--split", default="2022-01-01",
                    help="train/test split month (YYYY-MM-DD): search uses "
                         "start..split, forward uses split..end. Empty string disables.")
    ap.add_argument("--iterations", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-dd", type=float, default=70.0,
                    help="floor: reject anything with drawdown worse than -X%% "
                         "(default 70; relaxed to baseline if baseline is worse)")
    ap.add_argument("--dd-slack", type=float, default=2.0,
                    help="reject anything more than Xpp worse than best DD so far")
    ap.add_argument("--min-delta", type=float, default=0.05,
                    help="required CAGR improvement in pp to accept (default 0.05)")
    ap.add_argument("--cost-bps", type=float, default=25.0)
    ap.add_argument("--lookback", type=int, default=12)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--regime-ma", type=int, default=10)
    ap.add_argument("--stock-ma", type=int, default=0)
    ap.add_argument("--abs-mom", action="store_true")
    ap.add_argument("--results", default=".cache/auto_research/results.tsv")
    ap.add_argument("--best", default=".cache/auto_research/best.json")
    ap.add_argument("--resume", action="store_true",
                    help="continue from existing best.json instead of baseline")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    cost = args.cost_bps / 10_000
    results_path = REPO_ROOT / args.results
    best_path = REPO_ROOT / args.best
    results_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"loading monthly panel ({args.universe} from {args.start}) ...", flush=True)
    px, months, cols, start_i = load_monthly(args.universe, args.start)
    split_i = None
    if args.split:
        split_i = next((i for i, mm in enumerate(months) if str(mm) >= args.split), None)
        if split_i is None or not (start_i < split_i < len(months) - 1):
            raise SystemExit(f"--split {args.split} outside testable range "
                             f"({months[start_i]}..{months[-1]})")
    n_train = (split_i - start_i) if split_i is not None else len(months) - 1 - start_i
    n_fwd = (len(months) - 1 - split_i) if split_i is not None else 0
    print(f"{len(cols)} symbols | train from {months[start_i]} "
          f"({n_train}mo)" + (f" | forward from {months[split_i]} ({n_fwd}mo)"
                              if split_i is not None else " | no holdout"))

    if args.resume and best_path.exists():
        best_params = json.loads(best_path.read_text())["params"]
        print(f"resuming from {best_path}: {best_params}")
    else:
        best_params = {"lookback": args.lookback, "top": args.top,
                       "regime_ma": args.regime_ma, "stock_ma": args.stock_ma,
                       "abs_mom": bool(args.abs_mom)}

    def score_note(m: dict) -> str:
        base = (f"TRAIN {m['cagr']*100:+.2f}% DD {m['maxdd']*100:.2f}% "
                f"ret/DD {m['ret_dd']:.2f} H1 {m['h1_cagr']*100:+.1f}% "
                f"H2 {m['h2_cagr']*100:+.1f}% inv {m['invested']*100:.0f}% | "
                f"FWD {m['fwd_cagr']*100:+.2f}% DD {m['fwd_dd']*100:.2f}%")
        return base

    # Baseline first, like autoresearch's first run.
    base = evaluate(best_params, px, months, start_i, cost, split_i)
    best = base
    print(f"[baseline] {best_params} -> {score_note(base)} "
          f"(train bench {base['bench_cagr']*100:+.2f}% / {base['bench_dd']*100:.2f}% | "
          f"fwd bench {base['fwd_bench_cagr']*100:+.2f}% / {base['fwd_bench_dd']*100:.2f}%)")

    header = ("iter\tstatus\tlookback\ttop\tregime_ma\tstock_ma\tabs_mom\t"
              "train_cagr\train_dd\tret_dd\th1\th2\ttrain_bench\t"
              "fwd_cagr\tfwd_dd\tfwd_bench\tinvested\tnote\n")

    def row(iter_no: int, status: str, p: dict, m: dict, note: str) -> str:
        return (f"{iter_no}\t{status}\t{p['lookback']}\t{p['top']}\t"
                f"{p['regime_ma']}\t{p['stock_ma']}\t{int(p['abs_mom'])}\t"
                f"{m['cagr']*100:.3f}\t{m['maxdd']*100:.3f}\t{m['ret_dd']:.3f}\t"
                f"{m['h1_cagr']*100:.3f}\t{m['h2_cagr']*100:.3f}\t"
                f"{m['bench_cagr']*100:.3f}\t{m['fwd_cagr']*100:.3f}\t"
                f"{m['fwd_dd']*100:.3f}\t{m['fwd_bench_cagr']*100:.3f}\t"
                f"{m['invested']*100:.1f}\t{note}\n")
    if not args.resume or not results_path.exists():
        results_path.write_text(header)
        with open(results_path, "a") as f:
            f.write(row(0, "keep", best_params, base, "baseline"))
    best_path.write_text(json.dumps({"params": best_params, "metrics": best}, indent=2))

    floor = -abs(args.max_dd) / 100
    if base["maxdd"] < floor:
        print(f"baseline DD {base['maxdd']*100:.1f}% breaches --max-dd {args.max_dd:g}%: "
              f"relaxing floor to baseline so the loop is not dead on arrival")
        floor = base["maxdd"]
    for i in range(1, args.iterations + 1):
        cand = mutate(best_params, rng)
        try:
            m = evaluate(cand, px, months, start_i, cost, split_i)
        except Exception as e:  # crash: log and move on, like autoresearch
            with open(results_path, "a") as f:
                f.write(f"{i}\tcrash\t{cand['lookback']}\t{cand['top']}\t"
                        f"{cand['regime_ma']}\t{cand['stock_ma']}\t"
                        f"{int(cand['abs_mom'])}\t0.000\t0.000\t0.000\t"
                        f"0.000\t0.000\t0.000\t0.000\t0.000\t0.000\t0.0\t{e}\n")
            print(f"[{i:>3}] CRASH {cand}: {e}")
            continue
        # Selection uses TRAIN only; forward is logged, never used to accept.
        cagr_ok = m["cagr"] > best["cagr"] + args.min_delta / 100
        dd_ok = m["maxdd"] >= floor and m["maxdd"] >= best["maxdd"] - args.dd_slack / 100
        robust = m["h1_cagr"] > 0 and m["h2_cagr"] > 0
        status = "keep" if (cagr_ok and dd_ok and robust) else "discard"
        reason = ""
        if status == "discard":
            if not robust:
                reason = "fails train half"
            elif not cagr_ok:
                reason = f"TRAIN {m['cagr']*100:.2f}% <= best {best['cagr']*100:.2f}%"
            else:
                reason = f"DD {m['maxdd']*100:.1f}% breaches floor/slack"
        else:
            best, best_params = m, cand
            best_path.write_text(json.dumps({"params": best_params, "metrics": best}, indent=2))
        with open(results_path, "a") as f:
            f.write(row(i, status, cand, m, 'BEST' if status == 'keep' else reason))
        overfit = ""
        if split_i is not None and status == "keep" and m["fwd_cagr"] <= 0:
            overfit = " [WARN fwd <= 0: train-only winner fails forward]"
        print(f"[{i:>3}] {status.upper():<7} {cand} -> {score_note(m)}"
              + ("" if status == "keep" else f" ({reason})") + overfit, flush=True)

    print(f"\nBEST (train-selected): {best_params} -> {score_note(best)}")
    print(f"train bench {best['bench_cagr']*100:+.2f}% / {best['bench_dd']*100:.2f}% | "
          f"fwd bench {best['fwd_bench_cagr']*100:+.2f}% / {best['fwd_bench_dd']*100:.2f}% | "
          f"full {best['full_cagr']*100:+.2f}% / {best['full_dd']*100:.2f}%")
    print(f"results {results_path} | best {best_path}")
    if split_i is not None:
        verdict = "PASSES forward" if best["fwd_cagr"] > 0 else "FAILS forward"
        dd_flag = "" if best["fwd_dd"] >= best["fwd_bench_dd"] else " [WARN fwd DD worse than bench]"
        print(f"Overfit check: forward {best['fwd_cagr']*100:+.2f}% (DD {best['fwd_dd']*100:.2f}%) "
              f"vs fwd bench {best['fwd_bench_cagr']*100:+.2f}% (DD {best['fwd_bench_dd']*100:.2f}%) "
              f"-> {verdict}{dd_flag} (forward never drove selection).")
    print("Caveat: today's-index universe; momentum flattered by survivorship. "
          "Validate on an un-fitted universe before believing a regime effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
