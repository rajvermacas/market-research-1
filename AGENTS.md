# AGENTS.md

Guidance for AI agents (and humans) working in this repository.

## Working agreement

Whenever I point out or you catch yourself repeating same mistakes again, before continuing add it as a rule in #LESSONS below to avoid it in future

## Project

A **backtesting playground for the Indian equity market (NSE)** — not the repository of a single
strategy. The data is already committed; `scripts/` is where strategies go.

- **Data**: daily OHLCV for every NSE main-board listing (2000 to date), Yahoo hourly bars for
  the rolling window Yahoo serves, and a corporate-action-adjusted Kite hourly panel for the
  Nifty 500 back to 2015-02. All year-partitioned Parquet under `data/`. Weekly and monthly are
  not committed — they are a one-line resample of daily.
- **Engine**: [Polars](https://pola.rs) is the dataframe library of choice. Prefer `pl.scan_parquet`
  + lazy expressions over eager pandas-style code.
- **Purpose**: try strategies against this data, measure them honestly, and keep the result —
  including the negative ones. Several strategies in `scripts/` were tested and found not to
  work; they stay, with their numbers in the README's results ledger.
- **Shape of the work**: one script per strategy or per experiment, each with an argparse CLI and
  a docstring that states the setup in words before any code. Nothing is a library-only module;
  everything runs from the command line.

## Layout

```
data/                                     the substrate — strategy code reads it, never writes it
  universe/nse_universe.parquet           every NSE symbol -> company, series, ISIN, listing date,
                                          industry, and Nifty index membership flags
  ohlcv/daily/year=*/data.parquet         symbol, date, open, high, low, close, adj_close, volume
  ohlcv/hourly/year=*/data.parquet        symbol, datetime (Asia/Kolkata), open, high, low, close,
                                          volume — no adj_close, Yahoo does not adjust intraday,
                                          and only ~730 trading days deep
  ohlcv/60minute_kite/year=*/             the same shape from Kite Connect: Nifty 500, back to
                                          2015-02, corporate-action ADJUSTED
  ohlcv/60minute_kite_clean/year=*/       the above after clean_kite_panel.py — USE THIS ONE.
                                          Anything spanning 2018 or 2020 needs a Kite panel;
                                          the raw one carries token-reuse artefacts.
  ohlcv/_coverage_<interval>.csv          per-symbol bar counts and date ranges
  ohlcv/_manifest.json                    provenance of the Yahoo snapshot + known caveats
                                          (it does not describe the Kite panels)

scripts/                                  the playground

  data pipeline
    download_market_data.py               (re)builds the universe and the Yahoo panels
    kite_download.py                      deep intraday history from Kite Connect
    clean_kite_panel.py                   repairs token reuse, zero prints, adjustment breaks
    validate_data.py                      structural, quality and cross-interval checks

  strategies and screeners
    screener.py                           pullback-in-uptrend screen over the daily panel
    hourly_rsi_screener.py                hourly RSI cross above 60 under a daily/weekly/monthly
                                          RSI > 60 regime filter
    n_pattern.py                          impulse/pullback/resumption "N" on a rising 10 EMA
    ema_support.py                        how reliably each name holds its daily 20/50 EMA
    rsi_backtest.py                       backtest of the hourly RSI setup — and the shared
                                          engine (find_trades / simulate / performance)
    momentum_rotation.py                  cross-sectional momentum, monthly rebalance, regime
                                          overlay

  research labs (one question each, about a strategy already in the tree)
    rsi_filter_lab.py                     marginal effect of each candidate entry filter
    rsi_stop_lab.py                       do the filters stack, and is the stop the real problem
    rsi_combo_search.py                   every subset of the optional filters, scored
    rsi_slots_sweep.py                    slot count vs return, drawdown and capital deployed

  the loop
    strategy_loop.py                      unattended search over the whole family: propose a
                                          strategy, backtest it, rank it, mutate the best and
                                          repeat. Scores on a train window only, reports the
                                          holdout beside it, and audits its own leaderboard
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
- Commit the daily, hourly and Kite panels. Do not commit weekly/monthly — resample them from
  daily instead (`resample(daily, "1w" | "1mo")` in `screener.py`). Intraday panels are worth
  carrying because they cannot be derived from daily and the providers only serve a rolling
  window, so a snapshot is the only way to keep history that has already scrolled off.
- All scratch output — caches, feature frames, screener results — goes under `.cache/`
  (gitignored). Nothing a run produces belongs in `data/`.
- After changing anything that touches the data files, run `python scripts/validate_data.py`.
- `_manifest.json` is the source of truth for snapshot stats. Do not hard-code row counts in prose
  that will silently go stale — point at the manifest.

## Adding a strategy

A strategy is a new file in `scripts/`, named for the mechanism. Before writing one, read the
LESSONS at the bottom of this file — every rule there was paid for.

- **Reuse the toolkit; do not write a second indicator.** `screener.rsi` (validated against a
  textbook Wilder loop), `screener.resample`, `screener.fetch_market_caps`,
  `hourly_rsi_screener.ema`, and from `rsi_backtest`: `prior_bar_rsi`, `attach_htf`,
  `attach_market_cap`, `find_trades`, `walk_signals`, `simulate`, `elapsed_years`,
  `performance`. A second copy
  drifts from the first, and then two scripts disagree and the wrong one produces the numbers.
- **Say the setup in words in the docstring** — entry, stop, exit, universe, rebalance — then
  check the filters actually select for it.
- **Point-in-time discipline.** Higher-timeframe values read the last *completed* bar; anything
  fetched live (market cap) is walked back and the assumption stated. No column may depend on a
  bar the decision could not have seen.
- **Warm-up guards are mandatory** on any recursive indicator (`period * 3` bars is the template
  in `prior_bar_rsi`), and indicators are seeded from the longest history available rather than
  from the panel being traded.
- **Report, every time**: the equal-weight buy-and-hold control over the same window (the *mean*
  of normalised prices), max drawdown, return per unit of drawdown, how much capital was actually
  deployed, the cost assumption, and the result on each half of the window separately.
- **Sweep free parameters on the longest panel available**, which for intraday means
  `60minute_kite_clean`, not the 2.9-year Yahoo hourly panel.
- **One adjustment convention per test.** Do not mix the unadjusted Yahoo hourly panel with the
  adjusted Kite one; `rsi_backtest.py --daily-from-hourly` exists for exactly this.
- **Write the outcome down** — in the commit message, and as a row in the README's results ledger.
  A negative result is a finding and is kept, not deleted.

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
2. **Adjustments differ per panel.** In the daily panel `open/high/low/close` are split-adjusted
   and `adj_close` is also dividend-adjusted — use `adj_close` (or the `adj_close / close` ratio)
   for total-return work. The Yahoo hourly panel is not corporate-action adjusted at all; the Kite
   panels are. Never mix two conventions inside one test.
3. **Partial last bar.** A snapshot taken mid-session/week/month leaves an incomplete final bar;
   `last_bar_possibly_partial` in `_manifest.json` flags it.
   Median history is ~2,400 bars, not 6,600 — filter on bar count before cross-sectional ranking.
4. **Upstream gaps and bad ticks.** Yahoo drops the odd session for individual symbols, and a small
   number of bars violate OHLC ordering. Reported by `validate_data.py`, not silently patched.
5. **Kite artefacts.** Kite reuses instrument tokens, so the raw `60minute_kite` panel gives a
   recent listing the prices of whatever security held its token earlier. Trade
   `60minute_kite_clean`. 28 symbols whose total return still disagrees with Yahoo's by more than
   a quarter are reported by `clean_kite_panel.py` rather than patched.
6. **Out of scope.** NSE Emerge (SME) symbols and BSE-exclusive listings are not served by Yahoo.

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

- Warm-up truncation is a silent window filter, and it flattered this strategy by 9 points
  of CAGR. Seeding the monthly RSI from the intraday panel itself needs 42 monthly bars,
  which quietly moved the backtest start from 2015-02 to 2018-08 and deleted the worst
  regime the data contained. Seeding the higher timeframes from the deep daily panel
  instead recovers those 3.5 years, and the best configuration falls from +27.1% to
  +18.1% CAGR while return-per-drawdown collapses from 1.20 to 0.64. Always seed
  indicators from the longest history available, and check what a warm-up rule is
  removing before accepting a result computed after it.

- Do not scale out of a strategy whose edge lives in the tail. Taking half the position at
  1:2 or 1:3 and running the rest cut this setup from +27.1% CAGR to +14.8%, because the
  86% stop-out rate is paid for entirely by the far-distance winners that a partial exit
  gives away. Scaling out helps a high-win-rate mean-reverting system; it is a tax on a
  low-win-rate trend one.
- A regime filter tuned on one universe is not a regime filter. Market breadth above 0.65
  lifted Nifty 500 from +17.7% to +27.1% CAGR and cut its drawdown by half, then on the
  full NSE board over an overlapping window it took the same configuration from +44.2% to
  +3.8%. A real regime effect cannot do that. Test any regime rule on a universe it was
  not fitted to before believing it.

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
