---
name: autoresearch-trading
description: Use when running autonomous trading-strategy research loops in this repo — hill-climbing params with auto_research.py or evolving whole strategy mechanisms with strategy_lab.py, always with train/forward split, keep/discard logging, and bench comparison.
---

# Autoresearch Trading

Repeatable autonomous research loops for NSE strategies. Two phases: first
climb params on a fixed strategy, then evolve the strategy mechanism itself.
The agent changes code each loop; a fixed harness keeps score.

## Repo facts (do not re-derive, verify only)

- Data: `data/ohlcv/daily/year=*/data.parquet` (full NSE board, 2000→date),
  `data/ohlcv/60minute_kite_clean/` (Nifty 500 intraday to trade, never the raw
  Kite panel), `data/universe/nse_universe.parquet` (index flags).
- Reuse, never reimplement: `screener.rsi` (Wilder, validated), `screener.resample`,
  `momentum_rotation.performance`, `auto_research.load_monthly`.
- Scratch goes to `.cache/` (gitignored). Never write to `data/`.
  Exception: the four `best*.json` ledgers are force-tracked in git
  (`.cache/strategy_lab/best.json`, `best_validate.json`,
  `.cache/auto_research/best.json`, `best_nse_all.json`) — both harnesses
  resume from `best.json` alone, so these files are all a fresh session
  needs to continue from the last best instead of from scratch.
  Per-worker `w<ID>_best.json` ledgers are scratch: promote their winners
  onto the tracked ledgers in the same loop, or the finding dies with the
  session.
- Reference columns can be near-empty: the universe snapshot's `industry` is
  null for ~80% of symbols. Check `null_count()`/`n_unique()` before building
  any mechanism on an attribute — an 80%-null industry silently turns a
  "sector" rank into a no-op and a sector gate into a market gate.
- Costs always charged (default 25 bps/side monthly). Years from month counts,
  never a bars-per-year constant. Equal-weight mean buy-hold bench, never median.
- Universe is today's listing: survivorship flatters everything. Winners must be
  validated on an un-fitted universe before being believed.

## Phase A — param loop (fixed strategy, moving numbers)

```bash
python scripts/auto_research.py --iterations 50 --seed 42 --split 2022-01-01
python scripts/auto_research.py --resume --iterations 50 --seed 43 --split 2022-01-01
python scripts/auto_research.py --universe nse_all --iterations 50 --split 2022-01-01 \
  --results .cache/auto_research/results_nse_all.tsv --best .cache/auto_research/best_nse_all.json
```

- `--split YYYY-MM-DD` divides train (search) from forward (holdout).
  Selection uses TRAIN only; forward is logged, never used to accept.
- Keep iff: train CAGR > best + `--min-delta` (0.05pp) AND train DD above
  `--max-dd` floor and within `--dd-slack` (2pp) of best DD AND both train
  halves > 0. Else discard. Crash: log, continue.
- If the baseline itself breaches `--max-dd`, relax the floor to the baseline
  instead of deadlocking the loop on arrival (default floor is 70 for this reason).
- Long runs: background shell loop, 5 min wall clock, new `--seed` per chunk,
  always `--resume` so every chunk starts from current best.

## Phase B — strategy loop (moving mechanism, fixed harness)

New idea = new file `scripts/strat_<name>.py` implementing this contract:

```python
NEEDS_DAILY = True/False
SPACE = {...}  # params this strategy owns (docs only)
def score(panels, params) -> (scores, regime):
    # panels: px (months x stocks closes), months, cols, daily (long
    #   symbol/date/close, only if NEEDS_DAILY), start_i
    # scores: months x stocks float, NaN = ineligible, higher = better rank
    # regime: bool per month, False = cash that month
```

Point-in-time law: a holding month starting at `months[m]` may use only daily
bars with `date < months[m]` and closes through `px[m]`. HTF RSIs need a
warm-up guard (Wilder seeded at zero reads 100 on bar one and passes any
regime filter for free — require ~42 months of history per name).

```bash
# 1. verify harness: must EXACTLY match auto_research on same params
python scripts/strategy_lab.py --candidate strat_momentum \
  --params-json '{"lookback":12,"regime_ma":10,"stock_ma":0,"abs_mom":false}' \
  --universe nse_all --top 25
# 2. trial a new mechanism (first entry becomes baseline in best.json)
python scripts/strategy_lab.py --candidate strat_rsi_pullback --params-json '{}' \
  --universe nse_all --top 25
# 3. mutate: compose mechanisms by importing candidates, never copying signals
python scripts/strategy_lab.py --candidate strat_combo \
  --params-json '{"lookback":9,"regime_ma":6,"abs_mom":true}' \
  --universe nse_all --top 25
```

