"""Download daily OHLC history for the backtest from the Yahoo Finance chart API.

yfinance's curl_cffi transport does not survive this environment's TLS-terminating
proxy, so we talk to the public chart endpoint directly with requests.
"""

import argparse
import time
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)

# Yahoo symbol -> local file stem
SYMBOLS = {
    "ES=F": "ES",
    "NQ=F": "NQ",
    "^GSPC": "SPX",
    "^NDX": "NDX",
}


def fetch(symbol: str, retries: int = 6) -> pd.DataFrame:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(symbol)}"
    params = {"period1": 0, "period2": int(time.time()), "interval": "1d", "events": "div,split"}
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=60)
            if r.status_code == 429:
                raise RuntimeError("429 rate limited")
            r.raise_for_status()
            payload = r.json()["chart"]["result"][0]
            break
        except Exception as exc:  # noqa: BLE001 - retry any transport/rate-limit error
            last_err = exc
            time.sleep(2 ** attempt)
    else:
        raise RuntimeError(f"failed to fetch {symbol}: {last_err}")

    quote = payload["indicators"]["quote"][0]
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(payload["timestamp"], unit="s", utc=True).tz_convert(
                payload["meta"]["exchangeTimezoneName"]
            ).normalize().tz_localize(None),
            "open": quote["open"],
            "high": quote["high"],
            "low": quote["low"],
            "close": quote["close"],
            "volume": quote.get("volume"),
        }
    )
    df = df.dropna(subset=["close"]).drop_duplicates(subset="date", keep="last")
    return df.sort_values("date").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="*", default=list(SYMBOLS))
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    for symbol in args.symbols:
        df = fetch(symbol)
        out = DATA_DIR / f"{SYMBOLS[symbol]}.csv"
        df.to_csv(out, index=False)
        print(f"{symbol:6s} -> {out.name:8s} {len(df):6d} rows  {df.date.iloc[0].date()} .. {df.date.iloc[-1].date()}")
        time.sleep(1)


if __name__ == "__main__":
    main()
