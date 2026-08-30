"""Download daily history for NSE equities from the Yahoo chart API.

Yahoo lists NSE stocks as SYMBOL.NS. Prices are split/bonus adjusted on the
adjclose line, which is what a backtest has to use - Indian corporate actions
are frequent enough that raw close would manufacture fake gaps.
"""

import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NSE = DATA / "nse"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36")

_lock = threading.Lock()
_done = {"n": 0, "ok": 0, "fail": 0}


def fetch_one(symbol: str, retries: int = 5) -> pd.DataFrame | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
    params = {"period1": 0, "period2": int(time.time()), "interval": "1d", "events": "div,split"}
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=45)
            if r.status_code in (429, 502, 503):
                time.sleep(2 + 3 * attempt)
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose")
            df = pd.DataFrame({
                "date": pd.to_datetime(res["timestamp"], unit="s", utc=True)
                          .tz_convert("Asia/Kolkata").normalize().tz_localize(None),
                "open": q["open"], "high": q["high"], "low": q["low"],
                "close": q["close"], "volume": q.get("volume"),
                "adjclose": adj if adj is not None else q["close"],
            })
            df = df.dropna(subset=["close", "adjclose"]).drop_duplicates(subset="date", keep="last")
            return df.sort_values("date").reset_index(drop=True)
        except Exception:
            time.sleep(1.5 + 2 * attempt)
    return None


def worker(symbol: str) -> None:
    out = NSE / f"{symbol}.csv"
    if out.exists() and out.stat().st_size > 2000:
        with _lock:
            _done["n"] += 1; _done["ok"] += 1
        return
    df = fetch_one(symbol)
    with _lock:
        _done["n"] += 1
        if df is not None and len(df) > 250:
            # split/bonus adjusted OHLC: scale the bar by adjclose/close
            f = df["adjclose"] / df["close"]
            for c in ("open", "high", "low"):
                df[c] = df[c] * f
            df["close"] = df["adjclose"]
            df[["date", "open", "high", "low", "close", "volume"]].to_csv(out, index=False)
            _done["ok"] += 1
        else:
            _done["fail"] += 1
        if _done["n"] % 25 == 0:
            print(f"  {_done['n']} done  ok={_done['ok']} fail={_done['fail']}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="nifty500", choices=["nifty500", "all"])
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    NSE.mkdir(parents=True, exist_ok=True)
    if args.universe == "nifty500":
        syms = pd.read_csv(DATA / "nifty500.csv")["Symbol"].astype(str).str.strip().tolist()
    else:
        eq = pd.read_csv(DATA / "equity_l.csv")
        eq.columns = [c.strip() for c in eq.columns]
        syms = eq[eq["SERIES"].str.strip() == "EQ"]["SYMBOL"].astype(str).str.strip().tolist()

    print(f"{len(syms)} symbols, {args.workers} workers", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(worker, syms))
    print(f"DONE ok={_done['ok']} fail={_done['fail']}", flush=True)


if __name__ == "__main__":
    main()
