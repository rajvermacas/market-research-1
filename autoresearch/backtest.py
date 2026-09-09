#!/usr/bin/env python3
"""Run `strategy.py` against the panel, score it, and print the number the loop decides on.

This is the command an autoresearch iteration runs:

    python autoresearch/backtest.py

It loads the cached panel, imports `generate_weights` from `strategy.py`, forces the returned
book into something holdable, simulates it net of costs, and reports each window separately.
The last line is `SCORE`, and that is the only number the keep/revert rule reads.

Three windows, and only two of them are visible:

    train        the years an idea may be developed against
    validation   the years the score is gated on — held out from development, but the loop
                 sees it every iteration, so it is *not* a clean out-of-sample estimate either
    holdout      the most recent years, never printed and never written to `results.tsv`.
                 `--reveal-holdout` shows it. Spending it more than a handful of times over
                 the life of a research programme turns it into another training set.

`SCORE` is `min(train Sharpe, validation Sharpe)`, zeroed if the book barely trades or barely
invests. Fitting one window at the expense of the other cannot raise a minimum.

The harness is immutable. `prepare.py`, `evaluate.py`, `toolkit.py` and this file are hashed
into `harness.lock`, and a run whose hashes disagree stops rather than reporting a number
produced by a moved goalpost. `--update-lock` re-blesses them; that is a human's decision,
not an experiment's.

Usage:
    python autoresearch/backtest.py
    python autoresearch/backtest.py --note "EMA 20/100 instead of 20/50"
    python autoresearch/backtest.py --cost-bps 40 --slots 30
    python autoresearch/backtest.py --reveal-holdout      # sparingly, and never in the loop
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evaluate  # noqa: E402
import prepare  # noqa: E402

REPO_ROOT = HERE.parent
LOCK = HERE / "harness.lock"
LEDGER = HERE / "results.tsv"
HARNESS_FILES = ("prepare.py", "evaluate.py", "toolkit.py", "backtest.py")

WINDOWS = dict(
    train=("2008-01-01", "2015-12-31"),
    validation=("2016-01-01", "2021-12-31"),
    holdout=("2022-01-01", None),
)

LEDGER_COLUMNS = ("timestamp", "commit", "strategy_sha", "score", "train_sharpe", "val_sharpe",
                  "train_cagr", "val_cagr", "train_dd", "val_dd", "exposure", "turns_per_year",
                  "trades", "cost_bps", "universe", "note")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_lock(update: bool) -> None:
    current = {f: _sha(HERE / f) for f in HARNESS_FILES}
    if update or not LOCK.exists():
        LOCK.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"harness  lock written for {len(current)} files")
        return
    recorded = json.loads(LOCK.read_text())
    moved = [f for f in HARNESS_FILES if recorded.get(f) != current[f]]
    if moved:
        print("=" * 78)
        print("THE EVALUATION HARNESS HAS CHANGED: " + ", ".join(moved))
        print("Scores from a modified harness are not comparable with anything in results.tsv,")
        print("and the loop's one rule is that the strategy moves and the measurement does not.")
        print("Revert the change (git checkout -- autoresearch/), or, if a human meant it,")
        print("re-bless it with:  python autoresearch/backtest.py --update-lock")
        print("=" * 78)
        raise SystemExit(2)
    print("harness  lock ok")


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, timeout=10).stdout.strip() or "-"
    except Exception:
        return "-"


def _row(m: evaluate.Metrics) -> str:
    return (f"{m.label:<11}{m.bars:>7}{m.years:>8.1f}{m.cagr * 100:>9.2f}{m.sharpe:>9.2f}"
            f"{m.max_dd * 100:>9.2f}{m.calmar:>8.2f}{m.exposure * 100:>10.0f}%"
            f"{m.turns_per_year:>10.1f}{m.trades:>8}"
            f"{m.bench_cagr * 100:>10.2f}{m.bench_sharpe:>8.2f}{m.bench_max_dd * 100:>9.2f}")


def append_ledger(values: dict) -> None:
    fresh = not LEDGER.exists()
    with LEDGER.open("a") as fh:
        if fresh:
            fh.write("\t".join(LEDGER_COLUMNS) + "\n")
        fh.write("\t".join(str(values[c]) for c in LEDGER_COLUMNS) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--universe", default=prepare.DEFAULTS["universe"])
    ap.add_argument("--start", default=prepare.DEFAULTS["start"],
                    help="panel start — earlier than the train window, to warm indicators")
    ap.add_argument("--min-turnover", type=float, default=prepare.DEFAULTS["min_turnover"])
    ap.add_argument("--cost-bps", type=float, default=25.0,
                    help="round-trip cost per name, in basis points (default 25)")
    ap.add_argument("--max-gross", type=float, default=1.0, help="cap on invested capital")
    ap.add_argument("--min-trades", type=int, default=100)
    ap.add_argument("--min-exposure", type=float, default=0.20)
    ap.add_argument("--lookahead-cuts", type=int, default=4,
                    help="truncation points for the causality probe; 0 skips it")
    ap.add_argument("--reveal-holdout", action="store_true",
                    help="print the sealed window — a human decision, not a loop's")
    ap.add_argument("--note", default="", help="what this iteration changed; goes in results.tsv")
    ap.add_argument("--no-ledger", action="store_true", help="do not append to results.tsv")
    ap.add_argument("--update-lock", action="store_true", help="re-bless the harness hashes")
    args = ap.parse_args()

    check_lock(args.update_lock)
    if args.update_lock:
        return 0

    panel = prepare.build(universe=args.universe, start=args.start,
                          min_turnover=args.min_turnover)
    prepare.describe(panel)

    import strategy
    doc = (strategy.__doc__ or "").strip().splitlines()
    print(f"strategy {doc[0] if doc else 'strategy.py'}")
    print(f"costs    {args.cost_bps:.1f} bps round trip, cash earns nothing, "
          f"gross capped at {args.max_gross:.0%}")

    raw = strategy.generate_weights(panel)
    weights = evaluate.sanitise(raw, panel, max_gross=args.max_gross)
    dropped = float(np.abs(np.nan_to_num(raw, nan=0.0)).sum() - np.abs(weights).sum())
    if dropped > 1e-6:
        print(f"         {dropped:.1f} weight-units were dropped as untradable, negative or "
              f"over the gross cap")

    run = evaluate.simulate(weights, panel, cost_bps=args.cost_bps)
    shown = ["train", "validation"] + (["holdout"] if args.reveal_holdout else [])
    metrics = {name: evaluate.measure(name, run, panel, *WINDOWS[name]) for name in shown}

    print()
    print(f"{'window':<11}{'bars':>7}{'years':>8}{'CAGR%':>9}{'Sharpe':>9}{'maxDD%':>9}"
          f"{'Calmar':>8}{'invested':>11}{'turns/yr':>10}{'trades':>8}"
          f"{'bmCAGR%':>10}{'bmShrp':>8}{'bmDD%':>9}")
    for name in shown:
        print(_row(metrics[name]))
    if args.reveal_holdout:
        print("\n         ^ the holdout window was revealed. Every look at it spends a little "
              "of its\n           value as an out-of-sample estimate; it is not a window to "
              "iterate against.")

    if args.lookahead_cuts:
        failures = evaluate.lookahead_probe(strategy.generate_weights, panel,
                                            cuts=args.lookahead_cuts)
        if failures:
            print(f"\nLOOK-AHEAD: the book changes when the future is removed "
                  f"({len(failures)} of {args.lookahead_cuts} cut points)")
            for f in failures:
                print(f"   {f}")
            print("Something in strategy.py reads forward. The score below is meaningless "
                  "until it does not.")
        else:
            print(f"\nlookahead  clean at {args.lookahead_cuts} truncation points")

    value, reason = evaluate.score(metrics["train"], metrics["validation"],
                                   min_trades=args.min_trades, min_exposure=args.min_exposure)
    if reason:
        print(f"\nscore zeroed: {reason}")
    print(f"\nSCORE {value:.4f}   "
          f"(min of train {metrics['train'].sharpe:.4f} and "
          f"validation {metrics['validation'].sharpe:.4f})")

    if not args.no_ledger:
        t, v = metrics["train"], metrics["validation"]
        append_ledger({
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commit": _commit(), "strategy_sha": _sha(HERE / "strategy.py")[:12],
            "score": f"{value:.4f}", "train_sharpe": f"{t.sharpe:.4f}",
            "val_sharpe": f"{v.sharpe:.4f}", "train_cagr": f"{t.cagr * 100:.2f}",
            "val_cagr": f"{v.cagr * 100:.2f}", "train_dd": f"{t.max_dd * 100:.2f}",
            "val_dd": f"{v.max_dd * 100:.2f}",
            "exposure": f"{(t.exposure * t.bars + v.exposure * v.bars) / (t.bars + v.bars):.3f}",
            "turns_per_year": f"{(t.turns_per_year + v.turns_per_year) / 2:.2f}",
            "trades": t.trades + v.trades, "cost_bps": f"{args.cost_bps:g}",
            "universe": args.universe, "note": args.note.replace("\t", " ") or "-",
        })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
