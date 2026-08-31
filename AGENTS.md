# AGENTS.md

Guidance for AI agents (and humans) working in this repository.

## Working agreement

Whenever I point out or you catch yourself repeating same mistakes again, before continuing add it as a rule in #LESSONS below to avoid it in future

## Project

Market research and systematic trading work on the Indian equity market (NSE).

- **Data**: daily OHLCV for every NSE main-board listing, 2000 to date, plus hourly bars for the
  ~730 trading days Yahoo serves, stored as year-partitioned Parquet under `data/`. Daily and
  hourly are both committed; weekly and monthly are not, because they are a one-line resample of
  daily and committing them would only cost repository size.
- **Engine**: [Polars](https://pola.rs) is the dataframe library of choice. Prefer `pl.scan_parquet`
  + lazy expressions over eager pandas-style code.
- **Purpose**: data analysis, trade strategy research, and backtesting.

## Layout

```
data/universe/nse_universe.parquet        every NSE symbol -> company, series, ISIN, listing date,
                                          industry, and Nifty index membership flags
data/ohlcv/daily/year=*/data.parquet      symbol, date, open, high, low, close, adj_close, volume
data/ohlcv/hourly/year=*/data.parquet     symbol, datetime (Asia/Kolkata), open, high, low, close,
                                          volume — no adj_close, Yahoo does not adjust intraday
data/ohlcv/60minute_kite/year=*/          the same shape from Kite Connect: Nifty 500, back to
                                          2015-02, and corporate-action ADJUSTED (Yahoo's
                                          intraday panel is not). Use this for anything
                                          spanning 2018 or 2020.
data/ohlcv/_coverage_<interval>.csv       per-symbol bar counts and date ranges
data/ohlcv/_manifest.json                 provenance of the current snapshot + known caveats
scripts/download_market_data.py           (re)builds the universe and every price panel
scripts/validate_data.py                  structural, quality and cross-interval checks
scripts/screener.py                       pullback-in-uptrend screen over the daily panel
scripts/ema_support.py                    how reliably each name holds its daily 20/50 EMA
scripts/n_pattern.py                      impulse/pullback/resumption "N" on a rising 10 EMA
scripts/hourly_rsi_screener.py            hourly RSI cross above 60 under a daily/weekly/monthly
                                          RSI > 60 regime filter
scripts/kite_download.py                  deep intraday history from Kite Connect (back to
                                          ~2015, vs Yahoo's ~730 trading days)
scripts/rsi_slots_sweep.py                portfolio slot count vs return, drawdown and how
                                          much capital is actually deployed
```

## Conventions

- Prices live in **long format** (one row per symbol/bar), not wide. Keep it that way — it is what
  Polars group-by/window expressions want.
- Column names are lowercase snake_case. Intraday panels use a tz-aware `datetime`
  (`Asia/Kolkata`); daily/weekly/monthly use a `date`. `volume` is `pl.Int64`.
- Every panel is partitioned as `year=YYYY/data.parquet` so no file approaches GitHub's 100 MB
  limit. Read with `pl.scan_parquet("data/ohlcv/<interval>/**/*.parquet", hive_partitioning=True)`.
- Parquet is written with `zstd` compression.
- Refreshing data is `python scripts/download_market_data.py --interval daily`; it rewrites the
  interval directory from scratch. Batches are checkpointed under `.cache/` so an interrupted run
  resumes; `--fresh` ignores them.
- Commit the daily and hourly panels. Do not commit weekly/monthly — resample them from daily
  instead. Hourly is the one intraday panel worth carrying: it cannot be derived from daily, and
  Yahoo only serves a rolling ~730 trading days of it, so a snapshot is the only way to keep
  history that has already scrolled off.
- After changing anything that touches the data files, run `python scripts/validate_data.py`.
- `_manifest.json` is the source of truth for snapshot stats. Do not hard-code row counts in prose
  that will silently go stale — point at the manifest.

## Credentials

Kite Connect keys are read from `KITE_API_KEY` / `KITE_ACCESS_TOKEN` in the environment and
nowhere else. Never pass them as CLI arguments — they end up in shell history and in `ps`
output — and never write them into a file in the repository. The access token expires daily
and refreshing it needs an interactive login, so `kite_download.py` is run deliberately, not
on a schedule.

## Known data caveats

Read these before drawing conclusions from a backtest:

0. **The early years are thin.** The panel is dated from 2000 but holds only ~9% of the symbols
   that actually traded in 2000, rising to ~75% by 2008 and ~90% after 2020. Do not treat pre-2004
   results as market-wide. Curing this needs NSE bhavcopy (see below), not more Yahoo requests.
1. **Survivorship bias.** The universe is NSE's *current* main-board listing, so pre-snapshot
   delistings are absent.
2. **Adjustments.** `open/high/low/close` are split-adjusted; `adj_close` is also dividend-adjusted.
   Use `adj_close` (or the `adj_close / close` ratio) for total-return work.
3. **Partial last bar.** A snapshot taken mid-session/week/month leaves an incomplete final bar;
   `last_bar_possibly_partial` in `_manifest.json` flags it.
   Median history is ~2,400 bars, not 6,600 — filter on bar count before cross-sectional ranking.
4. **Upstream gaps and bad ticks.** Yahoo drops the odd session for individual symbols, and a small
   number of bars violate OHLC ordering. Reported by `validate_data.py`, not silently patched.
5. **Out of scope.** NSE Emerge (SME) symbols and BSE-exclusive listings are not served by Yahoo.

## Curing survivorship bias

Yahoo cannot fix this: it deletes delisted Indian tickers outright, returning zero bars even for
the years they traded (verified on AMTEKAUTO, ANDHRABANK, ALBK, ALOKTEXT). The point-in-time source
is NSE bhavcopy — the official end-of-day record of every symbol that traded on a given day.

- Legacy format, 1999 to ~2020:
  `nsearchives.nseindia.com/content/historical/EQUITIES/<YYYY>/<MON>/cm<DD><MON><YYYY>bhav.csv.zip`
- Current UDiFF format:
  `nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_<YYYYMMDD>_F_0000.csv.zip`
- Rename map: `nsearchives.nseindia.com/content/equities/symbolchange.csv` (1,057 records, 1999-2026)

Stacking ~6,650 daily files reconstructs the universe as it was on each date; a company simply stops
appearing after it dies. Filter to series EQ/BE/BZ — the files also carry SGBs and ETFs.

The cost is that bhavcopy prices are **raw**: no split or bonus adjustment. Rebuilding the
equivalent of `adj_close` from NSE's corporate-actions feed is the bulk of the work, and getting it
wrong manufactures fake gaps on every split. Key on ISIN where available, since symbols are renamed
and occasionally reused.

## LESSONS

- Report how much capital a strategy actually deploys before comparing it to a benchmark.
  This one runs 17-50% invested and sits in cash the rest of the time, so every "lower
  drawdown than the market" claim was partly just lower exposure. A part-time book measured
  against a fully-invested index flatters itself on risk and understates what the capital
  had to be reserved for.
- A parameter that dominates the result on a short window may do nothing over a full cycle.
  Slot count swung CAGR from +47.9% to +8.5% across 2.9 years of bull market and moved it
  by under two points across 11.6 years. Sweep every free parameter on the longest data you
  have before concluding it means anything.
- A buy-and-hold benchmark is the **mean** of normalised prices, never the median. The median
  is the path of the median stock: not tradeable, and always lower because cross-sectional
  returns are right-skewed. Reporting it as "equal-weight buy-and-hold" understated the
  benchmark by seven points of CAGR and manufactured the entire apparent edge of a strategy.
  When outliers threaten a mean, winsorise and say so — do not substitute a different
  estimator and keep the old label.
- A fix belongs on every path that needs it, not just the one being edited. `screener.py`
  guarded its RSI warm-up from the beginning; the backtest, written later against the same
  indicator, did not. The two disagreed for weeks and the unguarded one produced the numbers.
- A recursive EWM indicator returns a plausible number from the very first bar. Wilder's RSI
  seeded at zero reads exactly 100.0 on bar 1, which satisfies any "RSI > 60" regime filter
  for free — and those under-warmed signals scored three times the mean trade. Any indicator
  built on `ewm_mean` needs an explicit bar-count guard; nulls will not save you.
- Never hard-code a bars-per-year constant to annualise. `252 * 7` looked obviously right for
  NSE hourly and was 2.8% too high, overstating every CAGR in the repository. Derive elapsed
  time from the first and last timestamps.
- Get the arithmetic audited by something that did not write it. Four errors survived repeated
  self-review here — three of them pointing the same way, toward a better-looking result —
  and an independent pass found all four in fifteen minutes.


Rules accumulated from mistakes made in this repo. Add to this list — never remove — whenever a
mistake recurs.

- Always render a chart-pattern screener's hits before believing them. The N-pattern conditions
  passed on price geometry while matching stocks that looked nothing like the target shape; only
  the candlestick plot showed it. `--charts` exists for this.
- Constrain the *duration* of a pattern's legs, not just their size. Magnitude-only rules let one
  long trend masquerade as an impulse plus pullback, because the swing low pins to the edge of the
  search window.
- Never pick a threshold before looking at the distribution it sits in. A 60% "holds its EMA"
  cutoff sounded reasonable and returned 2 of 293 names, because the cohort median is 37%. Compute
  the distribution, then rank against it rather than gating on a number that felt right.
- A hit rate without a control measures the market, not the setup. A stock in a strong uptrend
  scores well on any entry rule. Always report the same statistic measured from random bars in the
  same window, and quote the difference.
- A screen's stated filters are not always its intent. "Daily RSI > 60" selects names that have
  already run; a pullback entry wants the daily RSI *low and turning up* while the higher
  timeframes stay strong. Restate the setup in words and check the filters actually select for it
  before building.
- Indicator code gets validated against a reference implementation before anyone trades on it.
  `screener.py`'s RSI is checked against a textbook Wilder loop on all three timeframes.
- Yahoo Finance rejects the default `python-requests`/`curl_cffi` user agent from this environment
  (`429` / SSL reset). Always pass a `requests.Session` with a browser `User-Agent` into
  `yf.download(..., session=...)`.
- `yfinance`'s `end` parameter is **exclusive**. Add one day when the caller means "up to and
  including this date", or the last session goes missing.
- Do not accept a Yahoo range limit at face value: an explicit 1h start/end is capped at 730
  *calendar* days, but `period="730d"` returns ~730 *trading* days — roughly 50% more history.
  Probe the actual limits before writing them into the code as a constant.
- `period=` requests fail for young listings (yfinance expands them into an explicit range anchored
  at the first trade date, which then exceeds the calendar cap). Always keep a narrower start/end
  fallback for the per-symbol retry pass.
- Do not judge data coverage by raw row counts per period: early years legitimately have fewer
  symbols because most constituents had not listed yet. Compare against the symbols actually listed
  at that time instead.
- Check whether a column carries real information before shipping it. Yahoo's intraday `adj_close`
  is a verbatim copy of `close`; shipping it would invite silently wrong total-return math.
- Never read an empty `yfinance` response as "this symbol has no data". Yahoo throttles past
  ~1500 consecutive symbol requests and yfinance swallows the 429 into an empty frame, which
  looks identical to a genuine miss. Classify the failure before recording a symbol as
  unavailable — and never derive coverage statistics from a run that was throttled part-way
  through.
- Read yfinance's *logger* for per-ticker failures, not `yfinance.shared._ERRORS`. Up to 1.6 that
  global held them; since 1.7 they live on a context object local to each `download()` call and
  the global is never written, so every read returns "no errors". Both the rate-limit guard and
  the "Yahoo does not carry this ticker" check were built on it and had silently become no-ops —
  a throttled hourly run recorded 25 batches of large caps (RELIANCE, RBLBANK, RALLIS...) as
  having no data. The logger emits `['A.NS', 'B.NS']: <reason>`, which is the channel to parse.
- A guard that reads a dependency's internals needs a test that makes it *fire*. Both guards above
  failed open — they returned "nothing wrong" when their data source went away, so nothing looked
  broken until the data was already corrupt. After any dependency upgrade, assert the guard still
  trips on a synthetic failure, and prefer failing closed when the signal is missing entirely.
- Only record a symbol as "not carried by the provider" when the provider explicitly says so
  (Yahoo: "no timezone found" / "possibly delisted"). A transient batch failure otherwise gets
  written into the manifest as permanent absence — a whole alphabetical block of real large caps
  (SIEMENS, SJVN, SOBHA...) was once shipped as "no history on Yahoo" that way. When a failure
  cannot be classified, fail loudly and keep the checkpoints rather than publishing the gap.
- Sanity-check a "missing data" list before trusting it. Contiguous alphabetical runs, or the
  presence of household names, mean a failed request batch, not absent data.
- Checkpoint long downloads to disk per batch. A run over thousands of symbols will get
  interrupted; writing results only at the end throws away hours of completed work.
- Back off for minutes, not seconds, on a 429. Retrying hard through a rate limit extends the
  block instead of clearing it.
- Report upstream data problems; do not silently repair or drop them. A backtest built on quietly
  patched data is worse than one built on data whose flaws are documented.
- Keep large Parquet panels partitioned (by year). A single file over 100 MB is rejected by GitHub
  outright, and anything near it makes the repo painful to clone.
- Sleep between retry attempts, not after the last one — a trailing back-off multiplies wasted time
  across thousands of symbols that will never resolve.
