"""Export the series the report charts need."""

import json
from pathlib import Path

import pandas as pd

from backtest import ES, NQ, Params, combine, run
from roll_adjust import back_adjust

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "output"


def load(s):
    return pd.read_csv(DATA / f"{s}.csv", parse_dates=["date"])


def main():
    es, nq = load("ES"), load("NQ")
    spx = load("SPX").set_index("date")["close"]
    ndx = load("NDX").set_index("date")["close"]
    es_adj = back_adjust(es.set_index("date"), spx)[0].reset_index()
    nq_adj = back_adjust(nq.set_index("date"), ndx)[0].reset_index()

    p = Params()
    raw = combine([run(es, ES, p), run(nq, NQ, p)])
    adj = combine([run(es_adj, ES, p), run(nq_adj, NQ, p)])

    payload = {}
    for tag, t in [("raw", raw), ("adjusted", adj)]:
        t = t[t["year"] >= 2009].copy()
        t["exit_date"] = pd.to_datetime(t["exit_date"])
        eq = t.groupby("exit_date")["net_usd"].sum().cumsum()
        payload[f"equity_{tag}"] = [
            {"d": d.strftime("%Y-%m-%d"), "v": round(float(v))} for d, v in eq.items()
        ]

    mtm = pd.read_csv(OUT / "mtm_equity.csv", index_col=0, parse_dates=True)["equity_usd"]
    mtm = mtm.resample("W").last().dropna()
    payload["equity_mtm"] = [
        {"d": d.strftime("%Y-%m-%d"), "v": round(float(v))} for d, v in mtm.items()
    ]

    a = adj[adj["year"] >= 2009]
    per_year = a.groupby("year").agg(
        net_usd=("net_usd", "sum"),
        sum_ret_pct=("ret_pct", lambda x: round(x.sum() * 100, 2)),
        trades=("net_usd", "size"),
        win_rate=("net_usd", lambda x: round((x > 0).mean(), 3)),
        mean_notional=("notional_usd", "mean"),
    ).round(0)
    payload["per_year"] = [
        {"year": int(y), **{k: float(v) for k, v in row.items()}}
        for y, row in per_year.iterrows()
    ]

    # buy & hold on the same 1 ES + 1 NQ, same window
    j = (es_adj.set_index("date")["close"] * ES.point_value
         + nq_adj.set_index("date")["close"] * NQ.point_value)
    j = j[j.index.year >= 2009]
    j = (j - j.iloc[0]).resample("W").last().dropna()
    payload["buy_hold"] = [{"d": d.strftime("%Y-%m-%d"), "v": round(float(v))} for d, v in j.items()]

    payload["trades"] = [
        {
            "d": pd.to_datetime(r.entry_date).strftime("%Y-%m-%d"),
            "sym": r.symbol,
            "usd": round(float(r.net_usd)),
            "ret": round(float(r.ret_pct) * 100, 3),
            "mae": round(float(r.mae_pct) * 100, 2),
            "bars": int(r.bars_held),
            "reason": r.exit_reason,
        }
        for r in a.itertuples()
    ]

    (OUT / "chart_data.json").write_text(json.dumps(payload))
    print("wrote chart_data.json", {k: len(v) for k, v in payload.items()})


if __name__ == "__main__":
    main()
