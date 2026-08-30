# market-research-1

Daily OHLCV price history for **every NSE-listed Indian equity**, 2000 to date, stored as
year-partitioned Parquet and meant to be read with [Polars](https://pola.rs) for strategy research
and backtesting.

## What is in here

| Path | Contents |
| --- | --- |
| `data/ohlcv/daily/year=*/data.parquet` | The price panel — `symbol, date, open, high, low, close, adj_close, volume` (+ `year` from the partition path) |
| `data/ohlcv/hourly/year=*/data.parquet` | Hourly bars — `symbol, datetime` (Asia/Kolkata)`, open, high, low, close, volume`; no `adj_close` |
| `data/ohlcv/_coverage_*.csv` | Per-symbol bar count and first/last timestamp, per interval |
| `data/ohlcv/_manifest.json` | Snapshot provenance, stats and caveats — the source of truth |
| `data/universe/nse_universe.parquet` | Every NSE main-board symbol: company, series, ISIN, listing date, face value, industry + Nifty index membership flags |
| `data/universe/nse_universe.csv` | Same, as CSV for quick eyeballing |
| `scripts/download_market_data.py` | Rebuilds everything above from NSE + Yahoo Finance |
| `scripts/validate_data.py` | Structural and data-quality checks |
| `scripts/hourly_rsi_screener.py` | Hourly RSI re-ignition screen under a daily/weekly/monthly trend filter |

### The data present

Numbers below describe the committed snapshot; `data/ohlcv/_manifest.json` is regenerated on every
refresh and always reflects what is actually on disk.

| | |
| --- | --- |
| Interval | Daily (`1d`) |
| Rows | 7,465,347 |
| Symbols with data | 2,559 of 2,559 — the entire NSE main board |
| Date range | 2000-01-03 → 2026-08-27 |
| Trading sessions | 6,657 |
| On disk | 131 MB across 27 yearly Parquet files (largest 9.6 MB) |
| Compression | zstd |

And the hourly panel, which reaches back only as far as Yahoo serves intraday bars:

| | |
| --- | --- |
| Interval | Hourly (`1h`) |
| Rows | 9,901,435 |
| Symbols with data | 2,559 of 2,559 |
| Range | 2023-09-18 09:15 → 2026-08-28 15:15 IST (5,068 hourly bars) |
| Bars per symbol | median 5,003 |
| On disk | 132 MB across 4 yearly Parquet files (largest 47 MB) |
| Columns | `symbol, datetime, open, high, low, close, volume` — **no `adj_close`** |

Two differences from the daily panel matter when you use it. There is no `adj_close`, because
Yahoo does not dividend-adjust intraday bars — the value it returns is a verbatim copy of `close`,
so shipping it would invite silently wrong total-return math. And 13.4% of hourly bars have zero
volume (against 4.0% daily), which is what a thinly traded name looks like inside the session
rather than a data fault.

History per symbol is very uneven — this is a full-market panel, not an index panel:

| Percentile | Bars available |
| --- | --- |
| 5th | 7 |
| 25th | 682 |
| 50th | 2,389 |
| 75th | 5,108 |
| 95th | 6,003 |

403 symbols have under a year of history, and only 81 reach all the way back to
January 2000. **Filter on bar count before any cross-sectional ranking** or recent listings will
distort the results.

#### The early years are thin — read this before backtesting pre-2005

The date range says 2000, but coverage in the early years is a small fraction of the market that
actually traded. Measured against NSE's own daily bhavcopy (the official end-of-day record of every
symbol that traded):

| Date | Symbols that traded on NSE | In this panel | Coverage |
| --- | --- | --- | --- |
| 2000-06-12 | 917 | 86 | **9%** |
| 2004-06-10 | 752 | 570 | 76% |
| 2008-06-10 | 1,225 | 898 | 73% |
| 2012-06-11 | 1,514 | 1,089 | 72% |
| 2016-06-10 | 1,532 | 1,226 | 80% |
| 2020-06-10 | 1,683 | 1,577 | 94% |
| 2024-06-10 | 2,208 | 1,975 | 89% |

Two effects stack. Delisted and merged companies are absent entirely (survivorship bias), and
Yahoo's Indian history is shallow even for companies that still trade — ABB, ACC and AARTIIND are
all currently listed and still have no year-2000 data there.

Practical reading: treat this panel as solid from roughly 2015, usable with care 2005–2015, and
**not representative of the market before about 2004**. A cross-sectional backtest run on 2000-2003
is ranking 9% of the universe, pre-selected for having survived to 2026.

Curing this requires a different source — NSE bhavcopy, stacked per trading day, which records the
universe as it was on each date. See `AGENTS.md` for the approach.

Every Nifty index constituent is present: Nifty 50 50/50, Next 50 50/50, Nifty 100 100/100,
Nifty 200 200/200, Nifty 500 500/500, Midcap 150 150/150, Smallcap 250 250/250.

### Daily and hourly are committed; weekly and monthly are not

