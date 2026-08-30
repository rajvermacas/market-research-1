"""Full backtest and stress-test of the RSI(2) 'dip buy' claims.

Produces output/results.json plus the tables printed to stdout.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import ES, NQ, Contract, Params, combine, compute_signals, metrics, run
from roll_adjust import back_adjust, detect_rolls

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "output"
OUT.mkdir(exist_ok=True)

CLAIMS = {
    "win_rate_since_2022": 0.83,
    "profit_factor_since_2022": 2.53,
    "ytd_2026_usd": 76_000,
    "green_years": "14/18",
    "cumulative_since_2009_usd": 335_000,
}


def load(stem: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{stem}.csv", parse_dates=["date"])


def slice_years(t: pd.DataFrame, lo: int, hi: int) -> pd.DataFrame:
    return t[(t["year"] >= lo) & (t["year"] <= hi)] if not t.empty else t


def yearly(trades: pd.DataFrame) -> pd.DataFrame:
    g = trades.groupby("year")
    return pd.DataFrame(
        {
            "trades": g.size(),
            "net_usd": g["net_usd"].sum(),
            "win_rate": g.apply(lambda x: (x["net_usd"] > 0).mean(), include_groups=False),
            "ret_pct_sum": g["ret_pct"].sum() * 100,
        }
    )


def date_equity(trades: pd.DataFrame) -> pd.Series:
    """Equity by exit date (P&L is booked when the trade closes)."""
    s = trades.set_index(pd.to_datetime(trades["exit_date"]))["net_usd"].sort_index()
    return s.groupby(level=0).sum().cumsum()


def drawdown_stats(equity: pd.Series) -> dict:
    dd = equity - equity.cummax()
    trough = dd.idxmin()
    peak = equity.loc[:trough].idxmax()
    rec = equity.loc[trough:][equity.loc[trough:] >= equity.loc[peak]]
    return {
        "max_dd_usd": float(dd.min()),
        "peak_date": str(peak.date()),
        "trough_date": str(trough.date()),
        "recovery_date": str(rec.index[0].date()) if len(rec) else None,
        "days_underwater": int(((rec.index[0] if len(rec) else equity.index[-1]) - peak).days),
    }


def exposure(df: pd.DataFrame, contract: Contract, p: Params) -> float:
    """Fraction of sessions the strategy holds a position."""
    trades = run(df, contract, p)
    bars_in = trades["bars_held"].sum()
    d = compute_signals(df, p).dropna(subset=["sma", "rsi"])
    return float(bars_in / len(d))


def buy_hold_compare(df: pd.DataFrame, contract: Contract, trades: pd.DataFrame,
                     lo: int, hi: int) -> dict:
    """What 1 contract held continuously over the same window would have made."""
    d = df[(df["date"].dt.year >= lo) & (df["date"].dt.year <= hi)]
    bh_pts = d["close"].iloc[-1] - d["close"].iloc[0]
    sub = slice_years(trades, lo, hi)
    return {
        "buy_hold_usd": float(bh_pts * contract.point_value),
        "strategy_usd": float(sub["net_usd"].sum()),
        "strategy_exposure_days": int(sub["bars_held"].sum()),
        "window_days": int(len(d)),
    }


def random_entry_benchmark(df: pd.DataFrame, contract: Contract, p: Params,
                           trades: pd.DataFrame, n_sims: int = 2000,
                           seed: int = 7) -> dict:
    """Does the RSI(2) timing beat entering on random days above the 200 SMA?

    Same number of trades, same holding-period distribution, same regime filter -
    only the entry *timing* is randomised. This isolates the claimed edge from
    the simple fact that the index goes up.
    """
    rng = np.random.default_rng(seed)
    d = compute_signals(df, p).dropna(subset=["sma", "rsi"]).reset_index(drop=True)
    eligible = np.flatnonzero(d["long_ok"].to_numpy())
    close = d["close"].to_numpy()

    holds = trades["bars_held"].to_numpy()
    n = len(trades)
    eligible = eligible[eligible + holds.max() < len(close)]

    sims = np.empty(n_sims)
    wins = np.empty(n_sims)
    for s in range(n_sims):
        idx = rng.choice(eligible, size=n, replace=True)
        h = rng.choice(holds, size=n, replace=True)
        pnl = (close[idx + h] - close[idx]) * contract.point_value - contract.cost_per_trade
        sims[s] = pnl.sum()
        wins[s] = (pnl > 0).mean()

    actual = float(trades["net_usd"].sum())
    return {
        "actual_usd": actual,
        "random_mean_usd": float(sims.mean()),
        "random_p95_usd": float(np.percentile(sims, 95)),
        "percentile_of_actual": float((sims < actual).mean() * 100),
        "actual_win_rate": float((trades["net_usd"] > 0).mean()),
        "random_mean_win_rate": float(wins.mean()),
    }


def main() -> None:
    es_raw, nq_raw = load("ES"), load("NQ")
    spx = load("SPX").set_index("date")["close"]
    ndx = load("NDX").set_index("date")["close"]

    es_adj, es_gaps = back_adjust(es_raw.set_index("date"), spx)
    nq_adj, nq_gaps = back_adjust(nq_raw.set_index("date"), ndx)
    es_adj = es_adj.reset_index()
    nq_adj = nq_adj.reset_index()

    results: dict = {"claims": CLAIMS}
    base = Params()

    datasets = {
        "raw": (es_raw, nq_raw),
        "roll_adjusted": (es_adj, nq_adj),
    }

    trades_by_set = {}
    for key, (e, n) in datasets.items():
        te, tn = run(e, ES, base), run(n, NQ, base)
        trades_by_set[key] = {"ES": te, "NQ": tn, "PORT": combine([te, tn])}

    # ---------- headline reproduction ----------
    repro = {}
    for key, tt in trades_by_set.items():
        for name, t in tt.items():
            for lo, hi, tag in [(2009, 2026, "2009_2026"), (2022, 2026, "2022_2026"),
                                (2001, 2008, "2001_2008")]:
                repro[f"{key}|{name}|{tag}"] = {
                    k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                    for k, v in metrics(slice_years(t, lo, hi)).items()
                }
    results["reproduction"] = repro

    port_raw = trades_by_set["raw"]["PORT"]
    port_adj = trades_by_set["roll_adjusted"]["PORT"]

    # ---------- roll-gap contamination ----------
    results["roll_gaps"] = {
        "es_rolls_detected": int(len(es_gaps)),
        "nq_rolls_detected": int(len(nq_gaps)),
        "es_mean_gap_pts": float(es_gaps.mean()),
        "nq_mean_gap_pts": float(nq_gaps.mean()),
        "net_2009_2026_raw": float(slice_years(port_raw, 2009, 2026)["net_usd"].sum()),
        "net_2009_2026_adjusted": float(slice_years(port_adj, 2009, 2026)["net_usd"].sum()),
    }

    # ---------- yearly / green years ----------
    yr_raw = yearly(slice_years(port_raw, 2009, 2026))
    yr_adj = yearly(slice_years(port_adj, 2009, 2026))
    results["yearly_raw"] = yr_raw.round(4).to_dict(orient="index")
    results["yearly_adjusted"] = yr_adj.round(4).to_dict(orient="index")
    results["green_years"] = {
        "raw": f"{int((yr_raw['net_usd'] > 0).sum())}/{len(yr_raw)}",
        "adjusted": f"{int((yr_adj['net_usd'] > 0).sum())}/{len(yr_adj)}",
    }
    results["ytd_2026"] = {
        "raw_usd": float(yr_raw.loc[2026, "net_usd"]) if 2026 in yr_raw.index else 0.0,
        "adjusted_usd": float(yr_adj.loc[2026, "net_usd"]) if 2026 in yr_adj.index else 0.0,
    }

    # ---------- drawdowns ----------
    results["drawdown"] = {
        "raw_2009_2026": drawdown_stats(date_equity(slice_years(port_raw, 2009, 2026))),
        "adjusted_2009_2026": drawdown_stats(date_equity(slice_years(port_adj, 2009, 2026))),
        "adjusted_full": drawdown_stats(date_equity(port_adj)),
    }

    # ---------- the sizing illusion ----------
    # 1 contract of NQ at 25,000 is 5x the risk of 1 contract at 5,000.
    for tag, t in [("raw", port_raw), ("adjusted", port_adj)]:
        sub = slice_years(t, 2009, 2026)
        by_half = {
            "2009_2017": slice_years(sub, 2009, 2017),
            "2018_2026": slice_years(sub, 2018, 2026),
        }
        results.setdefault("sizing_illusion", {})[tag] = {
            k: {
                "trades": int(len(v)),
                "net_usd": float(v["net_usd"].sum()),
                "mean_ret_pct": float(v["ret_pct"].mean() * 100),
                "sum_ret_pct": float(v["ret_pct"].sum() * 100),
                "mean_notional_usd": float(v["notional_usd"].mean()),
                "win_rate": float((v["net_usd"] > 0).mean()),
            }
            for k, v in by_half.items()
        }

    # ---------- tail risk with no stop ----------
    sub = slice_years(port_adj, 2009, 2026)
    results["tail_risk"] = {
        "worst_5_trades_usd": [float(x) for x in sub.nsmallest(5, "net_usd")["net_usd"]],
        "worst_5_dates": [str(pd.to_datetime(x).date()) for x in sub.nsmallest(5, "net_usd")["entry_date"]],
        "worst_mae_pct": float(sub["mae_pct"].min() * 100),
        "mean_mae_pct": float(sub["mae_pct"].mean() * 100),
        "pct_trades_underwater_5pct": float((sub["mae_pct"] < -0.05).mean() * 100),
        "avg_win_usd": float(sub[sub["net_usd"] > 0]["net_usd"].mean()),
        "avg_loss_usd": float(sub[sub["net_usd"] <= 0]["net_usd"].mean()),
        "loss_from_time_stops": float(sub[sub["exit_reason"] == "time_stop"]["net_usd"].sum()),
        "exit_reason_counts": sub["exit_reason"].value_counts().to_dict(),
    }

    # ---------- out-of-sample: before the equity curve starts ----------
    results["out_of_sample_2001_2008"] = {
        k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
        for k, v in metrics(slice_years(port_adj, 2001, 2008)).items()
    }

    # ---------- exposure and buy & hold ----------
    results["exposure"] = {
        "ES": exposure(es_adj, ES, base),
        "NQ": exposure(nq_adj, NQ, base),
    }
    results["buy_hold"] = {
        "ES_2009_2026": buy_hold_compare(es_adj, ES, trades_by_set["roll_adjusted"]["ES"], 2009, 2026),
        "NQ_2009_2026": buy_hold_compare(nq_adj, NQ, trades_by_set["roll_adjusted"]["NQ"], 2009, 2026),
    }

    # ---------- is the timing the edge? ----------
    results["random_entry"] = {
        "ES_2009_2026": random_entry_benchmark(
            es_adj, ES, base, slice_years(trades_by_set["roll_adjusted"]["ES"], 2009, 2026)),
        "NQ_2009_2026": random_entry_benchmark(
            nq_adj, NQ, base, slice_years(trades_by_set["roll_adjusted"]["NQ"], 2009, 2026)),
    }

    # ---------- robustness ----------
    variants = {
        "as_stated_close_entry": Params(),
        "next_open_entry": Params(entry_on="next_open"),
        "cutler_rsi": Params(rsi_kind="sma"),
        "rsi_entry_5": Params(rsi_entry=5.0),
        "rsi_entry_15": Params(rsi_entry=15.0),
        "rsi_exit_60": Params(rsi_exit=60.0),
        "rsi_exit_80": Params(rsi_exit=80.0),
        "max_hold_5": Params(max_hold=5),
        "max_hold_20": Params(max_hold=20),
        "sma_100": Params(sma_period=100),
        "sma_50": Params(sma_period=50),
    }
    rob = {}
    for name, p in variants.items():
        te, tn = run(es_adj, ES, p), run(nq_adj, NQ, p)
        port = slice_years(combine([te, tn]), 2009, 2026)
        m = metrics(port)
        rob[name] = {
            "trades": m["trades"],
            "win_rate": float(m["win_rate"]),
            "profit_factor": float(m["profit_factor"]),
            "net_usd": float(m["net_usd"]),
            "max_dd_usd": float(m["max_dd_usd"]),
        }
    results["robustness"] = rob

    # ---------- cost sensitivity ----------
    costs = {}
    for slip in (0.0, 1.0, 2.0, 4.0):
        e = Contract("ES", 50.0, 0.25, slippage_ticks=slip)
        n = Contract("NQ", 20.0, 0.25, slippage_ticks=slip)
        port = slice_years(combine([run(es_adj, e, base), run(nq_adj, n, base)]), 2009, 2026)
        costs[f"{slip:g}_tick_slippage"] = {
            "net_usd": float(port["net_usd"].sum()),
            "cost_per_rt_es": e.cost_per_trade,
            "profit_factor": float(metrics(port)["profit_factor"]),
        }
    results["cost_sensitivity"] = costs

    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str))

    port_adj.to_csv(OUT / "trades_roll_adjusted.csv", index=False)
    port_raw.to_csv(OUT / "trades_raw.csv", index=False)
    print(f"wrote {OUT/'results.json'}  ({len(port_adj)} adjusted trades)")


if __name__ == "__main__":
    main()
