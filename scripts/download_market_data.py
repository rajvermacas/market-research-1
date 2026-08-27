#!/usr/bin/env python3
"""Download hourly / daily / weekly / monthly OHLCV for NSE-listed equities as Parquet.

The default universe is every symbol on NSE's main board (EQUITY_L.csv, series EQ/BE/BZ).
Nifty index membership is recorded as boolean flags on the universe table, so any index
subset is a Polars filter rather than a second download.

Outputs (relative to the repo root):
    data/universe/nse_universe.parquet       one row per symbol + index membership flags
    data/ohlcv/<interval>/year=YYYY/data.parquet   long format prices, partitioned by year
    data/ohlcv/_coverage_<interval>.csv      per-symbol coverage (bars, first/last timestamp)
    data/ohlcv/_manifest.json                what was downloaded, when, and known caveats

Yahoo limits: hourly reaches back only ~730 trading days. Daily, weekly and monthly reach
back to 2000. NSE Emerge (SME) symbols and BSE-exclusive listings are not served by Yahoo
and are therefore out of scope.

Usage:
    python scripts/download_market_data.py                        # all NSE, all intervals
    python scripts/download_market_data.py --interval daily weekly
    python scripts/download_market_data.py --universe nifty50     # smaller run
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import polars as pl
import requests
import yfinance as yf
import yfinance.shared as yf_shared

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
UNIVERSE_DIR = DATA_DIR / "universe"
OHLCV_DIR = DATA_DIR / "ohlcv"

NSE_EQUITY_LIST = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_INDEX_CSV = "https://nsearchives.nseindia.com/content/indices/{slug}.csv"

# Index label -> NSE archive slug, used only to tag membership on the full universe.
INDEX_FILES = {
    "nifty50": "ind_nifty50list",
    "niftynext50": "ind_niftynext50list",
    "nifty100": "ind_nifty100list",
    "nifty200": "ind_nifty200list",
    "nifty500": "ind_nifty500list",
    "niftymidcap150": "ind_niftymidcap150list",
    "niftysmallcap250": "ind_niftysmallcap250list",
}

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NSE_CLOSE = dt.time(15, 30)

# Yahoo throttles hard somewhere past ~1500 consecutive symbol requests. Keep concurrency
# low, pause between batches, and back off for minutes (not seconds) once throttled —
# hammering through a 429 just extends the block.
YF_THREADS = 2
BATCH_PAUSE_SECONDS = 0.5
RATE_LIMIT_SLEEP_SECONDS = 60
RATE_LIMIT_HINTS = ("too many requests", "rate limited", "429", "ratelimit")
# The only messages that actually mean "Yahoo does not carry this ticker". Anything else
# (empty frame, transient 5xx, dropped connection) is an unresolved failure, and must not
# be recorded as absent — a whole batch of real large caps was once lost that way.
ABSENT_HINTS = ("no timezone found", "possibly delisted", "no price data found")
CACHE_DIR = REPO_ROOT / ".cache" / "download"


def error_reason(ticker: str) -> str:
    return str(yf_shared._ERRORS.get(ticker, ""))


def confirmed_absent(ticker: str) -> bool:
    reason = error_reason(ticker).lower()
    return any(hint in reason for hint in ABSENT_HINTS)


def hit_rate_limit() -> bool:
    """Inspect yfinance's per-ticker error map; it swallows 429s into an empty frame."""
    return any(
        any(hint in str(message).lower() for hint in RATE_LIMIT_HINTS)
        for message in yf_shared._ERRORS.values()
    )


@dataclass(frozen=True)
class Interval:
    """One bar size, plus whatever Yahoo-specific constraints apply to it."""

    name: str
    yf_code: str
    intraday: bool = False
    max_lookback_days: int | None = None  # Yahoo hard limit on an explicit date range
    max_period: str | None = None  # yfinance `period=` giving the deepest history available

    @property
    def time_column(self) -> str:
        return "datetime" if self.intraday else "date"

    @property
    def has_adj_close(self) -> bool:
        # Yahoo does not dividend-adjust intraday bars: adj_close would just repeat close.
        return not self.intraday