Hourly is in git despite its size, because it is the one panel that cannot be reconstructed later:
Yahoo serves only a rolling window of intraday bars, so history that scrolls off the end is simply
gone unless a snapshot was taken. Weekly and monthly stay out — they are a one-line resample of
daily, so committing them would buy nothing but repository size:

```bash
python scripts/download_market_data.py --interval weekly monthly   # if you really want the files
```

Weekly and monthly do not need a download at all — resample the daily panel:

```python
weekly = (
    daily.sort("date")
    .group_by_dynamic("date", every="1w", group_by="symbol")
    .agg(
        pl.col("open").first(), pl.col("high").max(), pl.col("low").min(),
        pl.col("close").last(), pl.col("adj_close").last(), pl.col("volume").sum(),
    )
)
```

Hourly cannot be derived from daily at all — an hourly bar is not recoverable from a daily one —
which is exactly why it is committed rather than left to be re-downloaded.

## Universe

`data/universe/nse_universe.parquet` is NSE's full main-board equity list (series `EQ` 2,288,
`BE` 243, `BZ` 28). Nifty index membership is carried as boolean columns, so narrowing to an index
is a filter rather than another download:

```python
nifty50 = universe.filter(pl.col("in_nifty50"))   # also in_niftynext50, in_nifty100, in_nifty200,
                                                   # in_nifty500, in_niftymidcap150,
                                                   # in_niftysmallcap250
```

Not included, because Yahoo Finance does not serve them: **NSE Emerge (SME)** symbols and
**BSE-exclusive** listings.

## Quickstart

```python
import polars as pl

daily = pl.scan_parquet("data/ohlcv/daily/**/*.parquet", hive_partitioning=True)
universe = pl.scan_parquet("data/universe/nse_universe.parquet")

# Nifty 50 members only, last 5 years
nifty50 = (
    daily.join(universe.filter(pl.col("in_nifty50")).select("symbol"), on="symbol")
    .filter(pl.col("date") >= pl.date(2021, 1, 1))
    .collect()
)

# 20/50-day moving-average crossover signal per symbol
signals = (
    daily.sort("symbol", "date")
    .with_columns(
        pl.col("adj_close").rolling_mean(20).over("symbol").alias("ma20"),
        pl.col("adj_close").rolling_mean(50).over("symbol").alias("ma50"),
    )
    .with_columns((pl.col("ma20") > pl.col("ma50")).alias("long"))
    .collect()
)

# Tradeable subset: enough history and real liquidity
liquid = (
    daily.filter(pl.col("date") >= pl.date(2024, 1, 1))
    .group_by("symbol")
    .agg(
        pl.len().alias("bars"),
        (pl.col("close") * pl.col("volume")).median().alias("median_turnover"),
    )
    .filter((pl.col("bars") > 400) & (pl.col("median_turnover") > 1e7))
    .collect()
)

# The `year` column comes from the partition path — filtering on it skips whole files
recent = daily.filter(pl.col("year") >= 2024).collect()
```

## Screener

`scripts/screener.py` implements a **pullback-in-uptrend** screen: higher timeframes strongly
trending, daily RSI dipped, daily RSI just turning back up — so the entry lands as strength
resumes rather than after the move has run.

```bash
python scripts/screener.py                      # full NSE universe
python scripts/screener.py --universe nifty500
python scripts/screener.py --pullback-max 50 --rising-bars 1   # looser
python scripts/screener.py --mode trend         # plain "daily+weekly+monthly RSI > 60"
```

Default conditions, each a flag:

| Stage | Condition |
| --- | --- |
| Structure | monthly RSI(14) > 60, weekly RSI(14) > 60, close above 200-day SMA |
| Pullback | daily RSI dipped to <= 45 within the last 15 bars |
| Turn | daily RSI rising 2 consecutive bars, >= 3 points off its trough, trough <= 7 bars ago |
| Not late | daily RSI still below 65 |
| Tradable | market cap > 5,000 crore, 20-day average turnover > 5 crore |

`--mode trend` is the opposite selection — it finds names already extended, which is what a
"daily RSI > 60" condition gives you.

RSI is Wilder's, validated to machine precision (< 1e-9) against a reference implementation on
daily, weekly and monthly. Weekly and monthly are resampled from the daily panel. Market caps are
fetched live from Yahoo, since the repository stores prices but not fundamentals; results are
written to `.cache/screener/` (gitignored).

**The last daily bar matters here.** If the snapshot was captured mid-session, the "RSI rising"
test is reading an incomplete bar and can flip by the close. The screener prints a warning when
`_manifest.json` flags the final bar as partial — refresh the daily panel after 15:30 IST for a
settled read.

## EMA support analysis

`scripts/ema_support.py` answers a different kind of question from the screener: not "what
qualifies today" but "which momentum names *historically* bounce off their daily 20/50 EMA".

```bash
python scripts/ema_support.py                     # monthly RSI > 60 universe, 3-year window
python scripts/ema_support.py --years 5 --min-touches 12
python scripts/ema_support.py --horizon 20 --break-tol 0.03
```

