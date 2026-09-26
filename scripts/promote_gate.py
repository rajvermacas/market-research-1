#!/usr/bin/env python3
"""Promotion gate: the only door to the realistic-execution champion.

Setup in words: a strategy_lab trial that KEEPs on the blind train ledger is a
candidate, not a champion. This script runs every pre-registered robustness
check on it in one pass, reveals the forward window exactly once (logged to
.cache/strategy_lab/reveals.tsv), writes a report to research/promotions/,
and — only if every check passes and --apply is given — records it as the
champion in .cache/strategy_lab/champion_real.json. Loops read the champion
from that file; they never crown one by hand.

Checks (thresholds are fixed here, before any candidate is seen):
  1 folds       train robust (median fold calmar, DD floored at 5%) > 0 and at
                most one of the train folds loses money.
  2 neighbours  every numeric param nudged one step (ints +-1, floats +-10%;
                zero-valued off-switches skipped): >= 75% of neighbours keep
                >= 80% of the candidate's robust score and none falls < 50%.
  3 cost        at 2x the profile's round-trip cost, train CAGR still beats
                the equal-weight bench.
  4 noise       32 reruns with a random 10% of new entries refused: the 10th
                percentile robust score stays >= 50% of the candidate's.
  5 margin      robust beats the reference (the standing champion, else the
                bench's robust) by >= noise_sd x sqrt(2 ln N), N = trials in
                the ledger — the expected best-of-N luck under that noise.
  6 footprint   vs the standing champion, the held book OR its exposure differs
                in >= 10% of invested decision months (skipped when there is no
                champion).
  7 transfer    on the OTHER universe (full board <-> Nifty 500, never fitted),
                train CAGR beats that universe's bench.
  8 forward     (the single reveal) fwd CAGR > fwd bench and fwd DD no worse
                than the bench's.
  9 tradeoff    the research goal, vs the standing champion, checked on the
                train AND the forward window separately. A window passes if
                the candidate dominates (higher CAGR, DD no deeper) OR buys a
                SIGNIFICANT CAGR gain with a bounded DD dent: CAGR >= champion
                + 2pp and DD at most min(0.5 x the CAGR gain, 5pp) deeper
                (e.g. +6pp CAGR may cost up to 3pp of DD). Skipped with no
                champion.

Universe: --universe nse_all (full board) or nifty500. The champion can come
from either; checks 1-8 run on the candidate's own universe, transfer on the
other, and the tradeoff compares strategy CAGR/DD directly across universes
(both are tradeable books).

Usage:
    python scripts/promote_gate.py --candidate strat_x --params-json '{...}' --top 25
    python scripts/promote_gate.py ... --universe nifty500   # a Nifty 500 candidate
    python scripts/promote_gate.py ... --apply      # crown it if all checks pass
    python scripts/promote_gate.py --from-best       # gate the realistic ledger's best
    python scripts/promote_gate.py --crown research/promotions/<report>.json
                                                     # crown a PASSING report without
                                                     # re-running (no second reveal)
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import strategy_lab as L  # noqa: E402

REPO_ROOT = L.REPO_ROOT
CHAMPION = REPO_ROOT / ".cache" / "strategy_lab" / "champion_real.json"
REPORTS = REPO_ROOT / "research" / "promotions"
UNIVERSES = ("nse_all", "nifty500")
TRADE_MIN_GAIN = 0.02   # a DD dent needs at least +2pp of CAGR ...
TRADE_DD_PER_GAIN = 0.5  # ... and may cost at most 0.5pp DD per pp of CAGR gained
TRADE_DD_CAP = 0.05      # ... and never more than 5pp of DD


def tradeoff(cagr: float, dd: float, c_cagr: float, c_dd: float) -> tuple[bool, str]:
    """One window of check 9. DDs are negative fractions (-0.19 = -19%)."""
    gain, dent = cagr - c_cagr, c_dd - dd  # dent > 0 = deeper drawdown than the champion
    if gain > 0 and dent <= 0:
        return True, "dominates"
    allowed = min(TRADE_DD_PER_GAIN * gain, TRADE_DD_CAP)
    if gain >= TRADE_MIN_GAIN and dent <= allowed:
        return True, f"trade: +{gain*100:.2f}pp CAGR for {dent*100:.2f}pp DD (allowed {allowed*100:.2f}pp)"
    if gain <= 0:
        return False, f"CAGR {gain*100:+.2f}pp vs champion"
    return False, (f"+{gain*100:.2f}pp CAGR does not pay for {dent*100:.2f}pp DD "
                   f"(allowed {allowed*100:.2f}pp; needs >= +{TRADE_MIN_GAIN*100:.0f}pp)")


def neighbours(params: dict) -> list[tuple[str, dict]]:
    out = []
    for k, v in params.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v == 0:
            continue
        steps = (v - 1, v + 1) if isinstance(v, int) else (v * 0.9, v * 1.1)
        for nv in steps:
            if isinstance(v, int) and nv < 1:
                continue
            out.append((f"{k}={nv:g}", {**params, k: round(nv, 6) if isinstance(nv, float) else nv}))
    return out


def count_trials() -> int:
    """Every trial run under the CURRENT realistic scoring, across the main
    ledger and all per-worker ledgers (rows tagged `select:robust` +
    `exec:realistic`). Deflation must count the whole search, not the one
    ledger the winner happened to be logged in."""
    n = 0
    for f in (REPO_ROOT / ".cache" / "strategy_lab").glob("*results*.tsv"):
        for line in open(f):
            if "select:robust" in line and "exec:realistic" in line:
                n += 1
    return n


def fmt(m: dict) -> str:
    return (f"train {m['cagr']*100:+.2f}/{m['maxdd']*100:.2f} (calmar {m['ret_dd']:.2f}, "
            f"robust {m['robust']:.3f})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidate")
    ap.add_argument("--params-json", default="{}")
    ap.add_argument("--top", type=int, default=None)
    ap.add_argument("--universe", choices=UNIVERSES, default="nse_all",
                    help="the candidate's universe; transfer is checked on the other")
    ap.add_argument("--from-best", action="store_true",
                    help="gate the candidate stored in the realistic best_real.json")
    ap.add_argument("--apply", action="store_true", help="crown it if every check passes")
    ap.add_argument("--skip-neighbours", action="store_true",
                    help="diagnostic only: a report without check 2 can never --apply")
    ap.add_argument("--crown", default=None,
                    help="crown an existing passing report (no re-run, no new reveal)")
    args = ap.parse_args()

    if args.crown:
        rep_ = json.loads((REPO_ROOT / args.crown).read_text())
        prof0 = L.EXEC_PROFILES["realistic"]
        want = {"exec": "realistic", **{k: prof0[k] for k in L.STAMP_KEYS},
                "universe": rep_["harness"].get("universe"), "start": "2015-01-01",
                "split": "2022-01-01", "top": rep_["top"]}
        if want["universe"] not in UNIVERSES:
            raise SystemExit(f"report universe {want['universe']} not in {UNIVERSES}")
        if not rep_.get("passed") or rep_["checks"].get("neighbours", {}).get("skipped"):
            raise SystemExit("report did not pass every check — not crowned")
        if rep_["harness"] != want:
            raise SystemExit(f"report harness {rep_['harness']} != current {want}")
        CHAMPION.write_text(json.dumps(rep_, indent=2))
        print(f"CROWNED: {CHAMPION.relative_to(REPO_ROOT)} now holds {rep_['candidate']}")
        return 0

    prof = dict(L.EXEC_PROFILES["realistic"])
    ledger = REPO_ROOT / prof["results"]
    if args.from_best:
        b = json.loads((REPO_ROOT / prof["best_json"]).read_text())
        args.candidate, params, top = b["candidate"], b["params"], b["top"]
    else:
        if not args.candidate or args.top is None:
            raise SystemExit("--candidate and --top are required (or --from-best)")
        params, top = json.loads(args.params_json), args.top
    cost = prof["cost_bps"] / 10_000
    folds = prof["folds"]
    mod = importlib.import_module(args.candidate)
    uni = args.universe
    other = [u for u in UNIVERSES if u != uni][0]
    ctx = L.build_context(uni, "2015-01-01", "2022-01-01", prof, True)

    champ = json.loads(CHAMPION.read_text()) if CHAMPION.exists() else None
    checks: dict = {}

    print(f"gating {args.candidate} top {top} {params}", flush=True)
    scored = L.score_candidate(mod, params, ctx)
    m = L.run_book(scored, ctx, top, cost, folds, record_picks=True)
    base = m["robust"]
    print("base", fmt(m), flush=True)

    # 1 folds
    neg = sum(1 for c in m["fold_cagr"] if c < 0)
    checks["folds"] = {"pass": base > 0 and neg <= 1, "robust": base,
                       "fold_cagr": m["fold_cagr"], "losing_folds": neg}

    # 2 neighbours
    if args.skip_neighbours:
        checks["neighbours"] = {"pass": False, "skipped": True}
    else:
        rows = []
        for name, p in neighbours(params):
            try:
                mn = L.run_book(L.score_candidate(mod, p, ctx), ctx, top, cost, folds)
                rows.append((name, mn["robust"], mn["cagr"], mn["maxdd"]))
                print(f"  nb {name:<24} robust {mn['robust']:.3f}", flush=True)
            except Exception as e:  # a param the candidate cannot take is a failed neighbour
                rows.append((name, float("-inf"), float("nan"), float("nan")))
                print(f"  nb {name:<24} ERROR {e}", flush=True)
        ok = [r for r in rows if r[1] >= 0.8 * base]
        worst = min((r[1] for r in rows), default=base)
        checks["neighbours"] = {"pass": bool(rows) and len(ok) >= 0.75 * len(rows)
                                and worst >= 0.5 * base,
                                "n": len(rows), "kept_80pct": len(ok), "worst": worst,
                                "rows": [list(r) for r in rows]}

    # 3 cost
    mc = L.run_book(scored, ctx, top, 2 * cost, folds)
    checks["cost"] = {"pass": mc["cagr"] > mc["bench_cagr"], "cost_bps": 2 * prof["cost_bps"],
                      "cagr": mc["cagr"], "dd": mc["maxdd"], "bench_cagr": mc["bench_cagr"]}

    # 4 noise
    noise = L.noise_probe(scored, ctx, top, cost, folds, "robust", 32, prof["noise_rate"])
    sd, p10 = float(np.std(noise, ddof=1)), float(np.percentile(noise, 10))
    checks["noise"] = {"pass": p10 >= 0.5 * base, "sd": sd, "p10": p10}

    # 5 deflated margin
    n_trials = max(2, count_trials())
    ref = champ["metrics"]["robust"] if champ else m["bench_robust"]
    need = sd * math.sqrt(2 * math.log(n_trials))
    checks["margin"] = {"pass": base - ref >= need, "reference": ref,
                        "reference_is": "champion" if champ else "bench",
                        "gain": base - ref, "required": need, "n_trials": n_trials}

    # 6 footprint
    if champ:
        cmod = importlib.import_module(champ["candidate"])
        cuni = champ["harness"].get("universe", "nse_all")
        cctx = ctx if cuni == uni else L.build_context(cuni, "2015-01-01", "2022-01-01",
                                                        prof, True)
        cm = L.run_book(L.score_candidate(cmod, champ["params"], cctx), cctx, champ["top"],
                        cost, folds, record_picks=True)
        inv = [t for t in m["picks"] if m["picks"][t][0] or cm["picks"].get(t, ([], 0))[0]]
        diff = [t for t in inv if m["picks"][t] != cm["picks"].get(t)]
        share = len(diff) / max(len(inv), 1)
        checks["footprint"] = {"pass": share >= 0.10, "differing_months": len(diff),
                               "invested_months": len(inv), "share": share}
    else:
        checks["footprint"] = {"pass": True, "skipped": "no standing champion"}

    # 7 transfer (un-fitted universe)
    ctx5 = L.build_context(other, "2015-01-01", "2022-01-01", prof, True)
    m5 = L.run_book(L.score_candidate(mod, params, ctx5), ctx5, top, cost, folds)
    checks["transfer"] = {"pass": m5["cagr"] > m5["bench_cagr"], "universe": other,
                          "cagr": m5["cagr"],
                          "dd": m5["maxdd"], "bench_cagr": m5["bench_cagr"],
                          "fwd_cagr": m5["fwd_cagr"], "fwd_dd": m5["fwd_dd"]}

    # 8 forward — the single reveal
    n_rev = L.log_reveal(args.candidate, params, str(prof["results"]), "promote_gate")
    fwd_calmar = m["fwd_cagr"] / abs(m["fwd_dd"]) if m["fwd_dd"] else 0.0
    champ_fc = champ["forward"]["calmar"] if champ else None
    checks["forward"] = {"pass": m["fwd_cagr"] > m["fwd_bench_cagr"]
                         and m["fwd_dd"] >= m["fwd_bench_dd"],
                         "cagr": m["fwd_cagr"], "dd": m["fwd_dd"], "calmar": fwd_calmar,
                         "bench_cagr": m["fwd_bench_cagr"], "bench_dd": m["fwd_bench_dd"],
                         "champion_calmar": champ_fc, "reveal_no": n_rev}

    if champ:
        cmet, cfwd = champ["metrics"], champ["forward"]
        ok_t, why_t = tradeoff(m["cagr"], m["maxdd"], cmet["cagr"], cmet["maxdd"])
        ok_f, why_f = tradeoff(m["fwd_cagr"], m["fwd_dd"], cfwd["cagr"], cfwd["dd"])
        checks["tradeoff"] = {
            "pass": ok_t and ok_f, "train_verdict": why_t, "fwd_verdict": why_f,
            "train": [m["cagr"], m["maxdd"]], "champ_train": [cmet["cagr"], cmet["maxdd"]],
            "fwd": [m["fwd_cagr"], m["fwd_dd"]], "champ_fwd": [cfwd["cagr"], cfwd["dd"]]}
    else:
        checks["tradeoff"] = {"pass": True, "skipped": "no standing champion"}

    passed = all(c["pass"] for c in checks.values())
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    harness = {"exec": "realistic", **{k: prof[k] for k in L.STAMP_KEYS},
               "universe": uni, "start": "2015-01-01", "split": "2022-01-01", "top": top}
    report = {"ts": ts, "candidate": args.candidate, "params": params, "top": top,
              "harness": harness, "passed": passed,
              "metrics": {k: v for k, v in L.strip_forward(m).items() if k != "picks"},
              "forward": {"cagr": m["fwd_cagr"], "dd": m["fwd_dd"], "calmar": fwd_calmar,
                          "bench_cagr": m["fwd_bench_cagr"], "bench_dd": m["fwd_bench_dd"]},
              "checks": checks,
              "replaces": champ["candidate"] if champ else None}
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"{ts}_{args.candidate}.json"
    out.write_text(json.dumps(report, indent=2, default=float))

    print()
    for name, c in checks.items():
        detail = {k: v for k, v in c.items() if k not in ("pass", "rows", "fold_cagr")}
        print(f"{'PASS' if c['pass'] else 'FAIL'}  {name:<10} {json.dumps(detail, default=float)}")
    print(f"\nFORWARD {m['fwd_cagr']*100:+.2f}% DD {m['fwd_dd']*100:.2f}% calmar {fwd_calmar:.2f} "
          f"(bench {m['fwd_bench_cagr']*100:+.2f}% / {m['fwd_bench_dd']*100:.2f}%) — reveal #{n_rev}")
    print(f"{'ALL CHECKS PASS' if passed else 'GATE FAILED'} — report {out.relative_to(REPO_ROOT)}")
    if args.apply:
        if passed:
            CHAMPION.write_text(json.dumps(report, indent=2, default=float))
            print(f"CROWNED: {CHAMPION.relative_to(REPO_ROOT)} now holds {args.candidate}")
        else:
            print("not crowned (gate failed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