# Ordered deliberately: daily runs first and its failures identify symbols Yahoo does not
# carry at all, which the later intervals then skip instead of re-probing.
INTERVALS = {
    iv.name: iv
    for iv in (
        Interval("daily", "1d"),
        # Yahoo rejects an explicit 1h range older than 730 *calendar* days, but honours
        # period="730d" as ~730 *trading* days (~3 calendar years) — so prefer the period
        # form whenever the request runs up to today, and fall back to the narrower
        # start/end window only when the caller pins an earlier --end.
        Interval("hourly", "1h", intraday=True, max_lookback_days=729, max_period="730d"),
        Interval("weekly", "1wk"),
        Interval("monthly", "1mo"),
    )
}

PRICE_COLUMNS = {
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "adj_close": pl.Float64,
    "volume": pl.Int64,
}

RENAMES = {
    "Date": "date",
    "Datetime": "datetime",
    "index": "datetime",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}


def make_session() -> requests.Session:
    """Yahoo and NSE both reject the default python-requests user agent."""
    session = requests.Session()
    session.headers.update({"User-Agent": BROWSER_UA, "Accept": "*/*"})
    return session


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


# --------------------------------------------------------------------------- universe


def fetch_csv(session: requests.Session, url: str, retries: int = 4) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=90)
            response.raise_for_status()
            frame = pd.read_csv(io.StringIO(response.text))
            frame.columns = [c.strip() for c in frame.columns]
            return frame
        except Exception as exc:  # network hiccup or transient NSE 5xx
            last_error = exc
            if attempt < retries - 1:
                time.sleep(2**attempt)
    raise RuntimeError(f"could not fetch {url}: {last_error}")


def build_universe(session: requests.Session) -> pl.DataFrame:
    """Every NSE main-board symbol, tagged with the Nifty indices it belongs to."""
    listed = fetch_csv(session, NSE_EQUITY_LIST)
    print(f"  NSE main board      {len(listed):>4} symbols")

    universe = pl.DataFrame(
        {
            "symbol": [str(s).strip() for s in listed["SYMBOL"]],
            "yahoo_ticker": [f"{str(s).strip()}.NS" for s in listed["SYMBOL"]],
            "company_name": [str(s).strip() for s in listed["NAME OF COMPANY"]],
            "series": [str(s).strip() for s in listed["SERIES"]],
            "isin": [str(s).strip() for s in listed["ISIN NUMBER"]],
            "listing_date": [str(s).strip() for s in listed["DATE OF LISTING"]],
            "face_value": pl.Series(listed["FACE VALUE"], dtype=pl.Float64),
        }
    ).with_columns(
        pl.col("listing_date").str.to_date("%d-%b-%Y", strict=False).alias("listing_date")
    )

    industry: dict[str, str] = {}
    flags: dict[str, set[str]] = {}
    for label, slug in INDEX_FILES.items():
        frame = fetch_csv(session, NSE_INDEX_CSV.format(slug=slug))
        print(f"  {label:<18} {len(frame):>4} constituents")
        members = {str(s).strip() for s in frame["Symbol"]}
        flags[label] = members
        for row in frame.to_dict("records"):
            industry.setdefault(str(row["Symbol"]).strip(), str(row.get("Industry", "")).strip())

    universe = universe.with_columns(
        pl.col("symbol").replace_strict(industry, default=None).alias("industry"),
        *[
            pl.col("symbol").is_in(list(members)).alias(f"in_{label}")
            for label, members in flags.items()
        ],
    )
    return universe.sort("symbol")


# ----------------------------------------------------------------------------- prices