A touch is counted when the previous close sat comfortably above the EMA (`--separation`,
default 1.5%) and the bar's low came down to it (`--touch-tol`, 0.5%) — requiring the prior bar to
be clearly above is what stops a week of chopping along the average counting as five touches. It
held if no close over the next `--horizon` bars fell more than `--break-tol` below the EMA and the
close at the horizon is back above it.

Two numbers matter, and the second is the honest one:

- **hold rate** — share of touches that held. Cohort median is ~37% on the 20 EMA and ~41% on the
  50 EMA, so read a name against that, not against 50%. The tool ranks rather than gates for this
  reason (`--min-hold` defaults to 0).
- **edge** — median return after a touch minus the same stock's median return from a random bar in
  the window. A stock in a relentless uptrend posts a high hold rate because *any* entry worked.
  Positive edge is what says the average itself carried information.

## N-pattern screener

`scripts/n_pattern.py` finds the three-leg continuation shape — impulse up, partial pullback that
leans on a rising 10 EMA, then resumption — by decomposing the recent swings:

```
      B          D        A  swing low the impulse starts from
     /\         /         B  impulse high
    /  \       /          C  pullback low: a HIGHER low than A, resting on the 10 EMA
   /    \     /           D  today, turning back up off C
  A      C___/
```

```bash
python scripts/n_pattern.py                            # full NSE universe
python scripts/n_pattern.py --universe nifty500 --charts 9
python scripts/n_pattern.py --min-impulse 0.10 --max-retrace 0.5
```

B is the highest high in the last `--window` bars, A the lowest low before it, C the lowest low
after it. Conditions then cover the geometry: impulse size, retracement depth, `C > A`, C touching
the 10 EMA without closing far below it, how recently C formed, how far price has resumed, and the
EMA rising with price above it.

**Leg duration matters as much as leg size.** Without `--max-leg1-bars` and `--min-pullback-bars`,
a stock in one long uninterrupted trend matches: A pins to the left edge of the window, the
"impulse" measures the entire run, and the "pullback" is a one-day wick near the highs. Those
constraints are what keep the pattern local and shaped like an N.

`--charts N` renders the top hits as candlesticks with the EMA and the A/B/C levels marked. Use it
— geometric conditions are easy to satisfy in ways that look nothing like the intended shape, and
the picture is the only quick way to catch that.

## Refreshing the data

```bash
pip install -r requirements.txt

python scripts/download_market_data.py --interval daily       # rebuild the committed panel
python scripts/download_market_data.py --universe nifty50     # smaller run
python scripts/download_market_data.py --start 2015-01-01 --end 2025-12-31

python scripts/validate_data.py                               # verify the result
```

The universe is re-fetched from NSE's public archives on every run, so a refresh also picks up new
listings and index reshuffles. Each batch is checkpointed under `.cache/` (gitignored): an
interrupted run resumes rather than re-fetching thousands of symbols. Pass `--fresh` to ignore
checkpoints.

Yahoo throttles somewhere past ~1,500 consecutive symbol requests, so a full run is paced and takes
roughly 20–30 minutes. The downloader detects throttling explicitly and **aborts with a resume hint
rather than writing a panel with silent holes**.

## Data caveats

Worth reading before trusting a backtest:

1. **Survivorship bias.** The universe is NSE's *current* main-board listing. Companies delisted
   before the snapshot are absent entirely, which flatters long-only backtests.
2. **Uneven history.** Median symbol has ~2,400 bars, not 6,600. See the percentile table above.
3. **Adjustments.** `open/high/low/close` are split-adjusted as served by Yahoo; `adj_close` is
   additionally dividend-adjusted. Use `adj_close` for return series, raw `close` for price levels.
4. **Partial last bar.** If a snapshot is taken while the NSE session is open, the newest bar is
   incomplete. `last_bar_possibly_partial` in `_manifest.json` flags it — filter that date out
   before backtesting. It is set in the current snapshot (2026-08-27).
5. **Upstream gaps.** Yahoo occasionally drops a session for individual symbols — 2026-08-26 is
   missing for a large share of the universe. `scripts/validate_data.py` reports affected dates.
6. **Bad ticks.** 1,852 bars of 7.47M (0.025%, across 290 symbols) violate OHLC ordering upstream,
   mostly illiquid names on zero volume. Documented rather than silently patched.
7. **Zero-volume bars.** 4.0% of bars (300,926) have zero volume — thin names with no trades that session.
   Screen them out for anything execution-sensitive.
8. **Symbol availability.** In this snapshot every NSE main-board symbol resolved on Yahoo
   (`symbols_unavailable_on_yahoo` is empty). The downloader records a symbol as absent only when
   Yahoo explicitly says so, never on a transient failure — an earlier run mislabelled a whole
   failed batch of large caps as "no history", and that class of bug now fails loudly instead.

Data source: Yahoo Finance via `yfinance`; symbol lists from NSE's public archives. For personal
research use — check the respective terms before redistributing.

## Agent instructions

See [AGENTS.md](AGENTS.md).