Verdict logic mirrors Phase A (train selects, forward judges, halves must pass)
and appends to `.cache/strategy_lab/results.tsv`. Keep `top` and costs fixed
when comparing mechanisms.

## Searchable risk (nothing hardcoded)

Risk settings are trial params, not house doctrine. Per trial, via
`--params-json` keys, `--trail-k` / `--max-hold` flags, or the candidate's
third return value `risk={trail_k, max_hold}` (candidate wins on conflict):
- `trail_k`: exit a name whose month low prints below its running peak x (1-k)
- `max_hold`: drop a name after N months held, however it ranks
- `regime` is exposure in [0,1], so partial tiers (0.4/0.7/1.0) are expressible
  per trial instead of cash-or-full
- `--select cagr|calmar`: the keep ruler. `cagr` chases raw train return,
  `calmar` chases ret/DD with a `--cagr-guard` floor against cash-like winners.
  Fixed per ledger so trials stay comparable; the loop discovers risk
  SETTINGS, never the ruler mid-ledger.

## Reading results (what counts as winning)

- Train-only CAGR lead with forward lagging bench = overfit smell, not a winner.
  (Seen live: momentum train +27.9% then forward +12.3% vs bench +14.7%.)
- Consistent bench-beat on BOTH windows outranks a higher train number.
  (Seen live: loose combo train +20.8%, forward +17.8% vs bench +14.7%.)
- Gates that cut DD but leave the book <30% invested usually just buy cash-like
  returns — check `invested` before celebrating `ret/DD`.
- Negative results are findings: keep the file, log the row, say so.

Run every command from the repo root (the folder containing scripts/ and data/),
not from the skill directory.

## Execution pattern (orchestrator + parallel mechanism workers)

Time-boxed loops run as an orchestrator plus N background workers, so the main
session stays free to talk and to design while the workers burn the clock on
numbers. Three rules make the parallelism safe: **one writer per ledger file,
one mechanism per worker handoff, one shared wall-clock stop.**

- **Orchestrator (main session) — owns the STRATEGY loop and its BUDGET.**
  The main agent gets the loop's wall-clock budget (default: 50 min for a
  "one hour" loop, leaving slack for close-out) and sets every worker's stop
  condition INSIDE it, as an absolute UTC time — never a queue length. It
  designs new mechanisms (`strat_*` files: rank + regime + book-size logic),
  writes each worker brief (its mechanism, baseline params, exact literal
  trial list, isolated ledger paths, ONE wall-clock stop, report format),
  keeps the mechanism queue deep enough that nobody grinds or idles, and
  re-plans dynamically from ledger tails. It monitors via side-channel only
  (`ps`, ledger tails, `git status` — never interrupts), verifies claims
  against `best.json`/ledger, promotes winners to the main ledger as the
  single writer, owns commit + push, and reports to the user.
- **Worker (background subagent) — owns the NUMBERS for its handoff.**
  It does not invent strategy, does not edit files, does not run git. It runs
  its pre-registered trials one at a time, logs every row through the harness,
  and stops only at its wall-clock stop. Worker model: **the same model and
  reasoning effort as the parent main session** — look the parent's model up
  via the models tool and pass that exact providerID/modelID (with the same
  effort variant). Never hardcode a model ID in this skill, and never
  downgrade workers to a different or free-tier model: in Loop-11 all three
  workers died on a free model's rate limit while the parent model was never
  throttled, leaving the loop with no numbers and forcing the orchestrator to
  run the queues itself.

### Ledger isolation (mutual exclusion)

Concurrent `strategy_lab.py` processes must never share a ledger. Give every
worker its own pair and make it pass them in EVERY command:

    --results .cache/strategy_lab/w<ID>_results.tsv \
    --best-json .cache/strategy_lab/w<ID>_best.json

The main ledger (`.cache/strategy_lab/results.tsv` / `best.json`) stays
single-writer. With one worker running it may own the main ledger directly;
with several, nobody touches it until the orchestrator's promotion pass.
Promotion: after all workers stop, replay the winners onto the main ledger
one at a time, in ratchet order (each keep must sit within `--dd-slack` of
the standing best at that moment), then re-read `best.json` and compare with
what was written — if it changed underneath (a concurrent writer slipped in),
re-run instead of accepting a stale verdict. `results_validate.tsv` /
`best_validate.json` holds the un-fitted-universe verdict and follows the
same single-writer rule.

