# AGENTS.md

Guidance for AI agents (and humans) working in this repository.

## Working agreement

Whenever I point out or you catch yourself repeating same mistakes again, before continuing add it as a rule in #LESSONS below to avoid it in future

**MANDATORY — time-boxed autonomous loops: the brief must state ONE explicit wall-clock stop condition (e.g. "stop only after 60 min elapsed"), and the agent must keep generating fresh trials until it is met. A finished trial queue is NEVER the stop signal — Loop-8 exited after ~15 min of a 1-hour brief because the brief listed work but defined no stop condition, and queue-exhaustion was read as completion.**

**MANDATORY — never rebuild a file from rendered/displayed content. A rendered copy (skill block, diff, chat text) is a lossy projection that silently drops what the renderer omitted: rebuilding the skill file from its skill block deleted the `name`/`description` frontmatter the loader needs. Use `edit` for existing files; use `write` only for files read from disk in this session or for brand-new files; after any full-file write, verify with a full `git diff <path>` (not `--stat`) or a first-lines diff against `git show HEAD:<path>`. The generalized rule: when a transformation is lossy or output was filtered, verify the invariant explicitly (frontmatter present, JSON parses, TRAIN line printed) — never infer it from a summary. Details in #LESSONS.**

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

research/                                 persistent research records (committed)
  tested_mechanisms.tsv                   every mechanism ever tested, with verdicts
  README.md                               how the registry is maintained and read
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
  `attach_market_cap`, `find_trades`, `simulate`, `elapsed_years`, `performance`. A second copy
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
- Annualising from a bar count is only safe if no calendar period is missing.
  `strategy_lab.seg()` divides month counts by 12; one skipped month would silently
  understate elapsed time and overstate CAGR. The Loop-11 audits hand-verified the
  monthly panel is continuous (139 intervals ≈ 2015-01 → 2026-09), but nothing in
  the harness asserts it — assert month continuity (or derive elapsed time from the
  first/last timestamps) before trusting a CAGR.
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
- Batch trial shells must keep stderr visible (no `2>/dev/null`) and build
  `--params-json` as full literal strings, never by appending keys to a shell
  variable that already ends in `}`. Loop-9 lost trials to exactly this: a wrong
  universe flag crashed silently under stderr suppression, then `"$F,...}"` with
  F already brace-closed produced invalid JSON across two batches — every run
  "completed" printing nothing while logging nothing. A batch that prints no
  TRAIN/KEEP/DISCARD line per trial is a failed batch: stop and read the error,
  never re-run blind.
- The batch-shell rule covers the orchestrator's own probe commands too, not just
  the worker's. Loop-10 lost six confirmation trials to a shell function that piped
  `2>&1 | grep TRAIN`: the argparse error vanished, empty output read as "no
  result", and the same six commands worked as plain literals. Any shorthand that
  filters output is `2>/dev/null` by another name — run the first trial of a new
  family as a plain literal command before wrapping it.
- Never rebuild a file from rendered/displayed content: rendering strips metadata.
  Rewriting `.claude/skills/autoresearch-trading/SKILL.md` from the skill-content
  block silently deleted its `name`/`description` YAML frontmatter the loader
  needs. Edit in place, or diff the first lines against `git show HEAD:<path>`
  before overwriting.
- Check the coverage of any reference column before building a mechanism on it.
  The universe snapshot's `industry` is null for 2,059 of 2,558 symbols (~80%).
  A sector-neutral rank silently became a no-op (subtracting one giant group's
  mean preserves order), a "sector momentum" gate became a market-momentum veto,
  and a per-industry concentration cap capped an "UNKNOWN" mega-group — all three
  were read as sector evidence until `null_count()`/`n_unique()` was checked.
  Coverage first, mechanism second, for every join key and attribute a strategy
  depends on.
- Checkpoint long downloads to disk per batch. A run over thousands of symbols will get
  interrupted; writing results only at the end throws away hours of completed work.
- Back off for minutes, not seconds, on a 429. Retrying hard through a rate limit extends the
  block instead of clearing it.
- Report upstream data problems; do not silently repair or drop them. A backtest built on quietly
  patched data is worse than one built on data whose flaws are documented.
- Keep large Parquet panels partitioned (by year). A single file over 100 MB is rejected by GitHub
  outright, and anything near it makes the repo painful to clone.
