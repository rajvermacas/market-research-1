"""Second-pass analysis: the things a headline equity curve hides."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from backtest import ES, NQ, Params, combine, compute_signals, run
from roll_adjust import back_adjust

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "output"


def load(stem):
    return pd.read_csv(DATA / f"{stem}.csv", parse_dates=["date"])


def daily_mtm(df: pd.DataFrame, contract, p: Params) -> pd.Series:
    """Daily mark-to-market equity in $, so open-trade pain is visible.

    Closed-trade equity curves hide the worst of a no-stop strategy: the loss
    only appears the day you finally exit.
    """
    d = compute_signals(df, p).dropna(subset=["sma", "rsi"]).reset_index(drop=True)
    trades = run(df, contract, p)
    pos = pd.Series(0.0, index=d["date"])
    entry_px = pd.Series(np.nan, index=d["date"])
    idx = {dt: i for i, dt in enumerate(d["date"])}

    pnl = pd.Series(0.0, index=d["date"])
    for _, t in trades.iterrows():
        i0, i1 = idx[t["entry_date"]], idx[t["exit_date"]]
        seg = d.loc[i0:i1]
        # daily change in open-trade value, cost booked at exit
        marks = seg["close"].diff().fillna(0.0) * contract.point_value
        pnl.iloc[i0 : i1 + 1] += marks.to_numpy()
        pnl.iloc[i1] -= contract.cost_per_trade
    return pnl.cumsum()


def dd_stats(eq: pd.Series) -> dict:
    dd = eq - eq.cummax()
    trough = dd.idxmin()
    peak = eq.loc[:trough].idxmax()
    after = eq.loc[trough:]
    rec = after[after >= eq.loc[peak]]
    return {
        "max_dd_usd": float(dd.min()),
        "peak": str(peak.date()),
        "trough": str(trough.date()),
        "recovered": str(rec.index[0].date()) if len(rec) else "not recovered",
        "days_underwater": int(((rec.index[0] if len(rec) else eq.index[-1]) - peak).days),
    }


def main():
    es, nq = load("ES"), load("NQ")
    spx = load("SPX").set_index("date")["close"]
    ndx = load("NDX").set_index("date")["close"]
    es_adj = back_adjust(es.set_index("date"), spx)[0].reset_index()
    nq_adj = back_adjust(nq.set_index("date"), ndx)[0].reset_index()

    p = Params()
    out = {}

    # ---- mark-to-market drawdown, the number that decides your margin ----
    eq_es, eq_nq = daily_mtm(es_adj, ES, p), daily_mtm(nq_adj, NQ, p)
    port_eq = (eq_es.reindex(eq_es.index).fillna(0) + eq_nq.reindex(eq_es.index).fillna(0))
    port_eq = port_eq[port_eq.index.year >= 2009]
    port_eq = port_eq - port_eq.iloc[0]
    out["mtm_drawdown_2009_2026"] = dd_stats(port_eq)
    out["closed_trade_vs_mtm"] = {
        "note": "closed-trade equity books the loss only on exit; MTM shows what the account saw",
    }

    te, tn = run(es_adj, ES, p), run(nq_adj, NQ, p)
    port = combine([te, tn])
    port = port[port["year"] >= 2009]
    port["entry_date"] = pd.to_datetime(port["entry_date"])

    # ---- is the edge growing, or just the index? ----
    per_year = port.groupby("year").agg(
        trades=("net_usd", "size"),
        net_usd=("net_usd", "sum"),
        mean_ret_pct=("ret_pct", lambda x: x.mean() * 100),
        sum_ret_pct=("ret_pct", lambda x: x.sum() * 100),
        mean_notional=("notional_usd", "mean"),
        win_rate=("net_usd", lambda x: (x > 0).mean()),
    )
    out["per_year"] = per_year.round(3).to_dict(orient="index")

    yrs = per_year.index.to_numpy(dtype=float)
    for col in ("net_usd", "sum_ret_pct"):
        sl = stats.linregress(yrs, per_year[col].to_numpy())
        out.setdefault("trend", {})[col] = {
            "slope_per_year": float(sl.slope),
            "p_value": float(sl.pvalue),
            "r2": float(sl.rvalue ** 2),
        }

    # ---- concentration ----
    total = port["net_usd"].sum()
    out["concentration"] = {
        "total_2009_2026_usd": float(total),
        "share_from_2024_2026_pct": float(port[port["year"] >= 2024]["net_usd"].sum() / total * 100),
        "share_from_2026_ytd_pct": float(port[port["year"] == 2026]["net_usd"].sum() / total * 100),
        "share_from_top_10_trades_pct": float(port.nlargest(10, "net_usd")["net_usd"].sum() / total * 100),
        "share_from_NQ_pct": float(port[port["symbol"] == "NQ"]["net_usd"].sum() / total * 100),
        "years_2009_2017_usd": float(port[port["year"] <= 2017]["net_usd"].sum()),
        "years_2018_2026_usd": float(port[port["year"] >= 2018]["net_usd"].sum()),
    }

    # ---- is the per-trade % edge statistically real? ----
    r = port["ret_pct"].to_numpy()
    t_stat, p_val = stats.ttest_1samp(r, 0.0)
    out["edge_significance"] = {
        "mean_ret_pct": float(r.mean() * 100),
        "median_ret_pct": float(np.median(r) * 100),
        "std_ret_pct": float(r.std(ddof=1) * 100),
        "t_stat": float(t_stat),
        "p_value": float(p_val),
        "n": int(len(r)),
    }
    # ...and split by half, to see whether it is decaying
    half = len(port) // 2
    for tag, seg in [("first_half", port.iloc[:half]), ("second_half", port.iloc[half:])]:
        rr = seg["ret_pct"].to_numpy()
        out["edge_significance"][tag] = {
            "period": f"{seg['year'].min()}-{seg['year'].max()}",
            "mean_ret_pct": float(rr.mean() * 100),
            "t_stat": float(stats.ttest_1samp(rr, 0.0).statistic),
        }

    # ---- capital actually required ----
    # CME initial margin is roughly 5-7% of notional for ES/NQ
    latest_es = es_adj["close"].iloc[-1] * ES.point_value
    latest_nq = nq_adj["close"].iloc[-1] * NQ.point_value
    margin = 0.06 * (latest_es + latest_nq)
    dd = abs(out["mtm_drawdown_2009_2026"]["max_dd_usd"])
    capital = margin + dd
    years = 2026.66 - 2009
    out["capital_required"] = {
        "es_notional_usd": float(latest_es),
        "nq_notional_usd": float(latest_nq),
        "est_initial_margin_usd": float(margin),
        "max_mtm_drawdown_usd": float(dd),
        "sane_account_size_usd": float(capital),
        "total_pnl_usd": float(total),
        "simple_annual_return_on_that_capital_pct": float(total / capital / years * 100),
    }

    # ---- what buy & hold did over the same window, same instruments ----
    bh = 0.0
    for d_, c in [(es_adj, ES), (nq_adj, NQ)]:
        w = d_[d_["date"].dt.year >= 2009]
        bh += (w["close"].iloc[-1] - w["close"].iloc[0]) * c.point_value
    out["vs_buy_hold"] = {
        "buy_hold_1es_1nq_usd": float(bh),
        "strategy_usd": float(total),
        "strategy_capture_pct": float(total / bh * 100),
        "strategy_exposure_pct_of_days": float(port["bars_held"].sum() / 2 / 4442 * 100),
    }

    (OUT / "deep_dive.json").write_text(json.dumps(out, indent=2, default=str))
    port_eq.to_frame("equity_usd").to_csv(OUT / "mtm_equity.csv")
    print(json.dumps({k: v for k, v in out.items() if k != "per_year"}, indent=2, default=str))
    print("\nPER YEAR")
    print(per_year.round(2).to_string())


if __name__ == "__main__":
    main()
