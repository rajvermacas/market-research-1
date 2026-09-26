# Research loop state — READ THIS FIRST in a new session

This file is the handoff between research loops. A fresh session resumes from it
and from the committed ledgers below; it never restarts from scratch. The
orchestrator rewrites the "Current state" and "Lead queue" sections at every loop
close-out and commits them with the ledgers.

## Goal

Find an un-researched mechanism that beats the standing champion on **both CAGR
and max drawdown** (train AND forward), under realistic execution, and crown it
through `scripts/promote_gate.py`. Nothing else crowns a champion.

## Protocol (the loop, in one screen)

1. `TZ=Asia/Kolkata date` — set ONE wall-clock stop for the loop.
2. Read `.cache/strategy_lab/champion_real.json` (the champion, its params and
   its revealed forward numbers) and the tail of `.cache/strategy_lab/results_real.tsv`.
3. Pick an idea from the lead queue or design a new one. Grep
   `research/tested_mechanisms.tsv` first; a DEAD family is only retested on a
   changed base. New file = `scripts/strat_l<loop><designer>_<idea>.py`, composing
   the champion by import, with an off-switch that reproduces it exactly.
4. Screen on the blind realistic ledger (defaults — never override the profile
   inside the main ledger; isolated `--results/--best-json` per parallel worker):
   `python scripts/strategy_lab.py --candidate <file> --params-json '<full json>' --universe nse_all --top <champion top>`
   Trials print train, folds and noise only; forward stays blind. ~4 s per trial
   for a light candidate (panels are cached under `.cache/strategy_lab/panels/`).
5. A KEEP (robust ruler beats the ledger best by more than the trial's own noise,
   train CAGR above bench, DD within slack, both halves positive) is a
   *candidate*. Gate it:
   `python scripts/promote_gate.py --candidate <file> --params-json '<json>' --top <n>`
   The gate reveals forward once (logged in `.cache/strategy_lab/reveals.tsv`).
   If it prints ALL CHECKS PASS: `python scripts/promote_gate.py --crown research/promotions/<report>.json`.
6. Close-out: append every mechanism to `research/tested_mechanisms.tsv`, add a
   README results-ledger row, rewrite the two sections below, `git add -f` the
   ledgers, commit, push.

## Current state (Loop-24 close, 2026-09-26 15:00 IST)

- **Champion** (`.cache/strategy_lab/champion_real.json`): `strat_floorhighfresh`, top 25,
  equal weight, no stops,
  `{"b_hi": 0.65, "b_lo": 0.45, "b_mid": 0.55, "floor_lb": 19, "lookback": 16, "max_dist": 0.055, "regime_ma": 18}`.
  Train +24.13% / DD −18.98% (calmar 1.27, robust 1.059) vs bench +19.84%;
  forward +20.63% / DD −21.65% (calmar 0.95) vs bench +14.53% / −27.88%.
- **To dethrone it** (gate check 9): train CAGR > 24.13% AND train DD ≥ −18.98% AND
  forward CAGR > 20.63% AND forward DD ≥ −21.65%, plus checks 1–8.
- **Harness**: realistic execution + robust fold ruler + noise margin + blind forward.
  **Policy is searchable** (params-json keys): `top`, `weighting` (equal/rank/invvol),
  `max_weight`, `min_hold`, `max_hold`, `sl_pct`, `ts_pct`, `stop_cool`. Pass `--top 25`
  on the CLI (the ledger stamp) and set the book size with the `top` key.
- **Reveals used**: 7 (`.cache/strategy_lab/reveals.tsv`). Each gate run spends one —
  gate only candidates whose train neighbourhood is already measured.
- **Trials under the current scoring**: ~170 across all realistic ledgers.
- **Loop counter**: last loop = 24. Next loop = 25.

## Lead queue (highest first)

1. **Gate `strat_l23a_liqconfirm` + top 25 inverse-vol** (ungated; neighbourhood already
   measured in `.cache/strategy_lab/l24_pol_results.tsv`: train 30.09/−17.22, every
   neighbour 26.8–33.4 at DD −16.8…−18.4). It keeps the 25-name breadth that held
   forward CAGR in every gate so far, and the liqconfirm regime that improved forward DD.
   params: champion keys + `"lq_min": 5e6, "lq_days": 40, "lq_shift": 0.05,
   "lq_shift_hi": 0.05, "lq_shift_lo": 0.075, "lq_mode": "strict", "top": 25,
   "weighting": "invvol"`.
2. **Concentration is a train artifact on this base**: 12–15-name books lifted train by
   6–10pp and lost ~4.5pp of forward CAGR in both gates. Keep new mechanisms at the
   champion's breadth (25) unless the base changes.
3. **Stops are dead** on the fresh-print book (every sl/ts level lowers CAGR without
   improving DD). Do not re-run without a changed base.
4. Rank channels that are NOT the V-recovery axis (ddquality/trmom lost forward).
5. gapdrift (held high-volume gap-up) — PARTIAL, needs a stronger event definition.
6. Data backlog: NSE bhavcopy (survivorship) — every result here is inflated by it.

## Loop log

- L22 (2026-09-26, 10 min): first realistic loop; 5 execution-aware tilts, none kept.
- L23 (2026-09-26, 40 min): harness v2 (blind/robust/noise/gate); 8 mechanisms,
  126 trials; 4 candidates gated (ddquality, liqconfirm, liqdq, liqramp), all failed
  forward dominance; champion unchanged. Gate fixes: deflation counts every ledger;
  footprint counts exposure changes.
- L24 (2026-09-26, 30 min): risk policy moved into training (book size, weights,
  holds, daily-path stops); 33 trials; 2 gated (top-15 inverse-vol on the champion and on
  liqconfirm), both lost forward CAGR; stops dead; champion unchanged.
