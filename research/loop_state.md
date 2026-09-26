# Research loop state — READ THIS FIRST in a new session

This file is the handoff between research loops. A fresh session resumes from it
and from the committed ledgers below; it never restarts from scratch. The
orchestrator rewrites the "Current state" and "Lead queue" sections at every loop
close-out and commits them with the ledgers.

**Workstream branch: `claude-routine`** — every loop (interactive or the scheduled night/morning
routines) checks it out, commits to it and pushes to it; never to another branch.

## Goal

Find an un-researched mechanism that beats the standing champion on **both CAGR
and max drawdown** (train AND forward), under realistic execution, and crown it
through `scripts/promote_gate.py`. Nothing else crowns a champion.

## Protocol (the loop, in one screen)

1. `TZ=Asia/Kolkata date` — set ONE wall-clock stop for the loop.
2. Read `.cache/strategy_lab/champion_real.json` (the champion, its params and
   its revealed forward numbers) and the tail of `.cache/strategy_lab/results_real.tsv`.
3. Pick an idea from the lead queue or design a new one — **never repeat a tested
   strategy** (the skill's MANDATORY no-repeat section): grep
   `research/tested_mechanisms.tsv` by signal/family words (a tested family is only
   retested on a changed base), grep `.cache/strategy_lab/*results*.tsv` for the exact
   candidate + params before every trial, and check `research/promotions/` before any
   gate. New file = `scripts/strat_l<loop><designer>_<idea>.py`, composing
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

## Current state (Loop-27 close, 2026-09-26 23:43 IST — champion unchanged since L25)

- **Champion** (`.cache/strategy_lab/champion_real.json`, crowned L25): `strat_l23a_liqconfirm`,
  full board (`nse_all`), `--top 25`, params
  `{"b_hi": 0.65, "b_lo": 0.45, "b_mid": 0.55, "floor_lb": 19, "lookback": 16, "max_dist": 0.055, "regime_ma": 18, "lq_min": 5e6, "lq_days": 40, "lq_shift": 0.05, "lq_shift_hi": 0.05, "lq_shift_lo": 0.075, "lq_mode": "strict", "top": 25, "weighting": "invvol"}`.
  Train +30.09% / DD −17.22% (calmar 1.75, robust 2.121, noise sd ~0.16) vs bench +19.84%;
  forward +21.58% / DD −20.47% (calmar 1.05) vs bench +14.53% / −27.88%. Nifty 500 transfer
  +28.4% / −12.1% vs bench +21.1%. Gate report:
  `research/promotions/2026-09-26T101152Z_strat_l23a_liqconfirm.json`.
- **Previous champion**: `strat_floorhighfresh` top 25 equal (train 24.13/−18.98, fwd 20.63/−21.65).
- **To dethrone it** (gate check 9 `tradeoff`, user rule), on train AND forward separately:
  dominate (CAGR higher, DD no deeper), or gain ≥ +2pp CAGR with DD at most
  min(0.5 × gain, 5pp) deeper. Train: > 30.09% / −17.22%. Forward: > 21.58% / −20.47%
  (or ≥ 23.58% with a bounded dent). Plus checks 1–8 (forward DD must also beat the bench's).
- **Universe is open**: full board or Nifty 500 (`--universe nifty500`, own ledger; gate with
  `--universe nifty500`).
- **Harness**: realistic execution + robust fold ruler + noise margin + blind forward;
  policy keys searchable (`top`, `weighting`, `max_weight`, `min_hold`, `max_hold`, `sl_pct`,
  `ts_pct`, `stop_cool`). Pass `--top 25` on the CLI; set the book size with the `top` key.
- **Reveals used**: 13 (L27 spent #12 on strat_l27b_spread, #13 on strat_l27a_froth). **Trials under the current scoring**: ~300 across realistic ledgers.
- **Loop counter**: last loop = 27. Next loop = 28.

## Lead queue (highest first)

00. **Loop-27 outcome — a crown was REVOKED.** `strat_l27a_froth` (illiquid-tail minus liquid-core
   2-month return > .06 -> exposure x 0.6) passed all 9 gate checks (train 30.21/−14.09, fwd
   23.44/−14.44) and was crowned, then the audit found the designer chose the sign after a
   diagnostic that printed the Jan-2022 rel spike — a FORWARD-window value — and the 2022-01 /
   2024-01 firings carry the forward DD gain. The L25 champion was restored by hand from git
   (commit 21b710a); the gate report stays in `research/promotions/`. If the owner judges the
   contamination tolerable, re-crown with
   `python scripts/promote_gate.py --crown research/promotions/2026-09-26T173406Z_strat_l27a_froth.json`.
   Otherwise froth can only be confirmed on forward data after 2026-09. Its train DD gain is the
   2016-10/11 firings alone (demonetisation); the 2020-21 firings cost 2.6pp train CAGR.
01. **Illiquidity rank premium is train-side.** CS spread (wide sign) gated: train 35.19/−15.84 but
   fwd 18.35/−17.24 (−3.23pp CAGR) — the third rank tilt (after ddquality, breakmag) that buys train
   CAGR and loses forward CAGR. Amihud (35.11/−16.22) is the same axis; do not gate it on this
   evidence. Rank tilts on the 25-name book look exhausted for forward CAGR; exposure-side work
   (with strictly pre-2022 diagnostics) is where the forward DD improvements have come from.

0. **Loop-26 outcome** (no promotion): breakout magnitude (`strat_l26b_breakmag`, bm_w .2 /
   bm_lb 9) is the best forward-DD line found — fwd 18.25/−14.32, calmar 1.27 vs the champion's
   1.05 — but −3.3pp forward CAGR fails the CAGR-first rule. If the user ever weights DD more,
   it is the ready alternative. Nifty 500 DD controls (corrspike, xuniconfirm) are dead; the
   Nifty 500 book's forward DD gap (−25.7 vs −20.5) is still open.
1. **Nifty 500 with a drawdown control**: the Nifty 500 regime_ma-24 cell has the forward
   CAGR (22.8%) but a −25.7% forward DD (worse than its bench). A regime or exposure rule that
   cuts that DD could make it pass the trade-off. Its ledger: `.cache/strategy_lab/l25_dA_results.tsv`.
2. **Book size is CLOSED at 25 names**: 20–24 is a train plateau (32–33%) but the gated
   top-22 cell read fwd 20.65/−18.74 (−0.94pp CAGR vs the champion) — the fourth gate where
   a more concentrated book lost forward CAGR.
3. Rank channels that are NOT the V-recovery axis (ddquality/trmom lost forward; gapdrift on
   the new champion lowers train CAGR).
4. Stops are dead on the fresh-print book; concentration below 20 names is a train artifact.
5. Data backlog: NSE bhavcopy (survivorship) — every result here is inflated by it.

## Loop log

- L27 (2026-09-26 22:43–23:43 IST, 60 min, routine test fire): 3 designers + 1 short round, ~14 mechanisms,
  ~130 trials; 2 gated: CS spread (fails fwd CAGR −3.23pp) and froth (passes all checks — crown REVOKED
  for forward contamination, see lead 00); champion unchanged.

- L22 (2026-09-26, 10 min): first realistic loop; 5 execution-aware tilts, none kept.
- L23 (2026-09-26, 40 min): harness v2 (blind/robust/noise/gate); 8 mechanisms,
  126 trials; 4 candidates gated (ddquality, liqconfirm, liqdq, liqramp), all failed
  forward dominance; champion unchanged. Gate fixes: deflation counts every ledger;
  footprint counts exposure changes.
- L24 (2026-09-26, 30 min): risk policy moved into training (book size, weights,
  holds, daily-path stops); 33 trials; 2 gated (top-15 inverse-vol on the champion and on
  liqconfirm), both lost forward CAGR; stops dead; champion unchanged.
- L25 (2026-09-26, 30 min): **NEW CHAMPION** liqconfirm + top 25 inverse-vol (fwd
  21.58/−20.47 vs 20.63/−21.65; train 30.09/−17.22); Nifty 500 searched (84 trials; best cell
  gated, fwd 22.82/−25.65 fails the trade-off); gap-drift dead on the new base; top-22 book
  gated, fwd 20.65/−18.74 fails; 4 gates, 1 pass.
- L26 (2026-09-26, 30 min): 4 mechanisms (2 Nifty 500 DD controls, 2 rank tilts), 43 trials,
  1 gated (breakout magnitude: fwd 18.25/−14.32, −3.3pp CAGR, fails); champion unchanged.
