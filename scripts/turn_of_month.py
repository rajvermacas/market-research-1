#!/usr/bin/env python3
"""The turn-of-the-month (Ultimo) effect on Indian equity.

The source states rules and a claim, both testable:

    entry   the close of the FIFTH-LAST trading day of the month
    exit    the close of the THIRD trading day of the new month
    else    in cash — roughly a third of the time invested

and the claim is explicitly about risk rather than return: on the S&P 500 since 1960 it
reports 7% CAGR against buy-and-hold's 7.5%, at a 27% drawdown against 56%. So the number
that decides it is not CAGR but return per unit of drawdown, and that is what this reports
first. A part-time book that merely has a smaller drawdown has proved nothing — it is in
cash two thirds of the time, and cash has no drawdown.

This is the first strategy tested in this repository whose signal is not a price at all.
Nothing is measured from the chart: the rule is a calendar, so there is no indicator to
warm up, no lookahead to guard against, and no parameter fitted to the data. That also
makes the two controls unusually clean:

  * random windows — the same number of holding spells, the same length, placed at random
    starts. If the turn of the month is special, it must beat a window that is not.
  * buy-and-hold of the same series over the same window.

Run on the real cap-weighted Nifty series from Yahoo (^NSEI 2007-, ^CNX100 and ^CRSLDX
2005-), which carries no survivorship bias at all — an index is not a basket of today's
survivors — and optionally on an equal-weight basket of the committed daily panel, which
does, and which is only there to reach further back.

Because the window is a free parameter that someone chose, `--sweep` prints every entry
and exit offset rather than only the published pair. A calendar effect that exists only at
(-5, +3) and nowhere near it is a fitted number, not an anomaly.

Usage:
    python scripts/turn_of_month.py --universe nifty50
    python scripts/turn_of_month.py --universe nifty500 --sweep
    python scripts/turn_of_month.py --source panel --start 2005-01-01
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

from rsi_backtest import performance
from rsi2_mean_reversion import fetch_index, INDICES

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"


def equal_weight_series(universe: str, start: str | None) -> pl.DataFrame:
    """An equal-weight basket of the committed daily panel, as a single price series.

    Survivorship-biased by construction — today's index membership walked backwards — and
    offered only to reach back further than Yahoo's index history. The MEAN of normalised
    closes, never the median, which is the path of the median stock and is not tradeable.
    """
    names = pl.read_parquet(UNIVERSE).filter(pl.col(f"in_{universe}"))
    panel = (pl.scan_parquet(DAILY_GLOB, hive_partitioning=True)
             .filter(pl.col("symbol").is_in(names["symbol"].implode()))
             .select("symbol", "date", "close").drop_nulls("close").collect())
    if start:
        panel = panel.filter(pl.col("date") >= pl.lit(start).str.to_date())
    wide = (panel.pivot(on="symbol", index="date", values="close").sort("date"))
    wide = wide.with_columns([pl.col(c).forward_fill()
                              for c in wide.columns if c != "date"])
    matrix = wide.select([c for c in wide.columns if c != "date"]).to_numpy()
    listed = ~np.isnan(matrix[0])
    normalised = matrix[:, listed] / matrix[0, listed]
    step = normalised[1:] / np.where(normalised[:-1] == 0, np.nan, normalised[:-1])
    with np.errstate(invalid="ignore"):
        artefact = np.nanmax(np.abs(step - 1.0), axis=0) > 0.50
    curve = np.nanmean(normalised[:, ~artefact], axis=1)
    print(f"  equal-weight basket of {int(listed.sum())} symbols "
          f"({int(artefact.sum())} corporate-action artefacts excluded)")
    return pl.DataFrame({"date": wide["date"], "close": curve})


def day_positions(frame: pl.DataFrame) -> pl.DataFrame:
    """Each session's position within its month, counted from both ends.

    Trading days, not calendar days — the fifth-last trading day is what the rule says and
    what a holiday-shortened month makes different from the 26th.
    """
    return (frame.sort("date")
            .with_columns(pl.col("date").dt.year().alias("_y"),
                          pl.col("date").dt.month().alias("_m"))
            .with_columns(
                (pl.int_range(pl.len()).over(["_y", "_m"]) + 1).alias("dom_start"),
                (pl.len().over(["_y", "_m"])
                 - pl.int_range(pl.len()).over(["_y", "_m"])).alias("dom_end")))


def spells(frame: pl.DataFrame, entry_n: int, exit_n: int) -> list[tuple[int, int]]:
    """(entry index, exit index) for each turn of the month in the series.

    Entry is the close of the entry day, so the first return that accrues is the NEXT
    session's. A spell that runs off the end of the data is dropped rather than marked to
    the last available close, which would book an unfinished holding as a completed trade.
    """
    starts = np.flatnonzero(frame["dom_end"].to_numpy() == entry_n)
    ends = np.flatnonzero(frame["dom_start"].to_numpy() == exit_n)
    out = []
    for i in starts:
        later = ends[ends > i]
        if later.size:
            out.append((int(i), int(later[0])))
    return out


def curve_from_spells(close: np.ndarray, held: list[tuple[int, int]],
                      cost: float) -> tuple[np.ndarray, float, list[float], list[int]]:
    """Mark the account daily: it rides the index while held and is flat otherwise.

    Daily marking rather than trade-to-trade is what makes the drawdown comparable with
    the benchmark's — a curve stepped only at exits hides every excursion the position sat
    through and reports a drawdown the strategy did not have.
    """
    equity = np.ones(len(close))
    level, days_held, trades, entry_at = 1.0, 0, [], []
    cursor = 0
    for i, j in held:
        equity[cursor:i + 1] = level
        base = close[i]
        if not np.isfinite(base) or base <= 0 or j <= i:
            cursor = i + 1
            continue
        for t in range(i + 1, j + 1):
            equity[t] = level * (close[t] / base) * (1 - cost)
        gross = close[j] / base
        trades.append(gross * (1 - cost) ** 2 - 1)
        entry_at.append(i)
        level *= gross * (1 - cost) ** 2
        equity[j] = level
        days_held += j - i
        cursor = j + 1
    equity[cursor:] = level
    return equity, days_held / max(len(close), 1), trades, entry_at


def random_spells(n_days: int, held: list[tuple[int, int]], seed: int) -> list:
    """The same number of holding spells, the same lengths, placed at random starts.

    Length-matched deliberately. A control with shorter spells would be in the market less
    and would look better on drawdown for a reason that has nothing to do with the
    calendar, which is the whole thing being tested.
    """
    rng = np.random.default_rng(seed)
    out = []
    for i, j in held:
        span = j - i
        if span <= 0 or span >= n_days - 2:
            continue
        start = int(rng.integers(0, n_days - span - 1))
        out.append((start, start + span))
    return sorted(out)


def month_profile(frame: pl.DataFrame) -> None:
    """Average session return by position in the month, from both ends.

    The event study for a calendar rule. If the turn of the month is real it shows up here
    without anyone choosing a window, and if it only appears once a window is chosen then
    the window is the finding.
    """
    close = frame["close"].to_numpy()
    ret = np.full(len(close), np.nan)
    ret[1:] = close[1:] / close[:-1] - 1
    start = frame["dom_start"].to_numpy()
    end = frame["dom_end"].to_numpy()
    good = np.isfinite(ret)
    overall = ret[good].mean()
    print(f"\n  average session return by position in the month "
          f"(all sessions: {overall * 100:+.4f}%)")
    cells = []
    for n in range(1, 6):
        sel = good & (end == n)
        cells.append((f"-{n}", ret[sel].mean() * 100, int(sel.sum())))
    for n in range(1, 6):
        sel = good & (start == n)
        cells.append((f"+{n}", ret[sel].mean() * 100, int(sel.sum())))
    print("    " + "".join(f"{c[0]:>9}" for c in cells))
    print("    " + "".join(f"{c[1]:>+9.4f}" for c in cells))
    print("    " + "".join(f"{c[2]:>9}" for c in cells))
    print("    (-n = nth-last session of the month, +n = nth session of the next)")


def evaluate(frame: pl.DataFrame, entry_n: int, exit_n: int, cost: float,
             years: float, seed: int) -> tuple[dict, dict]:
    close = frame["close"].to_numpy()
    held = spells(frame, entry_n, exit_n)
    equity, exposure, trades, at = curve_from_spells(close, held, cost)
    cagr, maxdd = performance(equity, years)
    ctrl_held = random_spells(len(close), held, seed)
    ctrl_equity, ctrl_exposure, ctrl_trades, ctrl_at = curve_from_spells(
        close, ctrl_held, cost)
    ctrl_cagr, ctrl_maxdd = performance(ctrl_equity, years)
    half = len(close) // 2

    def pack(label, c, d, expo, tr, entries):
        arr = np.array(tr) if tr else np.array([0.0])
        se = (float(arr.std(ddof=1)) / np.sqrt(len(arr))) if len(arr) > 1 else float("nan")
        idx = np.array(entries) if entries else np.array([0])
        h1 = arr[idx < half]
        h2 = arr[idx >= half]
        return {"run": label, "trades": len(tr),
                "win_rate_pct": round(float((arr > 0).mean()) * 100, 1),
                "mean_trade_pct": round(float(arr.mean()) * 100, 3),
                "se_pct": round(se * 100, 3) if np.isfinite(se) else None,
                "cagr_pct": round(c * 100, 2), "max_drawdown_pct": round(d * 100, 2),
                "ret_per_dd": round(abs(c / d), 2) if d else None,
                "time_in_market_pct": round(expo * 100, 1),
                "h1_mean_pct": round(float(h1.mean()) * 100, 3) if h1.size else None,
                "h2_mean_pct": round(float(h2.mean()) * 100, 3) if h2.size else None,
                "vs_random_sigma": None,
                "_mean": float(arr.mean()), "_se": se}

    strat = pack(f"turn-of-month (-{entry_n},+{exit_n})", cagr, maxdd, exposure,
                 trades, at)
    ctrl = pack("random windows", ctrl_cagr, ctrl_maxdd, ctrl_exposure,
                ctrl_trades, ctrl_at)
    spread = np.sqrt(strat["_se"] ** 2 + ctrl["_se"] ** 2)
    if np.isfinite(spread) and spread > 0:
        strat["vs_random_sigma"] = round((strat["_mean"] - ctrl["_mean"]) / spread, 2)
    return strat, ctrl


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=("index", "panel"), default="index")
    parser.add_argument("--universe", default="nifty50")
    parser.add_argument("--entry", type=int, default=5,
                        help="enter at the close of the Nth-LAST session of the month")
    parser.add_argument("--exit", dest="exit_n", type=int, default=3,
                        help="exit at the close of the Nth session of the new month")
    parser.add_argument("--sweep", action="store_true",
                        help="every entry/exit pair, not only the published one")
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--start", default=None)
    parser.add_argument("--random-seed", type=int, default=7)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    cost = args.cost_bps / 10_000

    if args.source == "index":
        frame = fetch_index(args.universe)
        label = f"{INDICES[args.universe]} ({args.universe})"
    else:
        frame = equal_weight_series(args.universe, args.start)
        label = f"equal-weight {args.universe} basket (survivorship-biased)"
    if args.start:
        frame = frame.filter(pl.col("date") >= pl.lit(args.start).str.to_date())
    frame = day_positions(frame.select("date", "close"))
    years = (frame["date"][-1] - frame["date"][0]).days / 365.25
    close = frame["close"].to_numpy()
    bench_cagr, bench_dd = performance(close / close[0], years)
    print(f"{label}: {frame.height:,} sessions, {frame['date'][0]} -> "
          f"{frame['date'][-1]}  ({years:.2f} years)")
    print(f"CONTROL buy-and-hold, fully invested: {bench_cagr * 100:+.2f}% CAGR / "
          f"{bench_dd * 100:.2f}% max DD  (ret/DD {abs(bench_cagr / bench_dd):.2f})")
    month_profile(frame)

    rows = []
    pairs = ([(e, x) for e in range(1, 8) for x in range(1, 6)] if args.sweep
             else [(args.entry, args.exit_n)])
    print(f"\n{'run':<26}{'trades':>8}{'win%':>7}{'mean%':>8}{'se%':>7}{'sigma':>7}"
          f"{'CAGR%':>8}{'maxDD%':>9}{'ret/DD':>8}{'inMkt%':>8}{'h1%':>8}{'h2%':>8}")
    print("-" * 112)
    for entry_n, exit_n in pairs:
        strat, ctrl = evaluate(frame, entry_n, exit_n, cost, years, args.random_seed)
        rows.append(strat)
        if not args.sweep:
            rows.append(ctrl)
        for row in ((strat, ctrl) if not args.sweep else (strat,)):
            sig = row["vs_random_sigma"]
            print(f"{row['run']:<26}{row['trades']:>8}{row['win_rate_pct']:>7.1f}"
                  f"{row['mean_trade_pct']:>8.3f}{(row['se_pct'] or 0):>7.3f}"
                  f"{(sig if sig is not None else float('nan')):>7.2f}"
                  f"{row['cagr_pct']:>8.2f}"
                  f"{row['max_drawdown_pct']:>9.2f}{(row['ret_per_dd'] or 0):>8.2f}"
                  f"{row['time_in_market_pct']:>8.1f}"
                  f"{(row['h1_mean_pct'] if row['h1_mean_pct'] is not None else float('nan')):>8.3f}"
                  f"{(row['h2_mean_pct'] if row['h2_mean_pct'] is not None else float('nan')):>8.3f}")
    print("-" * 112)
    print(f"{'BUY-AND-HOLD':<26}{'':>8}{'':>7}{'':>8}{'':>7}{'':>7}{bench_cagr * 100:>8.2f}"
          f"{bench_dd * 100:>9.2f}{abs(bench_cagr / bench_dd):>8.2f}{100.0:>8.1f}")
    if args.out:
        pl.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")}
                      for r in rows]).write_csv(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
