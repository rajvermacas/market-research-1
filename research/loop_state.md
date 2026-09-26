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

## Current state (Loop-23 close, 2026-09-26 14:30 IST)

- **Champion** (`.cache/strategy_lab/champion_real.json`): `strat_floorhighfresh`, top 25,
  `{"b_hi": 0.65, "b_lo": 0.45, "b_mid": 0.55, "floor_lb": 19, "lookback": 16, "max_dist": 0.055, "regime_ma": 18}`.
  Train +24.13% / DD −18.98% (calmar 1.27, robust 1.059, noise sd ~0.08) vs bench +19.84%;
  forward +20.63% / DD −21.65% (calmar 0.95) vs bench +14.53% / −27.88%. Nifty 500
  transfer +29.7% / −14.1% train vs bench +21.1%. Gate report:
  `research/promotions/2026-09-26T083708Z_strat_floorhighfresh.json`.
- **To dethrone it** (gate check 9): train CAGR > 24.13% AND train DD ≥ −18.98% AND
  forward CAGR > 20.63% AND forward DD ≥ −21.65%, plus checks 1–8.
- **Harness**: `strategy_lab.py --exec realistic` (next-open fill, circuit-lock block,
  ₹50 lakh liquidity floor, 50 bps, robust fold ruler, noise margin, blind forward).
  Legacy ledgers (`results.tsv` / `best.json`) are an upper bound only.
- **Reveals used**: 5 (`.cache/strategy_lab/reveals.tsv`). Each gate run spends one.
- **Trials under the current scoring**: 120 across all realistic ledgers (the gate's
  deflation counts them all).
- **Loop counter**: last loop = 23. Next loop = 24.

## Lead queue (highest first)

1. **Liquid-cohort regime + a forward-positive rank channel.** Both regime candidates
   (`strat_l23a_liqconfirm` fwd 20.41/−19.23; `strat_l23o_liqramp` fwd 19.15/−19.06) beat
   the champion's forward DD (−21.65) but give up 0.2–1.5pp of forward CAGR, so they fail
   dominance alone. Pair the regime with a rank channel whose gain is NOT the
   V-recovery axis (lead 2), and screen it blind before spending a reveal. liqramp
   hi 0.65 (27.46/−16.75 train) is ungated.
2. **Rank channels that are NOT the "less-extended / V-recovery" axis.** ddquality,
   trmom(−) and their compositions all lift train and lose forward — treat that axis as
   a train artifact on this base (DEAD for promotion purposes unless the base changes).
3. **gapdrift** (held high-volume gap-up): PARTIAL, about 1 noise sd over its placebo.
   Worth one more design (stronger event definition), not a gate run yet.
4. Untested on the realistic base: position sizing / portfolio DD stop (needs a harness
   change), a top-N sweep (15/20/30/40) of the champion, and the one-month-stale daily
   feature convention (using month t's bars is PIT-legal but needs its own stamp).
5. Data backlog: NSE bhavcopy (survivorship) — every result here is inflated by it.

## Loop log

- L22 (2026-09-26, 10 min): first realistic loop; 5 execution-aware tilts, none kept.
- L23 (2026-09-26, 40 min): harness v2 (blind/robust/noise/gate); 8 mechanisms,
  126 trials; 4 candidates gated (ddquality, liqconfirm, liqdq, liqramp), all failed
  forward dominance; champion unchanged. Gate fixes: deflation counts every ledger;
  footprint counts exposure changes.
