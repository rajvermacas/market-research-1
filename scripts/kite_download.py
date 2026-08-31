#!/usr/bin/env python3
"""Download deep intraday OHLCV for NSE equities from Kite Connect.

Yahoo serves only ~730 trading days of hourly bars, so every backtest built on the
committed panel covers a single rising market. Kite carries intraday history back to
roughly 2015, which spans the 2015-16 correction, the 2018 midcap collapse, the 2020
crash and the 2022 selloff — the regimes a momentum strategy actually needs to be tested
against. This fetches that history into the same long-format, year-partitioned Parquet
layout as the Yahoo panels, so the existing screeners and backtests read it unchanged.

Credentials come from the environment ONLY — never a CLI argument (those land in shell
history and in `ps` output) and never a file inside the repo:

    export KITE_API_KEY=...
    export KITE_API_SECRET=...

    python scripts/kite_download.py --login              # open the URL it prints
    echo "<request_token>" | python scripts/kite_download.py --exchange

The access token expires every day and refreshing it needs an interactive login, so this
is a run-when-you-mean-to script rather than something to put on a schedule.

Kite's per-request window is 400 days for 60minute and 200 days for 30minute, so history
is fetched in chunks and stitched. Every symbol is checkpointed under .cache/, because a
full run takes hours and will get interrupted.

Usage:
    python scripts/kite_download.py --probe                 # 5 symbols, compare vs Yahoo
    python scripts/kite_download.py --interval 60minute     # full NSE, ~2.6 hours
    python scripts/kite_download.py --interval 30minute --start 2015-01-01
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import os
import sys
import time
from pathlib import Path

import pandas as pd
import polars as pl
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
OHLCV_DIR = REPO_ROOT / "data" / "ohlcv"
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CACHE_DIR = REPO_ROOT / ".cache" / "kite"

API = "https://api.kite.trade"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# Kite's documented per-request window, by interval. Exceeding it is rejected outright.
WINDOW_DAYS = {"minute": 60, "3minute": 100, "5minute": 100, "10minute": 100,
               "15minute": 200, "30minute": 200, "60minute": 400, "day": 2000}
# Kite's historical endpoint is rate limited; 3/sec is the documented ceiling, and the
# script paces itself under it rather than discovering the limit by being blocked.
REQUESTS_PER_SECOND = 3.0


# The access token lives outside the repository, mode 0600. It expires daily, so this is
# a cache rather than a stored secret — but it is still never written inside a git tree.
TOKEN_FILE = Path.home() / ".kite" / "access_token"


def login_url() -> str:
    key = os.environ.get("KITE_API_KEY")
    if not key:
        sys.exit("Set KITE_API_KEY in the environment.")
    return f"https://kite.zerodha.com/connect/login?v=3&api_key={key}"


def exchange_request_token() -> None:
    """Trade a one-time request_token for a daily access_token.

    The request token is read from stdin, never from argv: an argument would be visible
    in `ps` and recorded in shell history. checksum = SHA-256(api_key + request_token +
    api_secret), per Kite's login flow.
    """
    key, secret = os.environ.get("KITE_API_KEY"), os.environ.get("KITE_API_SECRET")
    if not key or not secret:
        sys.exit("Set KITE_API_KEY and KITE_API_SECRET in the environment.")
    request_token = sys.stdin.read().strip()
    if not request_token:
        sys.exit("No request_token on stdin.")
    checksum = hashlib.sha256(f"{key}{request_token}{secret}".encode()).hexdigest()
    response = requests.post(f"{API}/session/token", headers={"X-Kite-Version": "3"},
                             data={"api_key": key, "request_token": request_token,
                                   "checksum": checksum}, timeout=60)
    if response.status_code != 200:
        sys.exit(f"Exchange failed ({response.status_code}): {response.text[:300]}\n"
                 f"A request_token is single-use and expires within minutes — if it was "
                 f"already spent, log in again for a fresh one.")
    data = response.json()["data"]
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(data["access_token"])
    TOKEN_FILE.chmod(0o600)
    print(f"access token stored in {TOKEN_FILE} (mode 0600), valid until tomorrow's "
          f"pre-open")
    print(f"  logged in as {data.get('user_name', '?')} ({data.get('user_id', '?')})")


def credentials() -> tuple[str, str]:
    key = os.environ.get("KITE_API_KEY")
    token = os.environ.get("KITE_ACCESS_TOKEN")
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
    if not key or not token:
        sys.exit("Set KITE_API_KEY, then run --login and --exchange to mint an access "
                 "token.\nNever pass credentials as arguments — they would be visible "
                 "in `ps` and in your shell history.")
    return key, token


def make_session(key: str, token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"X-Kite-Version": "3",
                      "Authorization": f"token {key}:{token}"})
    return s


def get(session: requests.Session, path: str, params: dict | None = None,
        retries: int = 6) -> requests.Response:
    """One paced request, with a real back-off on 429 and 5xx."""
    for attempt in range(retries):
        try:
            response = session.get(f"{API}{path}", params=params, timeout=60)
        except requests.RequestException as exc:
            # A dropped connection or proxy hiccup is transient, and over a run of 25,000
            # requests it is a certainty rather than a risk. Retrying it is the difference
            # between resuming and losing hours.
            wait = 2 ** attempt
            print(f"    network error ({type(exc).__name__}) — retrying in {wait}s",
                  flush=True)
            time.sleep(wait)
            continue
        if response.status_code == 200:
            return response
        if response.status_code in (401, 403):
            sys.exit(f"Kite rejected the credentials ({response.status_code}). The access "
                     f"token expires daily — generate a fresh one.\n{response.text[:200]}")
        if response.status_code == 429 or response.status_code >= 500:
            wait = 2 ** attempt
            print(f"    {response.status_code} — backing off {wait}s", flush=True)
            time.sleep(wait)
            continue
        response.raise_for_status()
    raise RuntimeError(f"{path} failed after {retries} attempts")


def instrument_tokens(session: requests.Session) -> dict[str, int]:
    """symbol -> instrument_token for NSE equities, from Kite's instruments dump."""
    text = get(session, "/instruments/NSE").text
    frame = pd.read_csv(io.StringIO(text))
    equities = frame[frame["instrument_type"] == "EQ"]
    return {str(r["tradingsymbol"]).strip(): int(r["instrument_token"])
            for _, r in equities.iterrows()}


