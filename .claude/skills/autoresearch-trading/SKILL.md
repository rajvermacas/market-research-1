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

## Fresh-session bootstrap

1. `git log --oneline -5`, `git status --short` — find the workstream branch.
2. Read `.cache/auto_research/best*.json` and `results*.tsv` tails for current best.
3. Read `.cache/strategy_lab/results.tsv` for mechanism history.
4. Continue the loop from current best; commit new `strat_*`/harness files with
   messages stating setup + verdict.
