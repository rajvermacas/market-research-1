"""The same RSI(2) dip-buy rules, run on the Indian market.

The strategy was published for ES and NQ. This asks whether the effect is a
property of US index futures or of index futures generally, by running the
identical rules on the two most-traded NSE contracts.

Two things differ from the US run and both are handled explicitly:

1. There is no usable continuous NSE futures series, so the backtest runs on the
   cash index and charges the long-futures cost of carry (repo less dividend
   yield) over each holding period. Ignoring it would flatter the result.
2. Indian costs are proportional, not flat. STT alone is 0.02% of the sell side.
   Against a ~0.4% edge per trade that is a real deduction, so the full statutory
   stack is modelled rather than a flat commission.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from backtest import (BANKNIFTY, ES, INDIA_CARRY, INDIA_PCT_COST, NIFTY, NQ,
                      Contract, Params, combine, compute_signals, metrics, run)
from roll_adjust import back_adjust

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "output"

START = 2008  # first full year after the 200-day SMA warms up on Sep-2007 data


def load(stem):
    return pd.read_csv(DATA / f"{stem}.csv", parse_dates=["date"])


def yrs(t, lo=START, hi=2026):
    return t[(t["year"] >= lo) & (t["year"] <= hi)] if not t.empty else t


def random_entry(df, contract, p, trades, n_sims=2000, seed=11):
    """Same significance test as the US run: randomise entry timing only."""
    rng = np.random.default_rng(seed)
    d = compute_signals(df, p).dropna(subset=["sma", "rsi"]).reset_index(drop=True)
    close = d["close"].to_numpy()
    holds = trades["bars_held"].to_numpy()
    eligible = np.flatnonzero(d["long_ok"].to_numpy())
    eligible = eligible[eligible + holds.max() < len(close)]
    n = len(trades)
    sims = np.empty(n_sims)
    for s in range(n_sims):
        idx = rng.choice(eligible, size=n, replace=True)
        h = rng.choice(holds, size=n, replace=True)
        sims[s] = ((close[idx + h] - close[idx]) / close[idx]).sum()
    actual = float(trades["ret_pct"].sum())
    return {
        "actual_sum_ret_pct": actual * 100,
        "random_mean_sum_ret_pct": float(sims.mean() * 100),
        "percentile_of_actual": float((sims < actual).mean() * 100),
    }


def dd_from_trades(t):
    eq = t.set_index(pd.to_datetime(t["exit_date"]))["net_usd"].sort_index()
    eq = eq.groupby(level=0).sum().cumsum()
    return float((eq - eq.cummax()).min())


def summarise(t, contract, label):
    t = yrs(t)
    m = metrics(t)
    r = t["ret_pct"].to_numpy()
    ts = stats.ttest_1samp(r, 0.0)
    return {
        "label": label,
        "currency": contract.currency,
        "trades": int(m["trades"]),
        "win_rate": float(m["win_rate"]),
        "profit_factor": float(m["profit_factor"]),
        "net_ccy": float(m["net_usd"]),
        "sum_ret_pct": float(r.sum() * 100),
        "mean_ret_pct": float(r.mean() * 100),
        "t_stat": float(ts.statistic),
        "p_value": float(ts.pvalue),
        "avg_win_ccy": float(m["avg_win"]),
        "avg_loss_ccy": float(m["avg_loss"]),
        "worst_ccy": float(m["worst"]),
        "worst_mae_pct": float(t["mae_pct"].min() * 100),
        "avg_bars": float(m["avg_bars"]),
        "max_dd_ccy": dd_from_trades(t),
        "first": str(m["first"]),
        "last": str(m["last"]),
        "cost_share_of_gross_pct": float(t["cost_usd"].sum() / t["gross_usd"].abs().sum() * 100),
    }


def main():
    p = Params()
    nifty, bank = load("NIFTY"), load("BANKNIFTY")

    t_nifty = run(nifty, NIFTY, p)
    t_bank = run(bank, BANKNIFTY, p)

    out = {"note": "cash indices used as futures proxies; carry and full statutory costs charged"}
    out["nifty"] = summarise(t_nifty, NIFTY, "Nifty 50")
    out["banknifty"] = summarise(t_bank, BANKNIFTY, "Nifty Bank")

    # portfolio of 1 lot each, in rupees
    port = yrs(combine([t_nifty, t_bank]))
    out["portfolio"] = {
        "trades": int(len(port)),
        "win_rate": float((port["net_usd"] > 0).mean()),
        "net_inr": float(port["net_usd"].sum()),
        "profit_factor": float(metrics(port)["profit_factor"]),
        "max_dd_inr": dd_from_trades(port),
        "sum_ret_pct": float(port["ret_pct"].sum() * 100),
    }

    # ---- decompose the edge: raw price move, then each cost layer ----
    # ret_pct is always the *gross* price move, so net has to be recomputed.
    def spec(**kw):
        return (Contract("NIFTY", 75.0, currency="INR", **kw),
                Contract("BANKNIFTY", 30.0, currency="INR", **kw))

    layers = {
        "gross_price_move": spec(slippage_points=0.0, commission_rt=0.0),
        "after_fees_and_slippage": spec(slippage_points=1.0, commission_rt=47.0,
                                        pct_cost_rt=INDIA_PCT_COST),
        "after_fees_and_carry": spec(slippage_points=1.0, commission_rt=47.0,
                                     pct_cost_rt=INDIA_PCT_COST, carry_pct_yr=INDIA_CARRY),
    }
    drag = {}
    for name, (cn, cb) in layers.items():
        t = yrs(combine([run(nifty, cn, p), run(bank, cb, p)]))
        net_pct = t["net_usd"] / t["notional_usd"]
        drag[name] = {
            "mean_net_ret_pct_per_trade": float(net_pct.mean() * 100),
            "sum_net_ret_pct": float(net_pct.sum() * 100),
            "net_inr": float(t["net_usd"].sum()),
            "win_rate": float((t["net_usd"] > 0).mean()),
            "profit_factor": float(metrics(t)["profit_factor"]),
        }
    drag["carry_cost_pct_per_trade"] = float(
        INDIA_CARRY * (port["bars_held"].mean() / 252.0) * 100)
    drag["total_cost_pct_per_trade"] = float(
        (port["cost_usd"] / port["notional_usd"]).mean() * 100)
    out["cost_drag"] = drag

    # ---- significance ----
    out["random_entry"] = {
        "nifty": random_entry(nifty, NIFTY, p, yrs(t_nifty)),
        "banknifty": random_entry(bank, BANKNIFTY, p, yrs(t_bank)),
    }

    # ---- vs buy and hold, and exposure ----
    bh = {}
    for df, c, t in [(nifty, NIFTY, t_nifty), (bank, BANKNIFTY, t_bank)]:
        w = df[df["date"].dt.year >= START]
        d = compute_signals(df, p).dropna(subset=["sma", "rsi"])
        d = d[d["date"].dt.year >= START]
        bh[c.name] = {
            "buy_hold_pct": float((w["close"].iloc[-1] / w["close"].iloc[0] - 1) * 100),
            "buy_hold_inr": float((w["close"].iloc[-1] - w["close"].iloc[0]) * c.point_value),
            "strategy_inr": float(yrs(t)["net_usd"].sum()),
            "strategy_sum_ret_pct": float(yrs(t)["ret_pct"].sum() * 100),
            "exposure_pct": float(yrs(t)["bars_held"].sum() / len(d) * 100),
        }
    out["vs_buy_hold"] = bh

    # ---- per year ----
    per_year = port.groupby("year").agg(
        trades=("net_usd", "size"),
        net_inr=("net_usd", "sum"),
        sum_ret_pct=("ret_pct", lambda x: round(x.sum() * 100, 2)),
        win_rate=("net_usd", lambda x: round((x > 0).mean(), 3)),
    )
    out["per_year"] = {int(k): {kk: float(vv) for kk, vv in v.items()}
                       for k, v in per_year.to_dict(orient="index").items()}
    out["green_years"] = f"{int((per_year['net_inr'] > 0).sum())}/{len(per_year)}"

    # ---- head to head with the US, on the same window and the same unit ----
    spx = load("SPX").set_index("date")["close"]
    ndx = load("NDX").set_index("date")["close"]
    es_adj = back_adjust(load("ES").set_index("date"), spx)[0].reset_index()
    nq_adj = back_adjust(load("NQ").set_index("date"), ndx)[0].reset_index()
    us = yrs(combine([run(es_adj, ES, p), run(nq_adj, NQ, p)]))
    head = {}
    for tag, t in [("US_ES_NQ", us), ("India_NIFTY_BANKNIFTY", port)]:
        r = t["ret_pct"].to_numpy()
        head[tag] = {
            "window": f"{START}-2026",
            "trades": int(len(t)),
            "win_rate": float((t["net_usd"] > 0).mean()),
            "mean_ret_pct": float(r.mean() * 100),
            "sum_ret_pct": float(r.sum() * 100),
            "t_stat": float(stats.ttest_1samp(r, 0.0).statistic),
            "profit_factor": float(metrics(t)["profit_factor"]),
            "avg_bars": float(t["bars_held"].mean()),
        }
    out["head_to_head"] = head

    # ---- does the pattern exist anywhere else in India? ----
    breadth = {}
    for stem, lot in [("NIFTY", 75.0), ("BANKNIFTY", 30.0), ("NIFTYIT", 1.0), ("SENSEX", 1.0)]:
        df = load(stem)
        c = Contract(stem, lot, slippage_points=0.0, commission_rt=0.0, currency="INR")
        t = yrs(run(df, c, p))
        if t.empty:
            continue
        r = t["ret_pct"].to_numpy()
        breadth[stem] = {
            "trades": int(len(t)),
            "win_rate": float((r > 0).mean()),
            "mean_gross_ret_pct": float(r.mean() * 100),
            "t_stat": float(stats.ttest_1samp(r, 0.0).statistic),
            "p_value": float(stats.ttest_1samp(r, 0.0).pvalue),
        }
    out["breadth_gross"] = breadth

    # ---- worst trades, for the tail ----
    worst = port.nsmallest(5, "net_usd")[
        ["entry_date", "exit_date", "symbol", "net_usd", "ret_pct", "mae_pct", "exit_reason"]]
    out["worst_trades"] = [
        {k: (str(v) if k.endswith("date") or k in ("symbol", "exit_reason") else float(v))
         for k, v in row.items()}
        for row in worst.to_dict(orient="records")
    ]

    (OUT / "india.json").write_text(json.dumps(out, indent=2, default=str))
    port.to_csv(OUT / "trades_india.csv", index=False)

    print(json.dumps({k: v for k, v in out.items() if k != "per_year"}, indent=2, default=str))
    print("\nPER YEAR (1 NIFTY + 1 BANKNIFTY lot, INR)")
    print(per_year.to_string())


def export_charts():
    """Series for the India section of the published report."""
    import pandas as pd

    p = Params()
    nifty, bank = load("NIFTY"), load("BANKNIFTY")
    port = yrs(combine([run(nifty, NIFTY, p), run(bank, BANKNIFTY, p)]))
    port["exit_date"] = pd.to_datetime(port["exit_date"])
    port["net_pct"] = port["net_usd"] / port["notional_usd"]

    spx = load("SPX").set_index("date")["close"]
    ndx = load("NDX").set_index("date")["close"]
    es_adj = back_adjust(load("ES").set_index("date"), spx)[0].reset_index()
    nq_adj = back_adjust(load("NQ").set_index("date"), ndx)[0].reset_index()
    us = yrs(combine([run(es_adj, ES, p), run(nq_adj, NQ, p)]))
    us["exit_date"] = pd.to_datetime(us["exit_date"])
    us["net_pct"] = us["net_usd"] / us["notional_usd"]

    def curve(t):
        s = t.groupby("exit_date")["net_pct"].sum().cumsum() * 100
        s = s.resample("ME").last().ffill()
        return [{"d": d.strftime("%Y-%m"), "v": round(float(v), 2)} for d, v in s.items()]

    def by_year(t):
        g = t.groupby("year").agg(
            net_pct=("net_pct", lambda x: round(x.sum() * 100, 2)),
            trades=("net_usd", "size"),
            win_rate=("net_usd", lambda x: round((x > 0).mean(), 3)),
            net_ccy=("net_usd", "sum"),
        )
        return [{"year": int(y), "net_pct": float(r.net_pct), "trades": int(r.trades),
                 "win_rate": float(r.win_rate), "net_ccy": round(float(r.net_ccy))}
                for y, r in g.iterrows()]

    payload = {
        "curve_india": curve(port),
        "curve_us": curve(us),
        "year_india": by_year(port),
        "year_us": by_year(us),
        "trades_india": [{"ret": round(float(r.ret_pct) * 100, 3), "sym": r.symbol}
                         for r in port.itertuples()],
    }
    (OUT / "india_charts.json").write_text(json.dumps(payload, separators=(",", ":")))
    print("wrote india_charts.json")


if __name__ == "__main__":
    main()
    export_charts()