def tidy_batch(raw: pd.DataFrame, tickers: list[str], interval: Interval) -> pd.DataFrame:
    """Turn yfinance's wide (field, ticker) frame into a long tidy frame."""
    records: list[pd.DataFrame] = []
    for ticker in tickers:
        try:
            sub = raw.xs(ticker, axis=1, level=1)
        except KeyError:
            continue
        sub = sub.dropna(how="all")
        if sub.empty:
            continue
        sub = sub.reset_index()
        sub = sub.rename(columns={c: RENAMES.get(c, c) for c in sub.columns})
        if interval.time_column not in sub.columns:  # yfinance names the index inconsistently
            sub = sub.rename(columns={sub.columns[0]: interval.time_column})
        sub["symbol"] = ticker.removesuffix(".NS")
        records.append(sub)
    if not records:
        return pd.DataFrame()
    return pd.concat(records, ignore_index=True)


def to_polars(frame: pd.DataFrame, interval: Interval) -> pl.DataFrame:
    out = pl.from_pandas(frame)
    column = interval.time_column
    if interval.intraday:
        stamp = pl.col(column).cast(pl.Datetime("us", "Asia/Kolkata"))
    else:
        # Daily/weekly/monthly bars are naive timestamps at midnight; keep them as dates.
        stamp = pl.col(column)
        if out.schema[column] != pl.Date:
            stamp = stamp.cast(pl.Datetime).dt.date()
    columns = {k: v for k, v in PRICE_COLUMNS.items() if k != "adj_close" or interval.has_adj_close}
    return out.select(
        [pl.col("symbol").cast(pl.Utf8), stamp.alias(column)]
        + [pl.col(name).cast(dtype).alias(name) for name, dtype in columns.items()]
    )


def download_batch(
    tickers: list[str],
    interval: Interval,
    request: dict,
    session: requests.Session,
    retries: int = 3,
) -> tuple[pd.DataFrame, bool]:
    """Returns (tidy frame, throttled). `throttled` means Yahoo refused, not that the
    symbols have no data — the caller must not record those as unavailable."""
    last_error: Exception | None = None
    for attempt in range(retries):
        yf_shared._ERRORS.clear()
        raw = None
        try:
            raw = yf.download(
                tickers,
                interval=interval.yf_code,
                **request,
                auto_adjust=False,
                actions=False,
                progress=False,
                threads=YF_THREADS,
                group_by="column",
                session=session,
            )
        except Exception as exc:
            last_error = exc

        if hit_rate_limit():
            wait = RATE_LIMIT_SLEEP_SECONDS * (2**attempt)
            print(f"    rate limited by Yahoo — backing off {wait}s", flush=True)
            time.sleep(wait)
            continue

        if raw is not None and not raw.empty:
            if not isinstance(raw.columns, pd.MultiIndex):  # single-ticker shape
                raw.columns = pd.MultiIndex.from_product([raw.columns, tickers])
            return tidy_batch(raw, tickers, interval), False

        last_error = last_error or RuntimeError("empty response")
        if attempt < retries - 1:
            time.sleep(2**attempt)

    if hit_rate_limit():
        return pd.DataFrame(), True
    return pd.DataFrame(), False


