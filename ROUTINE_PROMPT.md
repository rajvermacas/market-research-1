# Scheduled autoresearch loop — routine instructions

This file is the authoritative instruction set for the scheduled research-loop
routines (night ~01:50 IST, morning ~06:48 IST). The routine's own prompt only
points here. Run ONE autonomous strategy-research loop for exactly 60 minutes of
wall-clock time, then close out, commit and push. The run is unattended — no
human will answer questions; use the standing choices below.

## Repo and branch (mandatory)

Repository `rajvermacas/market-research-1`, branch **`claude-routine`** only.

    git fetch origin claude-routine && git checkout claude-routine && git pull --ff-only origin claude-routine

Never push to another branch, never force-push, never open a pull request. If the
repository is missing or push access fails, report the blocker in the final
message and stop.

## Models (mandatory)

- Orchestrator (this session): Claude Opus 5.5 (`claude-opus-5-5`) at medium
  effort — pinned in `.claude/settings.json`.
- Every designer / worker subagent: Agent tool with
  `subagent_type: "autoresearch-designer"` (Opus 5.5, effort medium, defined in
  `.claude/agents/autoresearch-designer.md`) and NO `model` override.

## Clock

Run `TZ=Asia/Kolkata date` first; STOP = start + 60 min (IST). Close-out is a
fixed window in the last 15 minutes. Keep generating fresh trials until then — an
empty queue is never a stop signal. Re-read the clock at every phase transition.
Kill orphan `strategy_lab` processes (`ps -eo pid,ppid,cmd | grep strategy_lab`)
before launching anything.

## Procedure

Invoke the `autoresearch-trading` skill and follow it, especially its MANDATORY
sections:

1. Resume from `research/loop_state.md` (champion, dethrone thresholds, reveal
   count, lead queue, loop counter — this run is the next loop number) and
   `.cache/strategy_lab/champion_real.json`.
2. Never repeat a tested strategy: grep `research/tested_mechanisms.tsv` by idea,
   grep `.cache/strategy_lab/*results*.tsv` for exact candidate + params before
   every trial, check `research/promotions/` before any gate.
3. Staffing (do not ask): 2 `autoresearch-designer` subagents on distinct axes
   (their stop = STOP − 17 min); trials on isolated ledgers
   `.cache/strategy_lab/l<loop>_<name>_results.tsv`; realistic harness defaults;
   forward blind (never `--reveal` in trials).
4. Promotion only via `python scripts/promote_gate.py` (one forward reveal each —
   gate at most 2 candidates per run, only ones with a measured train
   neighbourhood); crown a passing report with `--crown`. Rule: on train AND
   forward, dominate the champion, or gain >= +2pp CAGR with max DD at most
   min(0.5 x gain, 5pp) deeper; universe `nse_all` or `nifty500`.

## Commit and push (mandatory)

Checkpoint commits mid-loop whenever state accumulates, immediately after any
crown and after every gate run, and at close-out: new strat files, `git add -f`
the `.cache/strategy_lab/` ledgers / reveals / champion file, gate reports,
registry rows in `research/tested_mechanisms.tsv`, a README results-ledger row,
and the rewritten state / lead / loop-log sections of `research/loop_state.md`.

    git push -u origin claude-routine

Retry up to 4 times with 2/4/8/16 s backoff on network errors, then VERIFY after
a fetch that `git rev-parse HEAD` equals `git rev-parse origin/claude-routine`.

## Final message

Loop number, start/stop IST, models actually used, mechanisms and trial count,
each gated candidate with train and forward CAGR / max DD / calmar vs the
champion and bench, whether the champion changed, reveals used, and the pushed
commit hash.
