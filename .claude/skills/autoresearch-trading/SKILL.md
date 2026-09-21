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
- Harness quirk every audit should know: the pick at month t is masked by
  `isfinite(px[t+1])` (a next-month-close availability mask). It is
  conservative — it removes candidates, never adds them — and it is baked
  into every recorded number; never "fix" it without re-running the whole
  ledger under one harness version.
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

**Book-state mechanisms need a causal replay.** The harness re-picks top-N
every month with no incumbency memory, so any mechanism that depends on the
held book (incumbency, attrition, hold clocks, retention bonuses) must replay
the harness pick rule month by month inside the candidate, folding its own
modification in before each pick. Validate the replay by reproducing the
champion to the basis point with a no-op config (Loop-12's `strat_l12a_*`
files did this; the replay is the reason those negatives are trustworthy).

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
  condition INSIDE it, as an absolute wall-clock time in **IST (Asia/Kolkata)**
  — never a queue length, never UTC. All briefs, reports and timestamps the
  user sees are IST; workers verify the clock with `TZ=Asia/Kolkata date`.
  (The harness's own ledger timestamps stay UTC — do not conflate the two.) It
  designs new mechanisms (`strat_*` files: rank + regime + book-size logic),
  writes each worker brief (its mechanism, baseline params, exact literal
  trial list, isolated ledger paths, ONE wall-clock stop, report format),
  keeps the mechanism queue deep enough that nobody grinds or idles, and
  re-plans dynamically from ledger tails. **The queue is never the stop
  signal:** it runs `TZ=Asia/Kolkata date` at every phase transition (start,
  each design round, before close-out) because estimated elapsed time drifts
  hours ahead of reality — Loop-15 began close-out 60 minutes into a
  120-minute brief and reported ~1 h early, the design pipeline having simply
  drained with nothing refilled. When the queue empties before the stop, the
  next action is a new design round (re-task the designers with fresh ledger
  tails, spawn another designer, or write the files yourself) — never
  close-out. It monitors via side-channel only
  (`ps`, ledger tails, `git status` — never interrupts), verifies claims
  against `best.json`/ledger, promotes winners to the main ledger as the
  single writer, owns commit + push, and reports to the user.
  **Wake on file events, never poll:** arm a background shell watcher (a
  `while` loop checking for a designer's smoke ledger or a new `strat_*.py`,
  with a deadline) so the session resumes the moment a file is delivered;
  never busy-wait on a subagent. A watcher's relative deadline is not wall
  time — the environment can suspend the whole session and freeze every
  process (Loop-16: a 20-minute watcher returned after ~90 minutes). Re-read
  `TZ=Asia/Kolkata date` whenever a watcher fires and re-plan the remaining
  budget from the real clock.
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
- **Designer (background subagent, strongest reasoning model) — owns IDEAS.**
  Runs on the strongest reasoning model in the session (standing preference:
  GLM 5.3 Flash at max effort; fall back to another strong model if it is
  unavailable). It reads the skill, the champion files and the LIVE ledger
  tails, then writes 2–3 new mechanism files per round (4–6 when the brief
  names a mechanism-count target) with documented SPACE variants,
  smoke-tests them on isolated ledgers, and reports each hypothesis, its
  falsification test, and the ideas it rejected. Every deliverable must carry
  a **novelty statement**: its closest prior art from the mechanism inventory
  and the one thing that changed (new signal, or a base it was never tested
  on). A file whose novelty statement is "same signal, new shape/weights" is
  rejected unread. It never runs trial
  campaigns, never edits existing files, never touches the main ledger.
  Designer files are namespaced by loop and designer:
  `strat_l<loop><designer>_<idea>.py` (e.g. `strat_l12b_printclose.py`), so
  parallel designers cannot collide.

### Mechanism inventory (the anti-repeat ledger)

Designers MUST read this before writing a file, and every deliverable must
name its closest prior art here plus the one thing that changed. A family
marked DEAD may only be retested when the base it was falsified on has
changed (say which base and why) — a new filename, shape, or weight on the
same signal is NOT a new mechanism and will be rejected at the novelty gate.

- **LIVE:** floor-lift fresh-print rank + tier-shape exposure + breadth tiers
  (the base chain); regime-conditional weak-month cap (`cap_weak`/`cap_full`);
  short hold clock (`max_hold 3`); eligibility-wobble discount (`gw_w 0.13 /
  gf_lb 12`).
- **DEAD** (falsified with champion-reproducing controls): breadth ramps;
  exposure hysteresis; rank smoothing/skip/blending/borda; positive
  persistence weights; sector/industry neutrality (80%-null `industry`);
  volume gates; vol targeting; index-DD veto; book-health/attrition floors;
  path exits and path-conditional hold clocks; retention bonus/grandfathered
  exits; trailing stops; band-conditional freshness; symmetric count caps
  (`cap_full` inert for values >= top); close-location tilt; drought-shape
  tilts; freshness/drought/CLV re-based onto the capped champion; the
  gate-failure share `gf_w`; top-13 DD repair via hold/cap levers.
- **DEAD (Loop-16, bit-exact off-switch identities, every active direction
  train-destructive):** the per-name daily-tape axis on the ids champion —
  continuous range compression re-based onto the ids chain (69.5–75.8 train),
  same-calendar-month seasonality (66.4–86.5), intramonth path shape /
  front-vs-back-loaded month (62.8–76.3), daily-return skewness (74.4–78.0),
  cross-sectional outrank percentile of own trailing return (84.8–94.4),
  volume-participation expansion/contraction vs the name's own baseline
  (58.0–81.5; binary volume gates were already dead — the continuous tilt is
  too). The ids term has saturated this channel: more tape re-ranking
  double-counts it.
  Also DEAD: the incumbency-protection family is now complete — retention
  bonus (L13), replacement budget (L15), boundary-conditional hurdle (L16,
  knife-edge: `hur_m` 0.005 flat / 0.0075–0.010 +0.4–0.6pp / 0.015+ below
  base, gain traced to ONE 2017-07 firing — AVANTIFEED reinstated over
  STARPAPER — that propagates into 3 H1 decision months; forward untouched).
- **PARTIAL:** negative persistence premium (live on the rankpersist line,
  dead on the conc chain); `cap_weak`/`max_hold`/`b_hi`/`regime_ma` are
  sharp peaks — their local neighbourhood is closed to tuning, but changing
  their *mechanism* is not.
- **OPEN AXES (start here — expressible under the current harness):** none
  open at the ids champion base — Loop-16 tested the last one (the replacement
  hurdle for incumbents) and it is now DEAD: +0.6pp train only at `hur_m 0.01`
  (no fire at 0.005, collapse at 0.015+), one 2017-07 firing propagating into
  3 H1 decision months, zero forward/DD effect. A new loop must bring a NEW signal or a changed base — not a re-shape
  of the tried ones (see DEAD/CLOSED).
- **CLOSED (Loop-14, off-switch identities bit-exact):** breadth
  *change*/derivative regime (one-sided harm; grows with the shift);
  volatility-scaled rank, positive side (harmful at `v_w 0.25`, DD worsens);
  recency-weighted wobble (every blend trails ~1pp — the flat share's long
  memory is part of the edge). **PARTIAL from Loop-14:** market-relative
  strength vs the panel mean — forward-positive, train-negative, and it
  STACKS with the forward geometry: `rs_w 0.2 / rs_lb 6` + `cap_full 15 /
  max_hold 6` → fwd +63.2% / −14.4% (forward-calmar 4.38 vs the champion's
  3.30; the geometry alone is 3.93). Train 68.9 cannot pass the cagr ratchet —
  it is the best forward-risk-adjusted line found, kept as a documented
  forward alternative, never promoted. Vol-tilt (negative `v_w`) does not
  stack with the geometry (fwd DD blows out to −24 to −25).
- **NOT expressible without a harness change (do not attempt in a
  candidate):** position sizing (the backtest equal-weights top-N); intraday
  or `60minute_kite_clean` inputs (`panels` carries month-end px + optional
  daily only); staggered/overlapping rebalances (single monthly book);
  market-cap conditioning (no cached cap snapshot; a live fetch inside
  `score()` is not reproducible).

### The round (standard playbook)

**Step 0 — ask the user about models before spawning anything.** Which model
for the DESIGNERS and which model for the TRIAL WORKERS. Sensible defaults to
offer: designers = the strongest reasoning model available in the session
(GLM 5.3 Flash at max effort was the standing choice), workers = the parent
session's model. Record the answers in every brief; never assume a model
silently. If the user settled the pairing in a previous loop and does not
re-answer (an aborted question counts as no answer — say so), or says "keep
going", reuse the standing pairing, state it explicitly in the briefs, and
proceed — never downgrade and never leave the loop unstarted waiting on a
question the user has already answered once.

A 1-hour loop = a 50-minute orchestrator budget; workers stop ~12 min before
it ends. The proven shape:

| Minute | Orchestrator | Designers | Trial workers |
| --- | --- | --- | --- |
| 0–5 | brief designers; start 2 workers on existing frontier lines | start | start |
| 5–20 | smoke-check delivered files; one screen worker per file | write + smoke 2–3 files | batched screens |
| 20–38 | supervise, dedupe, redeploy dead workers, re-plan | second round from live ledger tails | deepen winners only |
| 38–40 | stop trials | stop | stop |
| 40–50 | promote in ratchet order, nifty500 validation, commit, push, report | — | — |

Roles are decoupled: designers need ledger DATA, not free workers; the only
dependency is file-before-screen. Keep pool size = number of unscreened
files, and re-task a designer (with the live tails) before any worker idles.

**Longer loops repeat the round.** A 2–3 hour loop is the same shape scaled:
each designer delivers one file every ~20–30 minutes once warm; workers
screen each file within minutes of delivery; the orchestrator re-tasks
designers from live ledger tails at every round boundary. Stops scale with
the budget: designers stop ~30–40 min before the orchestrator's stop,
workers ~20 min before, and the last 15–20 min are the fixed close-out.
Three designers with distinct axes is the proven pool for a count target.

**Mechanism-count briefs.** When the brief names a target ("test at least N
mechanisms"), size the designer pool to cover it (3 designers × 4–6 files),
track every mechanism in a per-loop manifest (`.cache/l<loop>_manifest.tsv`:
file, axis, designer, delivered, screened, train range, verdict), and count
only files that pass the novelty gate AND whose off-switch identity
reproduced the champion exactly — a variant of an already-counted file does
not add to the count. Report the final count with per-file verdicts.

### Ledger isolation (mutual exclusion)

Concurrent `strategy_lab.py` processes must never share a ledger. Give every
worker its own pair and make it pass them in EVERY command:

    --results .cache/strategy_lab/w<ID>_results.tsv \
    --best-json .cache/strategy_lab/w<ID>_best.json

The main ledger (`.cache/strategy_lab/results.tsv` / `best.json`) stays
single-writer. With one worker running it may own the main ledger directly;
with several, nobody touches it until the orchestrator's promotion pass.
**Namespace every worker ledger by loop** — `w<loop>_<worker>_results.tsv` /
`w<loop>_<worker>_best.json` (e.g. `l12_wA_*`). Reusing a name across loops
mixes eras: Loop-12's worker B appended to a Loop-10 ledger and only escaped
stale-best verdicts because every new config dominated the old best. A stale
best that is *higher* than everything new would silently suppress every keep.
Split mixed-era files by timestamp before trusting their best column.
Promotion: after all workers stop, replay the winners onto the main ledger
one at a time, in ratchet order (each keep must sit within `--dd-slack` of
the standing best at that moment), then re-read `best.json` and compare with
what was written — if it changed underneath (a concurrent writer slipped in),
re-run instead of accepting a stale verdict. Do not submit knife-edge
candidates: a train gain that collapses within ±1% of a discretisation
parameter (Loop-12: `clv_scale` 0.66 / 0.67 / 0.675 → 83.85 / 85.43 / 84.37)
is a rank-ordering artifact, not a new best — record it in the worker's
ledger and the report, and leave the main ledger alone. For a book-composition
mechanism (one that changes the held book, not the score scale), also COUNT
THE FIRING EVENTS before promoting: replay the harness pick rule (a stateless
score diff is NOT a book diff) and count the months where the picks actually
differ. Loop-16's hurdle keep (+0.60pp train, DD and fwd identical) traced to
ONE firing event (2017-07) that propagates through the path-dependent held
set into 3 differing decision months out of 139; the orchestrator's first
stateless diff said "1 month / ADANIENSOL" and the independent audit's
harness-faithful replay corrected it — have the audit reproduce any
diagnostic before it enters the record. A gain sourced from a handful of
name-months is a sample of a handful, not an edge. `results_validate.tsv` /
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
5. Rate-limited models: retry ONCE at most, then switch models or report the
   outage. Loop-12's audit retry burned a second attempt on a persistently
   throttled free-tier model (three failures in one session) — the review was
   delivered on an available model instead, and the outage was reported.

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

### Throughput: screen then deepen (matching design pace)

Designers can produce a smoke-tested mechanism file every few minutes; a
worker that runs one trial per model turn cannot consume them fast enough and
the design queue becomes the workflow bottleneck. Two rules fix the pacing:

- **Batch the screen.** A worker's first pass over a new file runs the
  designer's documented SPACE variants as ONE bounded shell batch: one literal
  `python scripts/strategy_lab.py …` line per variant (full literal JSON,
  never shell-variable assembly), strictly sequential, all output appended to
  a log file, and a verification tail printing the TRAIN-line count (must
  equal the variant count) plus Traceback/FAILED counts before the last
  lines. A batch that prints no TRAIN per variant is a failed batch: read the
  log, never re-run blind. This lifts throughput from ~1–3 trials/min
  (one command per model turn) to ~8+ trials/min.
- **Screen shallow, deepen only winners.** Pass 1 = the documented variants
  (3–6 trials per file). Pass 2 = a deeper grid only for files whose screen
  beats or approaches the incumbent. Never grind a grid on a file that failed
  its screen.
- Keep the worker pool equal to the current design batch (one file per
  worker) so every artifact is screened within minutes of delivery.

### Briefing rules (the worker channel is one-shot)

A background worker cannot be re-briefed mid-flight, so its brief carries the
whole round: baseline command, exact literal trial list, rotation/fallback
rule, ledger paths, stop time, report format. Hard-won rules:

- One trial per command LINE, never two at once; batches are allowed only as a
  written script of full literal command lines with a verification tail (see
  Throughput) — never a shell loop that assembles JSON. Never suppress stderr
  and never grep-filter the command output; a trial printing no TRAIN line is
  FAILED — stop, read the raw error, never re-run blind. (This applies to the
  orchestrator's own probe commands too.)
- Trials are strictly SEQUENTIAL, one process at a time per ledger. Never issue
  parallel tool calls that run `strategy_lab.py` against the same
  `--results`/`--best-json` pair: concurrent runs can lose a keep in a
  best.json read-modify-write race. Loop-11 caught a worker running five
  trials at once on one ledger; the rows survived (atomic appends at this
  line size) but the ledger best could silently lag. If parallel trials are
  wanted, give each process its own ledger pair and merge afterwards.
- Orchestrator smoke duty before a handoff: run the new file's FLAT/no-op
  config (its keys at zero, or its defaults) and compare it to the intended
  parent. If the flat base does not equal the champion, the brief must set the
  file's OWN base as the comparison target and must pass only keys the file
  actually reads. Loop-12: a brief told a worker to beat +83.93 on a file whose
  true base was +77.32 (it composed tiershape+fastgate+sustaincond, not
  rankpersist) and to sweep `pers_*` keys the file never consumed — the worker
  caught both, but part of its window was wasted. Designer deliverables must
  therefore state their import chain, their flat-base metric, and the exact
  keys they consume. **Designer files must compose the CURRENT champion chain**
  (state it explicitly in the brief: file + params + top), not a historical
  base — Loop-12's designer files were built on the Loop-10 `tiershape` chain
  while the champion had moved to `tiershape + cap_weak + max_hold 3`, so two
  mechanisms were screened against a superseded base and their falsifications
  are scoped to it. Re-base surviving terms onto the champion chain before
  believing a negative.
- State the run convention in every brief: candidate, `--top`, `--universe
  nse_all`, `--cost-bps 25`, the full params JSON, and the isolated ledger paths.
  A wrong universe silently produces rows incomparable to the champion —
  Loop-13: a worker's first batch ran nifty500 by its own choice and had to be
  rerun before any number meant anything. Ledgers are also blind to `--start`:
  best.json stores candidate+params+top+metrics but no window, so a
  `--start 2017` row can overwrite a full-window best in an isolated ledger
  (Loop-15 worker B) — run window variants on a throwaway ledger or check the
  `months` field before trusting a worker-ledger best. They are blind to
  `--cost-bps` too: three rows with identical params in one ledger are the
  25/50/100bps runs, not divergent source states (Loop-15 audit).
- Imported defaults leak into re-based files: when a mechanism file composes a
  term from an existing file, the source file's internal defaults activate
  unless overridden (Loop-13: gatefail's `gf_w=0.05`, printclose's
  `clv_scale=0.8` both broke the off-switch until the designer set its own
  neutral defaults). The designer must set neutral defaults first, and the
  worker's first row must be the off-switch identity check.
- **Novelty gate before a screen:** read the designer's file and check its
  signal against the mechanism inventory. If the family is DEAD and the base
  it was falsified on is unchanged, reject the file and re-task the designer
  with an OPEN axis — never spend a worker window on a known replay. A
  legitimate retest (changed base) is allowed but the worker brief must say
  which base changed.
- **Assign the two designers DISTINCT axes** — never the same family from two
  pens. Loop-12's four designer files all modulated the freshness/eligibility
  channel, which bought parameter breadth but no mechanism breadth; Loop-13's
  screens confirmed they were substitutes.
- Dedupe before a batch: grep the ledger for the candidate name and param
  signature and skip any (candidate, params) row that already exists —
  identical reruns are noise, not evidence. A retest is legitimate only on a
  changed base mechanism (new exposure shape, new book composition), and the
  brief should say which base changed and why.
- New mechanisms go into NEW files; never edit an existing `strat_*` file to
  change its meaning, or past ledger rows stop meaning what they meant.
- FREEZE delivered files. Once a designer file is handed to a trial worker it
  must not be renamed, edited, or "evolved" — a new idea gets a NEW file.
  Loop-12: a designer renamed its own delivered file mid-run
  (`strat_l12a_pathexit.py` → `strat_l12a_pathhold.py`), breaking the worker's
  candidate import and wasting the rest of its window. If a candidate file
  disappears mid-run, that worker stops its line and reports; it never
  silently switches to a different file. The orchestrator also watches for
  parallel sessions/external writers (`git status`, the scripts directory)
  before close-out. Designers do edit their own delivered files mid-loop
  (Loop-16: seasmom and monpath changed while a screen was running; Loop-17:
  crowd was fixed after its first smoke). Record each file's md5 at handoff;
  a screen that spans an edit is mixed-version — re-run the affected cells on
  the frozen final hash before trusting the verdict, or clear a doc-only edit
  by re-running one cell and matching the recorded number (Loop-16 seasmom
  re-check: identical).
- **Identity failure on delivery.** The orchestrator's smoke duty is to run
  each delivered file's off-switch BEFORE handing it to a worker. If it does
  not reproduce the champion bit-exactly, do not screen it on the champion
  target: either (a) it composes a legitimately different base — then the
  brief sets the file's OWN base as the comparison target and says which base
  changed, or (b) the composition is broken — hold the file, and either fix
  the composition yourself (and record that you did) or return it to the
  designer via post-loop session continuation. Loop-17:
  `strat_l17b_crowd.py` silently omitted the live ids term and its off-switch
  read 87.00/-17.34 = exactly champion-minus-ids; caught before any worker
  window was spent.
- Report format: stop-time confirmation, trial count, every KEEP, the full
  `w<ID>_best.json`, a compact trial table, raw errors for any failure.

**"Run the loop for N minutes" means:** the orchestrator runs its own clock
(N = 50 min default; workers get stops well inside it), designs and feeds new
mechanisms round by round, and closes out — promotion, validation, commit,
push, report — inside its own budget. Close-out is a FIXED window: the last
15–20 minutes before the stop, never the reward for finishing the checklist.
A loop whose queue empties at minute 60 of 120 keeps designing and screening
for another 45 minutes; if the orchestrator's last fresh trials are ~1 h old
at the cutoff, the loop ended early (Loop-15: closed out 60 min into a
120-min brief — see AGENTS.md LESSONS). If workers are still running at the
orchestrator's cutoff, that is a planning error to avoid next loop (brief
worker stops early enough to leave 10+ min for close-out); it is not a reason
to wait for them.

### Close-out (the fixed window — a checklist, not just a commit)

1. **Promotion.** Replay the winners onto the main ledger in ratchet order
   (see Ledger isolation), re-read `best.json`, and if nothing beat the
   champion, say so and leave the main ledger alone. A no-promotion loop
   still closes out — the negatives are the finding.
2. **Validation.** Run the promoted config (or the standing champion, if
   nothing changed) on the un-fitted universe and write
   `results_validate.tsv` / `best_validate.json`.
3. **Independent audit.** Spawn a clean-room audit on a DIFFERENT model from
   the trial workers, with a stop inside the window: re-run the promoted row
   (or the headline claims plus one dead-line control when nothing promoted)
   and reproduce any diagnostic the record will cite (book diffs, firing
   counts). Loop-16's audit re-ran the champion identity and the single keep
   to the printed precision AND corrected the orchestrator's stateless
   book-diff (1 month / ADANIENSOL → 3 months / AVANTIFEED); without it the
   wrong characterization would have shipped.
4. **Write the outcome down.** A row in the README's results ledger (setup,
   window, universe, costs, CAGR + DD + calmar for train and forward against
   the bench, verdict); the mechanism file(s); any new measurement rule into
   AGENTS.md LESSONS; any new closure into the mechanism inventory above.
5. **Update this skill's bootstrap state.** Append/replace a "State at
   Loop-N close" paragraph (champion + params + metrics, closures, artifact
   verdicts, operational notes). This is the loop's handoff artifact — the
   next fresh session resumes from git, not from a stale paragraph.
