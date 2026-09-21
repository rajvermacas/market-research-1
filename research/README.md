# Tested-mechanism registry (persistent, committed)

`tested_mechanisms.tsv` is the exhaustive anti-repeat record for this repo's
strategy research. One row per `scripts/strat_*.py` file ever written.

**Why it exists:** the research runs across days and sessions. The harness
ledgers (`.cache/strategy_lab/*`) are scratch and gitignored; the per-loop
manifests (`.cache/l<N>_manifest.tsv`) die with the loop. Without this file a
fresh session cannot tell which signals have already been tested and would
re-design dead mechanisms.

## Columns

- `file` — the mechanism file in `scripts/`
- `era` — `legacy` (pre-loop), `l12` … `l17` (loop number)
- `family` — the signal family the file belongs to
- `status` — `PROMOTED` (in the live champion chain) · `LIVE` (chain
  component) · `KEEP-not-promoted` (passed the harness keep rule but not
  promoted) · `PARTIAL` · `DEAD` · `SUPERSEDED` (ancestor of the live chain
  or a pre-loop family) · `SCREENING` / `PENDING SCREEN` (loop in flight)
- `key_numbers` — train CAGR / DD / calmar where recorded
- `note` — closest prior art and why the verdict

## How it is maintained

- **Before writing a mechanism**, a designer greps this file (by family and
  by signal name) and cites the closest rows in the file's novelty statement.
  A `DEAD` family may only be retested when the *base* changed — say which.
- **At loop close-out**, the orchestrator appends every new mechanism and
  updates statuses/numbers for the loop's screens.
- The curated family summary lives in the skill's "Mechanism inventory"
  (`.claude/skills/autoresearch-trading/SKILL.md`); this TSV is the
  exhaustive list behind it.

The champion at the time of writing: `strat_l15b_insideday` (train
+96.88% / DD −17.03% / calmar 5.69; forward +48.97% / −12.31%), params
`gw_w 0.15 / ids_lb 3 / ids_w −0.13` on the `strat_l13a_concwobble` chain.