def fetch_symbol(session: requests.Session, token: int, interval: str,
                 start: dt.date, end: dt.date) -> pl.DataFrame:
    """Walk the window forward in chunks Kite will accept, and stitch the candles."""
    span = WINDOW_DAYS[interval]
    rows: list[list] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + dt.timedelta(days=span - 1), end)
        response = get(session, f"/instruments/historical/{token}/{interval}",
                       {"from": f"{cursor} 09:00:00", "to": f"{chunk_end} 16:00:00"})
        rows += response.json()["data"]["candles"]
        time.sleep(1.0 / REQUESTS_PER_SECOND)
        cursor = chunk_end + dt.timedelta(days=1)
    if not rows:
        return pl.DataFrame()
    # Explicit dtypes, and volume as Float64 first: Kite occasionally returns 2**63 as a
    # volume, which is one past Int64's ceiling and aborts inference outright.
    frame = pl.DataFrame(
        rows,
        schema={"datetime": pl.Utf8, "open": pl.Float64, "high": pl.Float64,
                "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64},
        orient="row",
    )
    impossible = frame.filter(pl.col("volume") >= 2.0 ** 62).height
    if impossible:
        # Nulled rather than kept or silently zeroed, and counted so the run says so.
        print(f"      {impossible} bars carry an impossible volume (>= 2^62) — nulled",
              flush=True)
        frame = frame.with_columns(
            pl.when(pl.col("volume") >= 2.0 ** 62).then(None)
              .otherwise(pl.col("volume")).alias("volume"))
    return frame.with_columns(
        # Kite stamps candles like 2017-12-15T09:15:00+0530 — an explicit format is
        # required, since Polars refuses to infer one when an offset is present.
        pl.col("datetime")
          .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%z")
          .dt.convert_time_zone("Asia/Kolkata"),
        *[pl.col(c).cast(pl.Float64) for c in ("open", "high", "low", "close")],
        pl.col("volume").cast(pl.Int64, strict=False),
    ).unique(subset=["datetime"], keep="last").sort("datetime")


def compare_with_yahoo(panel: pl.DataFrame, symbols: list[str]) -> None:
    """Kite is exchange data; Yahoo is adjusted. A large gap means unadjusted history."""
    yahoo_glob = str(OHLCV_DIR / "hourly" / "**" / "*.parquet")
    if not list((OHLCV_DIR / "hourly").glob("year=*/*.parquet")):
        print("  (no Yahoo hourly panel to compare against)")
        return
    yahoo = (pl.scan_parquet(yahoo_glob, hive_partitioning=True)
             .filter(pl.col("symbol").is_in(symbols))
             .select("symbol", "datetime", pl.col("close").alias("yahoo_close")).collect())
    joined = panel.join(yahoo, on=["symbol", "datetime"], how="inner")
    if joined.is_empty():
        print("  no overlapping bars to compare — check bar alignment")
        return
    joined = joined.with_columns(
        ((pl.col("close") - pl.col("yahoo_close")).abs() / pl.col("yahoo_close")).alias("gap"))
    print(f"\n  overlap with the Yahoo panel: {joined.height:,} bars")
    print(f"    median relative gap {float(joined['gap'].median()):.5f}")
    print(f"    bars differing by >1%: {joined.filter(pl.col('gap') > 0.01).height:,} "
          f"({joined.filter(pl.col('gap') > 0.01).height / joined.height:.2%})")
    for row in (joined.group_by("symbol").agg(pl.col("gap").median().alias("median_gap"))
                .sort("median_gap", descending=True).head(5).iter_rows(named=True)):
        print(f"      {row['symbol']:<12} median gap {row['median_gap']:.5f}")
    print("    A gap that grows going back in time means Kite's candles are NOT "
          "split-adjusted — corporate actions would have to be applied before use.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--interval", default="60minute", choices=sorted(WINDOW_DAYS))
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--universe", default="nse_all")
    parser.add_argument("--probe", action="store_true",
                        help="fetch 5 liquid symbols only and compare against the Yahoo "
                             "panel — run this before committing hours to a full pull")
    parser.add_argument("--fresh", action="store_true", help="ignore .cache checkpoints")
    parser.add_argument("--login", action="store_true",
                        help="print the Kite login URL and exit")
    parser.add_argument("--exchange", action="store_true",
                        help="read a request_token from STDIN and store the access token")
    args = parser.parse_args()

    if args.login:
        print(login_url())
        return 0
    if args.exchange:
        exchange_request_token()
        return 0

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end) if args.end else dt.datetime.now(IST).date()
    session = make_session(*credentials())

    print("Fetching Kite instrument tokens")
    tokens = instrument_tokens(session)
    print(f"  {len(tokens)} NSE equity instruments")

    universe = pl.read_parquet(UNIVERSE)
    if args.universe != "nse_all":
        universe = universe.filter(pl.col(f"in_{args.universe}"))
    symbols = [s for s in universe["symbol"].to_list() if s in tokens]
    missing = len(universe) - len(symbols)
    if args.probe:
        symbols = [s for s in ("RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC") if s in tokens]
    print(f"  {len(symbols)} of {len(universe)} universe symbols matched"
          + (f" ({missing} absent from Kite — delisted or renamed)" if missing else ""))

    cache = CACHE_DIR / args.interval
    cache.mkdir(parents=True, exist_ok=True)
    if args.fresh:
        for stale in cache.glob("*.parquet"):
            stale.unlink()

    chunks = (end - start).days // WINDOW_DAYS[args.interval] + 1
    print(f"\nDownloading {len(symbols)} symbols, {args.interval}, {start} -> {end}")
    print(f"  ~{chunks} requests each, ~{len(symbols) * chunks:,} total, "
          f"~{len(symbols) * chunks / REQUESTS_PER_SECOND / 3600:.1f} hours at "
          f"{REQUESTS_PER_SECOND:g}/sec")

    # Checkpoints are the only store. An earlier version also accumulated every symbol in
    # memory, which reaches about 4 GB across 2,300 names and got the process OOM-killed
    # twice with no traceback. The panel is assembled by re-reading the checkpoints at the
    # end, which costs seconds and bounds memory to one symbol at a time.
    unavailable: list[str] = []
    done = 0
    for i, symbol in enumerate(symbols, 1):
        checkpoint = cache / f"{symbol}.parquet"
        if checkpoint.exists():
            done += 1
            continue
        try:
            frame = fetch_symbol(session, tokens[symbol], args.interval, start, end)
        except Exception as exc:
            # Fail loudly rather than recording a transient failure as absent history.
            raise RuntimeError(
                f"{symbol} failed: {exc}. Checkpoints are kept in {cache}; re-run to "
                f"resume from here."
            ) from exc
        if frame.is_empty():
            unavailable.append(symbol)
            continue
        frame = frame.with_columns(pl.lit(symbol).alias("symbol"))
        frame.write_parquet(checkpoint, compression="zstd")
        done += 1
        if i % 25 == 0 or i == len(symbols):
            print(f"  [{i:>5}/{len(symbols)}] {done} symbols with data", flush=True)

    have = [cache / f"{s}.parquet" for s in symbols if (cache / f"{s}.parquet").exists()]
    if not have:
        return 1
    print(f"  assembling {len(have)} checkpoints")
    panel = (pl.concat([pl.read_parquet(f) for f in have], how="vertical_relaxed")
             .select("symbol", "datetime", "open", "high", "low", "close", "volume")
             .unique(subset=["symbol", "datetime"], keep="last")
             .sort(["symbol", "datetime"]))
    print(f"\n{panel.height:,} rows, {panel['symbol'].n_unique()} symbols, "
          f"{panel['datetime'].min()} -> {panel['datetime'].max()}")
    if unavailable:
        print(f"  {len(unavailable)} symbols returned no candles: "
              f"{', '.join(unavailable[:8])}")

    if args.probe:
        compare_with_yahoo(panel, symbols)
        print("\nProbe only — nothing written. Re-run without --probe for the full pull.")
        return 0

    # A separate directory: the Yahoo panel stays authoritative until this one is validated.
    out_dir = OHLCV_DIR / f"{args.interval}_kite"
    total = 0
    for (year,), part in panel.group_by(pl.col("datetime").dt.year(), maintain_order=True):
        target = out_dir / f"year={year}" / "data.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        part.write_parquet(target, compression="zstd", statistics=True)
        total += target.stat().st_size
    print(f"\nWrote {out_dir.relative_to(REPO_ROOT)}/ — {total / 1024**2:.1f} MB")
    print("The Yahoo panel is untouched. Validate this one before switching over.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