### Worker failure policy (the loop does not stop)

A worker error — rate limit, crash, timeout, provider outage — is a staffing
event, not a loop stop. The wall-clock stop is the only stop. On an error
notification (or when a worker's ledger mtime goes stale with no live
process):

1. Read its ledger tail and `w<ID>_best.json` — state is durable, nothing is
   lost with the session.
2. Relaunch the SAME handoff to a fresh worker, or hand the remaining queue
   to a live worker. The fresh brief starts with: "resume from
   `w<ID>_results.tsv` / `w<ID>_best.json`; rows already there are done, do
   not repeat them."
3. If the provider still refuses workers, absorb the queue in the main
   session — the orchestrator runs the trials itself on the worker's ledger.
   This is cheap insurance: in Loop-11 the absorbed queues produced ~40 rows
   while the free-tier workers produced none. The ledger, not the role, is
   the record.
4. Never stand still and never let a worker failure trigger close-out early.
   A dead worker is a queued action, not a reason to pause: relaunch first,
   close out only at the wall-clock stop. The test of the orchestrator is
   whether the loop keeps producing rows after a worker dies.

The orchestrator owns worker liveness: check `ps` and ledger mtimes
periodically and redeploy without waiting for an error notification.

### Worker rotation (breadth beats depth)

A worker must not sit on one mechanism for long: cap each handoff at roughly
8–10 trials or ~10 minutes, then rotate to the next mechanism. A trial costs
~12 s of compute, so a worker can burn 30–60 trials an hour — the binding
resource is the supply of distinct, well-posed mechanisms, not compute. The
orchestrator therefore writes new `strat_*.py` files while workers run and
keeps queue depth >= number of workers. If a worker's queue empties before
its stop, it tests additional one-key variants of the best of its handed
mechanisms, rotating — never a deep grid on a single one — unless the
orchestrator briefed that one mechanism as the live line worth depth.

### Briefing rules (the worker channel is one-shot)

A background worker cannot be re-briefed mid-flight, so its brief carries the
whole round: baseline command, exact literal trial list, rotation/fallback
rule, ledger paths, stop time, report format. Hard-won rules:

- One trial per shell command; never suppress stderr and never grep-filter the
  command output; a trial printing no TRAIN line is FAILED — stop, read the
  raw error, never re-run blind. Build `--params-json` as full literal JSON;
  never assemble it from shell variables. (This applies to the orchestrator's
  own probe commands too.)
- Trials are strictly SEQUENTIAL, one process at a time per ledger. Never issue
  parallel tool calls that run `strategy_lab.py` against the same
  `--results`/`--best-json` pair: concurrent runs can lose a keep in a
  best.json read-modify-write race. Loop-11 caught a worker running five
  trials at once on one ledger; the rows survived (atomic appends at this
  line size) but the ledger best could silently lag. If parallel trials are
  wanted, give each process its own ledger pair and merge afterwards.
- Dedupe before a batch: grep the ledger for the candidate name and param
  signature and skip any (candidate, params) row that already exists —
  identical reruns are noise, not evidence. A retest is legitimate only on a
  changed base mechanism (new exposure shape, new book composition), and the
  brief should say which base changed and why.
- New mechanisms go into NEW files; never edit an existing `strat_*` file to
  change its meaning, or past ledger rows stop meaning what they meant.
- Report format: stop-time confirmation, trial count, every KEEP, the full
  `w<ID>_best.json`, a compact trial table, raw errors for any failure.

**"Run the loop for N minutes" means:** the orchestrator runs its own clock
(N = 50 min default; workers get stops well inside it), designs and feeds new
mechanisms round by round, and closes out — promotion, validation, commit,
push, report — inside its own budget. If workers are still running at the
orchestrator's cutoff, that is a planning error to avoid next loop (brief
worker stops early enough to leave 10+ min for close-out); it is not a reason
to wait for them.

## Fresh-session bootstrap

1. `git log --oneline -5`, `git status --short` — find the workstream branch.
2. Read `.cache/auto_research/best*.json` and `results*.tsv` tails for current best.
3. Read `.cache/strategy_lab/results.tsv` for mechanism history.
4. Continue the loop from current best; commit new `strat_*`/harness files with
   messages stating setup + verdict.
5. End of loop: `git add` any changed `best*.json` ledgers plus new files,
   commit, and `git push origin <workstream-branch>` — the next fresh
   session (or clone) must find the latest best on git, never restart
   from scratch.
