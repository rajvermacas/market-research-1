"""The RSI(2) dip buy on NSE cash equities.

The strategy was published for index futures. This runs the identical rules
across the Nifty 500 as single stocks, which changes three things that matter:

1. **Costs go up, a lot.** Delivery equity pays STT at 0.1% on *each* side, where
   futures pay 0.02% on the sell alone. Round-trip friction lands near 0.32% of
   position value - the same order of magnitude as the whole edge.
2. **Survivorship bias appears.** The Nifty 500 is today's list; its members are
   the companies that made it. Any long-only backtest on it is flattered. The
   random-entry benchmark is the defence: it trades the same survivor universe,
   so whatever bias inflates the strategy inflates the benchmark equally.
3. **Signals cluster.** In a selloff, hundreds of stocks trip RSI(2) < 10 on the
   same day. A real account cannot take them all, so a capacity-capped portfolio
   is modelled alongside the uncapped edge measurement.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from backtest import Contract, Params, compute_signals, run

ROOT = Path(__file__).resolve().parents[1]
DATA, NSE, OUT = ROOT / "data", ROOT / "data" / "nse", ROOT / "output"

START = 2008
CAPITAL_PER_TRADE = 100_000.0     # fixed rupee size, so no sizing illusion
MIN_TURNOVER_CR = 5.0             # median daily traded value, rupees crore
MIN_BARS = 500

# Delivery equity round-trip friction, as a fraction of position value:
#   STT 0.1% buy + 0.1% sell            0.00200
#   exchange txn 0.00297% x 2           0.00006
#   stamp duty 0.015% on buy            0.00015
#   SEBI + GST                          0.00002
#   slippage 0.05% a side               0.00100
DELIVERY_COST_RT = 0.00323
FNO_COST_RT = 0.00126   # STT 0.02% sell + fees + 0.05% slippage a side, no carry shown


def universe() -> list[Path]:
    return sorted(NSE.glob("*.csv"))


def load(path: Path) -> pd.DataFrame | None:
    df = pd.read_csv(path, parse_dates=["date"])
    if len(df) < MIN_BARS:
        return None
    return df


def liquid(df: pd.DataFrame) -> bool:
    """Median daily turnover over the traded window, in rupees crore."""
    recent = df[df["date"].dt.year >= START]
    if len(recent) < 250:
        return False
    turnover = (recent["close"] * recent["volume"]).median() / 1e7
    return bool(turnover >= MIN_TURNOVER_CR)


def contract(sym: str, cost_rt: float) -> Contract:
    """One rupee of index point = one rupee, so notional is just the share price."""
    return Contract(sym, point_value=1.0, slippage_points=0.0, commission_rt=0.0,
                    pct_cost_rt=cost_rt, currency="INR")


def run_universe(p: Params | None = None) -> pd.DataFrame:
    """One pass over the universe, before costs.

    Round-trip friction here is a flat fraction of the entry price and does not
    depend on the trade's path, so every cost regime is just a constant shift of
    the gross return - `apply_cost` does that instead of re-walking the data.
    """
    p = p or Params()
    frames = []
    for path in universe():
        df = load(path)
        if df is None or not liquid(df):
            continue
        sym = path.stem
        t = run(df, contract(sym, 0.0), p)
        if t.empty:
            continue
        t = t[t["year"] >= START].copy()
        if t.empty:
            continue
        t["symbol"] = sym
        frames.append(t)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def apply_cost(t: pd.DataFrame, cost_rt: float) -> pd.DataFrame:
    """Every cost regime is a constant subtraction from the gross return."""
    out = t.copy()
    out["net_pct"] = out["ret_pct"] - cost_rt
    out["pnl_inr"] = out["net_pct"] * CAPITAL_PER_TRADE
    return out


def describe(t: pd.DataFrame, label: str) -> dict:
    r = t["net_pct"].to_numpy()
    wins, losses = r[r > 0], r[r <= 0]
    ts = stats.ttest_1samp(r, 0.0)
    return {
        "label": label,
        "symbols": int(t["symbol"].nunique()),
        "trades": int(len(t)),
        "win_rate": float((r > 0).mean()),
        "mean_net_pct": float(r.mean() * 100),
        "median_net_pct": float(np.median(r) * 100),
        "t_stat": float(ts.statistic),
        "p_value": float(ts.pvalue),
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.size else float("inf"),
        "avg_win_pct": float(wins.mean() * 100) if wins.size else 0.0,
        "avg_loss_pct": float(losses.mean() * 100) if losses.size else 0.0,
        "avg_bars": float(t["bars_held"].mean()),
        "worst_pct": float(r.min() * 100),
        "worst_mae_pct": float(t["mae_pct"].min() * 100),
        "total_pnl_inr_at_1L": float(t["pnl_inr"].sum()),
    }


def random_entry(p: Params, base: pd.DataFrame, n_sims: int = 400, seed: int = 3) -> dict:
    """Survivorship-neutral benchmark: same universe, same holds, random entry days.

    Because the benchmark trades the identical survivor list, any bias from using
    today's Nifty 500 lifts both numbers. What survives the comparison is timing.
    """
    rng = np.random.default_rng(seed)
    pools, holdpool = [], []
    for path in universe():
        df = load(path)
        if df is None or not liquid(df):
            continue
        d = compute_signals(df, p).dropna(subset=["sma", "rsi"]).reset_index(drop=True)
        d = d[d["date"].dt.year >= START].reset_index(drop=True)
        if len(d) < 100:
            continue
        elig = np.flatnonzero(d["long_ok"].to_numpy())
        elig = elig[elig < len(d) - 25]
        if elig.size:
            pools.append((d["close"].to_numpy(), elig))

    holdpool = base["bars_held"].to_numpy()
    n = len(base)
    actual = float(base["ret_pct"].mean())

    sims = np.empty(n_sims)
    for s in range(n_sims):
        pick = rng.integers(0, len(pools), size=n)
        acc = np.empty(n)
        for i, pi in enumerate(pick):
            close, elig = pools[pi]
            j = elig[rng.integers(0, elig.size)]
            h = holdpool[rng.integers(0, holdpool.size)]
            k = min(j + h, len(close) - 1)
            acc[i] = close[k] / close[j] - 1.0
        sims[s] = acc.mean()
    return {
        "actual_mean_gross_pct": actual * 100,
        "random_mean_gross_pct": float(sims.mean() * 100),
        "random_p95_pct": float(np.percentile(sims, 95) * 100),
        "percentile_of_actual": float((sims < actual).mean() * 100),
        "n_sims": n_sims,
    }


def concurrency(t: pd.DataFrame) -> dict:
    """How many positions the uncapped strategy wants open at once."""
    events = []
    for r in t.itertuples():
        events.append((pd.Timestamp(r.entry_date), 1))
        events.append((pd.Timestamp(r.exit_date), -1))
    ev = pd.DataFrame(events, columns=["d", "x"]).groupby("d")["x"].sum().sort_index()
    open_n = ev.cumsum()
    return {
        "median_open": float(open_n.median()),
        "p90_open": float(open_n.quantile(0.90)),
        "max_open": int(open_n.max()),
        "max_open_date": str(open_n.idxmax().date()),
        "capital_needed_at_max_inr": float(open_n.max() * CAPITAL_PER_TRADE),
    }


def capped_portfolio(t: pd.DataFrame, cap: int = 10) -> dict:
    """Equal-rupee book with at most `cap` positions, first-come by signal date.

    Ties on a date are broken by the lowest entry RSI - deepest dip first, which
    is information available at the signal and so carries no look-ahead.
    """
    t = t.sort_values(["entry_date", "entry_rsi"]).reset_index(drop=True)
    open_until: list[pd.Timestamp] = []
    taken = []
    for r in t.itertuples():
        ed = pd.Timestamp(r.entry_date)
        open_until = [x for x in open_until if x > ed]
        if len(open_until) >= cap:
            continue
        open_until.append(pd.Timestamp(r.exit_date))
        taken.append(r.Index)
    sub = t.loc[taken]
    daily = sub.copy()
    daily["exit_date"] = pd.to_datetime(daily["exit_date"])
    eq = daily.groupby("exit_date")["pnl_inr"].sum().sort_index().cumsum()
    dd = eq - eq.cummax()
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    deployed = cap * CAPITAL_PER_TRADE
    return {
        "cap": cap,
        "trades_taken": int(len(sub)),
        "trades_skipped": int(len(t) - len(sub)),
        "win_rate": float((sub["net_pct"] > 0).mean()),
        "total_pnl_inr": float(sub["pnl_inr"].sum()),
        "capital_deployed_inr": deployed,
        "return_on_capital_pct_total": float(sub["pnl_inr"].sum() / deployed * 100),
        "return_on_capital_pct_yr": float(sub["pnl_inr"].sum() / deployed / years * 100),
        "max_dd_inr": float(dd.min()),
        "max_dd_pct_of_capital": float(dd.min() / deployed * 100),
        "years": float(years),
    }


def main() -> None:
    p = Params()
    out: dict = {"universe_file": "nifty500", "capital_per_trade_inr": CAPITAL_PER_TRADE}

    base = run_universe(p)
    gross = apply_cost(base, 0.0)
    net = apply_cost(base, DELIVERY_COST_RT)
    fno = apply_cost(base, FNO_COST_RT)

    out["gross"] = describe(gross, "Before costs")
    out["delivery"] = describe(net, "After delivery-equity costs (0.323% round trip)")
    out["stock_futures"] = describe(fno, "After stock-futures costs (0.126% round trip)")

    out["cost_sensitivity"] = {}
    for c in (0.0, 0.001, 0.002, 0.00323, 0.005):
        t = apply_cost(base, c)
        out["cost_sensitivity"][f"{c*100:.3f}pct_rt"] = {
            "mean_net_pct": float(t["net_pct"].mean() * 100),
            "win_rate": float((t["net_pct"] > 0).mean()),
            "total_pnl_inr_at_1L": float(t["pnl_inr"].sum()),
        }

    per_year = net.groupby("year").agg(
        trades=("net_pct", "size"),
        mean_net_pct=("net_pct", lambda x: round(x.mean() * 100, 3)),
        win_rate=("net_pct", lambda x: round((x > 0).mean(), 3)),
        pnl_inr=("pnl_inr", "sum"),
    )
    out["per_year"] = {int(k): {kk: float(vv) for kk, vv in v.items()}
                       for k, v in per_year.to_dict(orient="index").items()}
    out["green_years"] = f"{int((per_year['pnl_inr'] > 0).sum())}/{len(per_year)}"

    out["concurrency"] = concurrency(net)
    out["capped_portfolio"] = {str(c): capped_portfolio(net, c) for c in (5, 10, 20)}
    out["random_entry"] = random_entry(p, base)

    # per-symbol spread: is the edge broad or a few names?
    bysym = net.groupby("symbol")["net_pct"].agg(["size", "mean", "sum"])
    bysym = bysym[bysym["size"] >= 10]
    out["breadth"] = {
        "symbols_with_10plus_trades": int(len(bysym)),
        "share_of_symbols_profitable": float((bysym["sum"] > 0).mean() * 100),
        "median_symbol_mean_pct": float(bysym["mean"].median() * 100),
        "top10_share_of_total_pnl_pct": float(
            bysym["sum"].nlargest(10).sum() / bysym["sum"].sum() * 100),
    }

    (OUT / "nse_equities.json").write_text(json.dumps(out, indent=2, default=str))
    net.to_csv(OUT / "trades_nse_equities.csv", index=False)
    print(json.dumps({k: v for k, v in out.items() if k != "per_year"}, indent=2, default=str))
    print("\nPER YEAR")
    print(per_year.to_string())


def export_charts() -> None:
    """Series for the NSE-equities section of the published report."""
    d = json.loads((OUT / "nse_equities.json").read_text())
    t = pd.read_csv(OUT / "trades_nse_equities.csv")

    per_year = [
        {"year": int(y), "mean_net_pct": v["mean_net_pct"], "trades": int(v["trades"]),
         "win_rate": v["win_rate"], "pnl_inr": round(v["pnl_inr"])}
        for y, v in sorted(d["per_year"].items(), key=lambda kv: int(kv[0]))
    ]
    cost = [
        {"cost_pct": float(k.replace("pct_rt", "")), "mean_net_pct": v["mean_net_pct"],
         "win_rate": v["win_rate"]}
        for k, v in d["cost_sensitivity"].items()
    ]
    # histogram of net trade returns, clipped for display
    bins = np.arange(-15, 15.5, 1.0)
    idx = np.clip(np.digitize(t["net_pct"] * 100, bins) - 1, 0, len(bins) - 2)
    hist = [{"lo": float(bins[i]), "n": int((idx == i).sum())} for i in range(len(bins) - 1)]

    payload = {
        "per_year": per_year,
        "cost_sensitivity": cost,
        "hist": hist,
        "decomposition": {
            "random_baseline": d["random_entry"]["random_mean_gross_pct"],
            "timing_edge": d["gross"]["mean_net_pct"] - d["random_entry"]["random_mean_gross_pct"],
            "gross": d["gross"]["mean_net_pct"],
            "delivery_cost": 0.323,
            "fno_cost": 0.126,
            "net_delivery": d["delivery"]["mean_net_pct"],
        },
        "capped": d["capped_portfolio"],
        "concurrency": d["concurrency"],
    }
    (OUT / "nse_charts.json").write_text(json.dumps(payload, separators=(",", ":")))
    print("wrote nse_charts.json")


if __name__ == "__main__":
    if not (OUT / "nse_equities.json").exists():
        main()
    export_charts()