def download_interval(
    tickers: list[str],
    interval: Interval,
    request: dict,
    session: requests.Session,
    batch_size: int,
    fallback_request: dict | None = None,
    resume: bool = True,
) -> tuple[pl.DataFrame, list[str]]:
    """Returns the tidy panel plus the symbols Yahoo genuinely has no data for.

    Each batch is checkpointed under .cache/, so a run interrupted by throttling or a
    crash resumes instead of re-fetching thousands of symbols it already has.
    """
    cache = CACHE_DIR / interval.name
    cache.mkdir(parents=True, exist_ok=True)
    if not resume:
        for stale in cache.glob("*.parquet"):
            stale.unlink()

    frames: list[pl.DataFrame] = []
    downloaded: set[str] = set()
    throttled: list[str] = []

    def absorb(frame: pl.DataFrame) -> None:
        frames.append(frame)
        downloaded.update(frame["symbol"].unique().to_list())

    for offset in range(0, len(tickers), batch_size):
        batch = tickers[offset : offset + batch_size]
        checkpoint = cache / f"{offset:06d}.parquet"
        if checkpoint.exists():
            absorb(pl.read_parquet(checkpoint))
            continue

        tidy, limited = download_batch(batch, interval, request, session)
        if limited:
            throttled += batch
        elif not tidy.empty:
            frame = to_polars(tidy, interval)
            frame.write_parquet(checkpoint, compression="zstd")
            absorb(frame)

        done = offset + len(batch)
        if done % (batch_size * 10) == 0 or done == len(tickers):
            print(f"  [{done:>5}/{len(tickers)}] {len(downloaded)} symbols with data"
                  + (f", {len(throttled)} throttled" if throttled else ""), flush=True)
        time.sleep(BATCH_PAUSE_SECONDS)

    # Retry whatever the batch pass missed, one ticker at a time. A batch can come back
    # empty wholesale (one bad ticker poisoning the call), and for a young listing yfinance
    # expands period= into an explicit range anchored at its first trade date, which Yahoo
    # rejects for exceeding 730 calendar days — hence the narrower fallback window.
    missing = [t for t in tickers if t.removesuffix(".NS") not in downloaded]
    if missing:
        print(f"  retrying {len(missing)} symbols individually", flush=True)
        retry_cache = cache / "single"
        retry_cache.mkdir(exist_ok=True)
        still_throttled: list[str] = []
        unresolved: list[str] = []
        absent: list[str] = []
        for ticker in missing:
            checkpoint = retry_cache / f"{ticker}.parquet"
            if checkpoint.exists():
                absorb(pl.read_parquet(checkpoint))
                continue
            tidy, limited = download_batch([ticker], interval, request, session, retries=3)
            if tidy.empty and not limited and fallback_request:
                tidy, limited = download_batch(
                    [ticker], interval, fallback_request, session, retries=3
                )
            if limited:
                still_throttled.append(ticker)
            elif not tidy.empty:
                frame = to_polars(tidy, interval)
                frame.write_parquet(checkpoint, compression="zstd")
                absorb(frame)
            elif confirmed_absent(ticker):
                absent.append(ticker)
            else:
                unresolved.append(ticker)
        throttled = still_throttled
        if unresolved:
            raise RuntimeError(
                f"{len(unresolved)} symbols failed without Yahoo confirming they are absent "
                f"(e.g. {', '.join(t.removesuffix('.NS') for t in unresolved[:5])}). These are "
                f"most likely transient failures, and recording them as missing would corrupt "
                f"coverage. Checkpoints are kept in {CACHE_DIR}; re-run to retry just these."
            )

    if not frames:
        raise RuntimeError(
            f"no {interval.name} data downloaded — check network access to Yahoo Finance"
        )
    if throttled:
        raise RuntimeError(
            f"{len(throttled)} symbols still rate limited after back-off (e.g. "
            f"{', '.join(t.removesuffix('.NS') for t in throttled[:5])}). Checkpoints are "
            f"kept in {CACHE_DIR}; re-run the same command later to resume."
        )

    column = interval.time_column
    panel = (
        pl.concat(frames, how="vertical")
        .unique(subset=["symbol", column], keep="last")
        .sort(["symbol", column])
    )
    unavailable = sorted(
        t.removesuffix(".NS") for t in tickers if t.removesuffix(".NS") not in downloaded
    )
    return panel, unavailable


def trim_window(prices: pl.DataFrame, interval: Interval, start: str, end: dt.date) -> pl.DataFrame:
    """Clip to the caller's window — the period= form ignores start/end server-side."""
    column = interval.time_column
    stamp = pl.col(column).dt.date() if interval.intraday else pl.col(column)
    return prices.filter(stamp.is_between(dt.date.fromisoformat(start), end))


