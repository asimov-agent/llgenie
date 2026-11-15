# 2026-11-14 — rebase-bot dispatch can be aimed at one PR (#2446)

Implements issue #2446 (OpenSpec change `rebase-bot-dispatch-pr-input`). PR: #2686. (written before the PR existed;

## What was verified against the spec

- `scripts/rebase_bot_sweep.py` gained `sweep(..., target=<n>)` and `--pr <n>`: an aimed run
  evaluates only the named PR; a target absent from the open set answers `action=none` with
  `targeted PR #<n> is not open` (exit 0). Board-wide behavior is unchanged when unset.
- `mk/bots.mk` forwards `TARGET_PR=<n>` → `--pr <n>`; `.github/workflows/rebase-bot.yml` gained
  the optional `pr` `workflow_dispatch` input, `TARGET_PR` job env, an aim echo, and threads the
  aim through every drain-loop iteration (an aimed run stays aimed: after the target is rebased
  the next sweep re-evaluates IT and the loop stops on `none`).
- All invariants verified to still apply to the aimed path by tests: daily cap, draft/base/owner
  reads, direct staleness measurement, bot-claim coexistence (`held by another bot` passes the
  target over), checks-in-flight, armed-green, never-merges, force-with-lease push to the head repo.
- New tests in `tests/test_rebase_bot_sweep.py`: aimed pick despite an older behind PR; ineligible
  target refused by name; closed target named; held target passed over. Full module green:
  73 passed (`~/llama-gguf-tools/.venv/bin/python -m pytest tests/test_rebase_bot_sweep.py -q
  -p no:cacheprovider`).
- Gates run: `make check-workflows` OK, `make check-wiring` OK, `make check-dispatch-forms` OK (dispatch table regenerated with `make dispatch-forms-report`), AGENTS.md `pr`-input line added,
  `make openspec-validate NAME=rebase-bot-dispatch-pr-input` valid.

## Key decisions

- The aim restricts *evaluation*, not *permission*: every guard, claim and cap check applies to
  the target exactly as to any sweep candidate (spec requirement "an aimed run cannot weaken a
  guard").
- The workflow keeps the aim across iterations so one dispatch can complete a rebase and then
  re-verify the (now fresh) target instead of drifting into board-wide behavior.
- AC3's live vehicle: dispatch `rebase-bot.yml` with `pr=<this PR>` and `--ref` this branch
  (the input only exists on the branch until merge); a fresh target must answer with the named
  `action=none` reason, exit 0.

## Current status

Implementation + tests green locally; live aimed dispatch runs after the PR exists. The AGENTS.md
line documenting the `pr` input is pending explicit owner consent (protected-file approval prompt
timed out; not applied, task 4 unticked until consent).
