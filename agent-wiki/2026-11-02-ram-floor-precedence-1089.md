# card-gate RAM-floor precedence (issue #1089)

The #1072 measured-governs ruling is now a tree-enforced invariant in more than one direction.

## The rule, verbatim

The system-RAM floor is read from the evidence that admitted the model — the admitting run's
own `system_ram_min`, else the RAM its `hardware` string names — and only when that evidence
states none is the model's declared `system_ram_min` read. In both directions the evidence's
figure is the floor. A `fits()` call with no host RAM applies the card evidence alone (it has
no host to measure the floor against).

## Before (the #1061 defect class)

- `specs/card-gate/spec.md:11` read *"When the store states `system_ram_min`, the host's RAM
  SHALL also be at least that"* — unqualified contract-governs, excluding the run's own figure.
- `docs/ARCHITECTURE.md` repeated the unqualified claim ("the store's own `system_ram_min` floor
  when it states one").
- The suite pinned the floor in only ONE direction (run 32 GB / contract 128 GB): a switch to
  declared-governs, or to `max()` of the two, passed every test.

## What changed (#1089)

1. **Tests (both directions + the unknown-host case):**
   - `test_the_system_ram_floor_still_applies` extended to assert the declared value is not read
     when the run states one (16 GB / 512 GB relabels change no `fits()` answer).
   - `test_the_run_floor_governs_when_the_run_names_more_ram_than_the_contract`: run 110 GB /
     contract 16 GB → `fits(m, 24, 64) is False`, `fits(m, 24, 110) is True` — the opposite
     direction, where 12 of the 23 divergent store rows live (e.g. `qwen3.8-flash-next-125b`
     declares 16 GB, admitted by a run naming 110 GB).
   - `test_fits_without_host_ram_applies_the_card_evidence_only`: the no-host widening is stated
     deliberately, not left an artefact.
2. **Criterion of record:** `specs/card-gate/spec.md`'s requirement states the evidence-ordered
   rule verbatim (both directions + no-host), the `system-RAM floor still applies` scenario
   re-read to name the run's figure, and two new Given/When/Then scenarios added each with its
   `- **Test:**` line. `docs/ARCHITECTURE.md` names the same evidence-ordered floor.
3. **No behaviour change:** `ram_floor_gb()` / `fits()` are already measured-governs (#1072); the
   work is the pin, the criterion, and the honest unknown-host case.

## Verification

- `tests/test_card_gate_measured_vram.py`: 12 passed.
- `git grep -n system_ram_min docs/ARCHITECTURE.md openspec/changes/card-gate-measured-vram/`
  shows no unqualified "the host's RAM SHALL also be at least [the store's]".
- `make check-docs check-workflows check-wiring lint` green; `make openspec-validate
  NAME=card-gate-measured-vram` green (measured on the PR head).