def write_partitioned(prices: pl.DataFrame, interval: Interval, out_dir: Path) -> float:
    """One Parquet file per calendar year, so no single file approaches GitHub's 100 MB cap."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    column = interval.time_column
    total = 0
    for (year,), part in prices.group_by(pl.col(column).dt.year(), maintain_order=True):
        target = out_dir / f"year={year}" / "data.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        part.write_parquet(target, compression="zstd", statistics=True)
        total += target.stat().st_size
    return total / 1024**2


# ---------------------------------------------------------------------------- reports


def write_coverage(
    prices: pl.DataFrame, universe: pl.DataFrame, interval: Interval, path: Path
) -> None:
    column = interval.time_column
    coverage = prices.group_by("symbol").agg(
        pl.len().alias("bars"),
        pl.col(column).min().alias("first"),
        pl.col(column).max().alias("last"),
    )
    (
        universe.select("symbol", "company_name", "series", "industry")
        .join(coverage, on="symbol", how="left")
        .with_columns(pl.col("bars").fill_null(0))
        .sort("symbol")
        .write_csv(path)
    )


def last_bar_is_partial(interval: Interval, last_stamp) -> bool:
    """True when the newest bar covers a period that has not finished yet."""
    now = now_ist()
    if interval.name in ("hourly", "daily"):
        last_date = last_stamp.date() if isinstance(last_stamp, dt.datetime) else last_stamp
        return last_date == now.date() and now.time() < NSE_CLOSE
    if interval.name == "weekly":
        return last_stamp >= now.date() - dt.timedelta(days=now.weekday())
    if interval.name == "monthly":
        return (last_stamp.year, last_stamp.month) == (now.year, now.month)
    return False


def interval_manifest(
    prices: pl.DataFrame,
    interval: Interval,
    unavailable: list[str],
    skipped: list[str],
    start: str,
    end: str,
    size_mb: float,
) -> dict:
    column = interval.time_column
    last_stamp = prices[column].max()
    partial = last_bar_is_partial(interval, last_stamp)
    entry = {
        "path": f"data/ohlcv/{interval.name}/year=*/data.parquet",
        "yfinance_interval": interval.yf_code,
        "time_column": column,
        "has_adj_close": interval.has_adj_close,
        "requested_start": start,
        "requested_end": end,
        "rows": prices.height,
        "symbols": prices["symbol"].n_unique(),
        "first": str(prices[column].min()),
        "last": str(last_stamp),
        "size_mb": round(size_mb, 1),
        "symbols_unavailable_on_yahoo": unavailable,
        "symbols_skipped_no_daily_data": skipped,
        "last_bar_possibly_partial": partial,
    }
    if interval.max_period:
        entry["yahoo_intraday_window"] = interval.max_period
    if partial:
        print(f"  WARNING: the {last_stamp} bar covers a period still in progress — it is partial.")
    return entry


GENERAL_NOTES = [
    "OHLC are split-adjusted as served by Yahoo; adj_close is additionally dividend-adjusted. "
    "Use adj_close (or its ratio to close) for total-return work.",
    "The hourly panel has no adj_close column: Yahoo does not adjust intraday bars, so the "
    "value it returns is just a copy of close and would be misleading.",
    "Yahoo serves only ~730 trading days of hourly bars, so the hourly panel cannot reach 2000.",
    "The universe is NSE's *current* main-board listing, so companies delisted before the "
    "snapshot are absent and the panel carries survivorship bias for historical backtests.",
    "NSE Emerge (SME) symbols and BSE-exclusive listings are not served by Yahoo Finance and "
    "are therefore not in this dataset.",
    "Yahoo occasionally omits a session for individual symbols; see the _coverage_*.csv files "
    "and scripts/validate_data.py for the gaps present in this snapshot.",
    "A bar flagged last_bar_possibly_partial covers a period that had not closed when the "
    "snapshot was taken — filter it out before backtesting.",
]


# ------------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--start", default="2000-01-01", help="first date, inclusive (default 2000-01-01)")
    parser.add_argument("--end", default=None, help="last date, inclusive (default: today)")
    parser.add_argument(
        "--interval",
        nargs="+",
        default=list(INTERVALS),
        choices=list(INTERVALS),
        help="bar sizes to download (default: all four)",
    )
    parser.add_argument(
        "--universe",
        default="nse_all",
        choices=["nse_all", *sorted(INDEX_FILES)],
        help="symbols to download (default nse_all: every NSE main-board listing)",
    )
    parser.add_argument("--batch-size", type=int, default=25, help="tickers per yfinance call")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="ignore .cache/ checkpoints and re-fetch everything from scratch",
    )
    args = parser.parse_args()

    end_date = dt.date.fromisoformat(args.end) if args.end else now_ist().date()
    # yfinance treats `end` as exclusive; bump it so the last session is included.
    end_exclusive = (end_date + dt.timedelta(days=1)).isoformat()

    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    OHLCV_DIR.mkdir(parents=True, exist_ok=True)
    session = make_session()

    print("Fetching NSE symbol lists")
    universe = build_universe(session)
    universe.write_parquet(UNIVERSE_DIR / "nse_universe.parquet", compression="zstd")
    universe.write_csv(UNIVERSE_DIR / "nse_universe.csv")
    print(f"  wrote data/universe/nse_universe.parquet ({len(universe)} symbols)")

    selected = universe if args.universe == "nse_all" else universe.filter(pl.col(f"in_{args.universe}"))
    tickers = selected["yahoo_ticker"].to_list()

    manifest_path = OHLCV_DIR / "_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest.update(
        {
            "generated_at_ist": now_ist().isoformat(timespec="seconds"),
            "source": "Yahoo Finance via yfinance; symbol lists from NSE public archives",
            "universe": args.universe,
            "universe_size": len(selected),
            "notes": GENERAL_NOTES,
        }
    )
    manifest.setdefault("intervals", {})

    # Symbols Yahoo has no daily history for do not exist there at any interval either.
    dead: list[str] = []
    ordered = [n for n in INTERVALS if n in args.interval]

    for name in ordered:
        interval = INTERVALS[name]
        start = args.start
        request = {"start": start, "end": end_exclusive}
        fallback_request = None

        if interval.max_period and end_date >= now_ist().date():
            request = {"period": interval.max_period}
            narrow_start = end_date - dt.timedelta(days=interval.max_lookback_days or 729)
            fallback_request = {"start": narrow_start.isoformat(), "end": end_exclusive}
            print(f"\n  ({name}: Yahoo limits intraday history — requesting "
                  f"period={interval.max_period}, the deepest window it serves)")
        elif interval.max_lookback_days:
            floor = end_date - dt.timedelta(days=interval.max_lookback_days)
            if dt.date.fromisoformat(start) < floor:
                start = floor.isoformat()
                request["start"] = start
                print(f"\n  ({name}: Yahoo serves only {interval.max_lookback_days} days "
                      f"for a pinned end date, starting from {start})")

        live = [t for t in tickers if t.removesuffix(".NS") not in set(dead)]
        print(f"\nDownloading {len(live)} symbols, {name} bars, "
              f"{request.get('start', interval.max_period)} -> {end_date}")
        prices, unavailable = download_interval(
            live, interval, request, session, args.batch_size, fallback_request,
            resume=not args.fresh,
        )
        prices = trim_window(prices, interval, args.start, end_date)

        if name == "daily":
            dead = unavailable
            if dead:
                print(f"  {len(dead)} symbols have no history on Yahoo; skipping them for "
                      "the remaining intervals")

        size_mb = write_partitioned(prices, interval, OHLCV_DIR / name)
        write_coverage(prices, selected, interval, OHLCV_DIR / f"_coverage_{name}.csv")
        manifest["intervals"][name] = interval_manifest(
            prices, interval, unavailable, list(dead) if name != "daily" else [],
            args.start, end_date.isoformat(), size_mb,
        )

        column = interval.time_column
        print(
            f"  wrote data/ohlcv/{name}/: {prices.height:,} rows, "
            f"{prices['symbol'].n_unique()} symbols, {prices[column].min()} -> "
            f"{prices[column].max()}, {size_mb:.1f} MB"
        )

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\nWrote {manifest_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