- A blind forward window is blind to diagnostics too, not just to strategy returns. A Loop-27
  designer chose an exposure rule's sign after printing its signal's spikes, including Jan-2022,
  which is in the forward window. That rule then passed every gate check, with the forward drawdown
  gain coming from that same firing, and the crown had to be revoked. Diagnostics that inform a
  design may only print months before the split. Remembered post-split market events ("the 2022
  small-cap unwind") are forward data as well.
  The same loop's orchestrator broke this too: a scratch attribution printed `run_book`'s
  `full_cagr`/`full_dd`, which include the forward window. Filter scratch metrics down to the
  train keys before printing them, not after.
- Sleep between retry attempts, not after the last one — a trailing back-off multiplies wasted time
  across thousands of symbols that will never resolve.
- Best strategy means best FORWARD performer, not best train. Train selects candidates,
  forward crowns the winner — a train leader whose forward lags the bench is overfit,
  never the best. But selecting on forward spends the holdout: re-validate the
  forward-pick on an un-fitted universe before believing it.
- Always report CAGR *and* max drawdown together, train and forward both, every time
  a strategy is discussed. CAGR alone hides risk; the user weighs both equally.
- Calmar (ret/DD) is always decision-relevant for the user: quote it with every
  CAGR/DD pair, train and forward, strategy and bench alike.
- One harness version per comparison. A harness edit (strategy_lab backtest rewrite)
  changed same-params numbers mid-ledger (newhigh 15/0.1/6 read 28.26/28.42 under the
  old harness, 30.02/9.89 under the new one), and a stale row nearly crowned a false
  best. Never rank across a harness change — re-run the contenders fresh first.
- Imported defaults leak. When a new mechanism file composes a term from an existing
  file, the source file's internal defaults silently activate unless overridden
  (Loop-13: gatefail's `gf_w=0.05` and printclose's `clv_scale=0.8` would have broken
  the off-switch identity). Set your own neutral default first, and require the
  off-switch to reproduce the champion exactly before any variant is believed.
  To NEUTRALIZE a delegate's term, FORCE the key (`p["gw_w"] = 0.0`), never
  `setdefault` — a caller-passed value beats a setdefault, so passing the
  champion's `gw_w` through while re-implementing its term double-applies it
  (Loop-14's wobble-recency first smoke read 81.36 instead of the identity).
- Re-measure, don't inherit, when the promoted config changes. Loop-13's gw 0.13
  promotion carried the gw 0.12 cost-stress numbers (84.44 / calmar 4.79) into the
  README and the champion annotation; a worker's control mismatch (84.70 / 4.80)
  exposed it. Every auxiliary figure (cost stress, window splits, transfer) is valid
  only for the exact params it was measured on — re-run it on promotion, or label it
  with the params it belongs to.
- The loop stops at the clock, never at queue exhaustion. Loop-15 was briefed for
  2 hours (stop ~15:33 IST); it ran its champion, all screens and two audits, then
  began close-out at ~14:35 and reported ~14:36 — 60 minutes into a 120-minute brief.
  The queue was empty because the orchestrator let the design pipeline drain: both
  designers were allowed to finish at their briefed stops without being re-tasked and
  no checkpoint noticed the hour that remained. The missing mechanism is an
  ORCHESTRATOR clock: run `TZ=Asia/Kolkata date` at every phase transition (start,
  each design round, before close-out) and treat close-out as a fixed window before
  the stop (last 15-20 min), not as the reward for finishing the checklist. If the
  queue empties early, the next action is a new design round (or a new designer) —
  never the report. Estimated elapsed time drifts and will read hours ahead of the
  real clock; only the shell's date is authoritative.
  Repeated in the Loop-27 routine test fire: it closed out ~35 min into a 60-min
  run and wrote "60 min, 22:43-23:43 IST" into loop_state from the planned STOP.
  Save the start epoch to a file, refuse close-out before 45 elapsed minutes by
  the shell clock, and write only times read from `date` at that moment.
- A train gain from a book-composition mechanism must be traced to its firing
  events before it is promoted. Loop-16's incumbency hurdle kept a +0.60pp train
  "improvement" (DD and forward identical) that turned out to rest on ONE
  firing event propagating through the path-dependent held set into just 3
  differing decision months out of 139. Count the months in which the
  candidate's picks actually differ from the base's; a gain sourced from a
  handful of name-months is a sample of a handful, not an edge. The harness's
  own keep rule cannot see this: it scores returns, not the mechanism's
  footprint.
- A mechanical keep is not automatically a better strategy: check calmar and
  the forward window before promoting. Loop-17's `pxlevel` keep raised train
  CAGR by +0.58pp but widened drawdown by 1.64pp (calmar 5.22 vs 5.69) and
  collapsed forward to +38.0%/−20.8% from +49.0%/−12.3% — left unpromoted.
  The user weighs CAGR and drawdown equally, and the forward window is the
  judge; a train gain paid for with risk and forward performance is an
  artifact, not an upgrade.
- A signal's holdout risk can be DOSE-DEPENDENT with a sharp threshold:
  screen the dose neighbourhood, not just the window/weight axis, and prefer
  the risk-clean dose when the full dose's extra train is paid on the forward
  window. Loop-20's CS-spread tilt at w −0.05 holds champion-level forward DD
  (−10.4%) at every window (lb 4/6/12), while −0.075 and all larger doses trip
  a 2.68pp forward-DD break (−13.1%) for only +0.8pp of train; promotion took
  the −0.05 cell and declined the mechanically-higher −0.1 keep
  (103.83/−15.0/calmar 6.92 but fwd +52.5/−13.1).
- Know which months a tilt can act in before believing its gain or its
  negative. The champion's age/outrank tilts sit AFTER the book cap; when the
  cap binds below book size (cap_weak 11 < top 15) every capped name is held
  and the tilts are inert — they only pick names in full-breadth months
  (cap_full 20 > 15). Moving them pre-cap makes them act in every invested
  month and is train-destructive (74.9–97.2 vs 98.7, Loop-20
  `strat_l20o_tiltorder`): placement is a mechanism, and a composition must
  preserve the screened order.
- Two tilts on the same underlying axis interfere; different transforms of
  one NEW channel can be super-additive. Loop-20: illiquidity × spread (both
  load on turnover-adjusted price movement) — best combo 102.1, below both
  parents (102.4 and 103.8), avg form below base; dividend-factor size ×
  timing — 103.6 vs an additive prediction of 101.1 (+2.5pp beyond
  additivity, footprint 39/139) though it pays DD. Compose across channels,
  not within one, and measure the composition instead of assuming it.
- A new join key needs a coverage audit with a pre-registered floor before a
  mechanism is built on it. Loop-20's sector attempt built a company-name
  keyword classifier (agreement 77.6% vs 15.5% chance where labels exist) but
  it covered only 56.0% of the panel (< the 70% gate) and its union with the
  20%-populated industry column tops out at 64.2% — the sector family stays
  untestable from committed data; the fix is an external sector map, not
  another mechanism. Measure coverage, then build; stop when the gate fails
  rather than filling gaps with generic words that fake coverage.
- A two-point parameter check is not a neighbourhood. Loop-21's spread-change
  term read 4:102.2 → 12:103.9 across its two documented lags and looked
  monotone; the orchestrator's 8/10/14/16 grid exposed the oscillation
  (8:102.8, 10:102.7, 12:103.9, 14:102.3, 16:103.2) — the peak was a
  knife-edge, not a plateau, and the candidate was declined. Any window
  parameter that decides a promotion needs at least two interior neighbours
  measured on the SAME ledger before the cell is believed.
- After an environment restart, check `ps` for surviving processes before
  relaunching a batch. Loop-21's server restart cancelled the session but a
  nohup'd grid script kept running; the relaunched copy then wrote the same
  ledger concurrently (duplicate rows, double load). Kill orphans
  (`ps -eo pid,ppid,cmd | grep <script>`) before relaunching, and expect the
  pre-restart process to be reparented to init (ppid 1) rather than killed.
- A suspension can last hours, not minutes. Loop-21's environment froze for
  ~14 h across two restarts; when the session resumed, the briefed stop
  (01:08/01:30 IST) was long past while the harness clock showed 15:00. On
  waking: re-read `TZ=Asia/Kolkata date`, do NOT resume trial campaigns whose
  stop has passed, and go straight to close-out — the durable ledgers and
  delivered files are the record, and fresh trials 14 h later risk mixing
  harness versions inside one ledger.
- A backtest that fills at the bar its signal read, on a universe with price
  bands, is measuring un-fillable trades. The legacy `strategy_lab` harness
  bought every pick at the same month-end close the score used; on the full
  NSE board ~30% of the L21 champion's entries closed at their high and ~16%
  printed one price all day (upper-circuit locks, no sellers). Refusing only
  the locked entries took its forward from +55.0%/−11.0% to ~+21%/−39% — far
  outside a random-block control (fwd 42–62%) — and the full realistic
  model (next-open fill, lock block, INR 50 lakh liquidity floor, 50 bps)
  reads fwd −5.2%/−41.2%. Twenty-one loops of PIT, identity and arithmetic
  audits never asked whether the trade could be executed. Model the fill
  (next session, locks, liquidity) in the harness before ranking anything,
  and stamp every ledger with the execution model it was measured under.
- A train ranking that is noise-aware and fold-robust still cannot see the
  forward window — only the gate can. Loop-23's three gated candidates beat
  the champion's train CAGR and DD by 3–8pp, passed neighbours, cost, noise,
  footprint and Nifty 500 transfer, and ALL THREE fell short of its forward
  CAGR (16.9 / 20.4 / 17.1 vs 20.6). Never crown from the ledger; and count
  the whole search when deflating a margin — the first gate runs counted one
  ledger (2 rows) while 112 trials had been run across the loop's ledgers.