6. **Commit + push** on the workstream branch (`git add -f` the tracked
   ledgers if `.cache` is ignored), then report: train and forward CAGR/DD/
   calmar for strategy and bench, costs, the mechanism count when one was
   briefed, and the honest caveats.

## Fresh-session bootstrap

1. Read this skill end-to-end first — the loop assumes the playbook above.
2. `git log --oneline -5`, `git status --short` — find the workstream branch
   and check for external/parallel changes.
3. Read the tracked ledgers: `.cache/strategy_lab/best.json` (main, nse_all),
   `best_validate.json` (nifty500), `.cache/auto_research/best*.json`, plus the
   tails of the results files for the frontier and the dead lines. `best.json`
   alone is enough to resume.
4. State at Loop-15 close (re-verify, do not trust): champion
   `strat_l15b_insideday` (gw_w 0.15 / ids_lb 3 / ids_w -0.13), top 15 — the
   `strat_l13a_concwobble` chain (floor-lift fresh-print rank + gates +
   weak-month cap 11/20 + max_hold 3) carrying the inside-day pause-share tilt
   applied pre-cap and a retuned wobble → train +96.88% / DD -17.03% /
   calmar 5.69, fwd +48.97% / -12.31%, full DD -27.11%; beats the L13 chain on
   CAGR (+8.7pp), DD (0.3pp) and calmar (5.69 vs 5.08). Promoted three times in
   one loop (-0.15, then -0.13 at gw 0.13, then gw 0.15). Both axes are
   plateaus, not spikes: ids_w -0.10..-0.18 → 91.7-94.6 at gw 0.13; gw_w
   0.10..0.20 → 94.3-96.9 at ids -0.13 (0.15/0.16 tie the peak). Documented
   frontier siblings: balanced gw 0.13/ids -0.13 (94.58/-18.86/5.01, fwd
   +54.40/-12.31), risk-lean ids -0.15/gw 0.13 (93.43/-17.03/5.49, fwd
   +52.91), forward-lean gw 0.00/ids -0.25 (89.33/-18.55/4.81, fwd
   +62.17/-13.92). Cost slopes: 50bps 94.58/5.52 (fwd +47.16), 100bps
   90.04/5.00 (fwd +43.58). Diagnostics: inside-day coverage ~100%, turnover
   unchanged vs base (5.0 replacements/month). Independent audit (L15):
   reproducible to the printed precision, PIT-clean, independent inside-day
   recomputation exact; the +9.9pp train lift is entirely the ids term (gw 0.15
   alone = 87.00/-17.34) and is train-side only (fwd 48.97 vs 49.29 untilted);
   ids_lb 3 is load-bearing (lb 6 -> 86.44/-21.80). NOTE the file's docstring
   hypothesis is inverted vs its code — the tested/winning direction rewards
   FEWER inside days (expanding tape), not the coil story. Caveats: the train-DD
   edge over the L13 chain flips at other splits (2020/2021 starts: +10.5-10.7pp
   train but DD 1.5pp worse) and nothing transfers to index universes (Nifty 500
   +35.91/-25.09, fwd DD -28.98 worse than bench). Forward frontier:
   geometry+rngcomp (6,-0.4) fwd +63.71/-11.61 (fwd-calmar 5.49) at train +73.97;
   geometry+rs fwd +63.18/-14.44; rs+ids on the geometry adds on returns (fwd
   +68.03/-15.97) but not on fwd-calmar. Loop-15 closures: overnight-vs-intraday
   (dead at both bases), up-streak (dead), replacement budget/fill (dominated),
   rank-band pick buffer, weak-month cap grandfather (risk-efficient only:
   85.5-86.1 train at -16.05 DD, calmar 5.33-5.37 — documented, not
   ratchet-eligible), dualshield and ids×grandfather stacks (sub-additive: one
   book-composition channel, not two — ids(-0.15)+grand(4) reads 86.34/-19.26/
   4.48, worse than either single), positive inside-day direction, pers re-based
   onto the wobble chain, serial-dependence (sign-persistence) tilt (dead on
   train; its choppy arm is the best forward print on the champion base, fwd
   +69.55/-16.13 at train +72.65/-24.49). Dead lines (carried from L14): ramps, hysteresis, positive
   persistence, freshness/drought/CLV re-based onto the capped champion, rank
   smoothing/skip/blending, sector (80%-null industry), volume gates, vol
   targeting, index-DD veto, book-health floors, path exits, retention bonus,
   top-13 DD repair.
   State at Loop-16 close (2026-09-21): champion UNCHANGED — nothing promoted.
   Seven families screened on the champion base, every active direction
   train-destructive with bit-exact off-switch identities: range compression
   re-based onto the ids chain (69.5–75.8), seasonal momentum (66.4–86.5),
   intramonth path shape (62.8–76.3), daily skewness (74.4–78.0),
   cross-sectional outrank (84.8–94.4), volume participation (58.0–81.5),
   incumbency hurdle (96.1–97.5; the single
   KEEP at `hur_m 0.01 / hur_n 2` reads +97.48/-17.03/calmar 5.72, h1 +99.5,
   h2 +95.5, fwd identical — NOT promoted: narrow `hur_m` window, one 2017-07
   firing (AVANTIFEED reinstated over STARPAPER) propagating into 3 H1 decision
   months, no forward/DD effect; the orchestrator's first diagnostic mis-read it
   as a single ADANIENSOL swap and the independent audit's harness-validated
   replay (1e-9) corrected it). Conclusions: the
   per-name daily-tape axis is saturated by the ids term; the incumbency family
   (bonus/budget/hurdle) is fully dead; the next loop needs a NEW channel, not
   another tape re-ranking. Operational: the session/VM can be suspended
   mid-loop (L16: a 20-min watcher returned after ~90 min of wall time, all
   processes and the clock frozen together) — re-read `TZ=Asia/Kolkata date`
   whenever a watcher fires and re-plan the remaining budget from the real
   clock, never from an elapsed-time estimate.
5. Ask the user for the designer and worker models (Step 0 of the playbook),
   then open the round. At close: commit with setup + verdict, `git add -f` the
   tracked ledgers if `.cache` is ignored, and push the workstream branch — the
   next fresh session must find the latest best on git, never restart.
