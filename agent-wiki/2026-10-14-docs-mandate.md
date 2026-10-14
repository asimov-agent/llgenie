# Documentation is part of the change: README + agent-wiki, guarded (issue #257, PR #258)

## What was decided

AGENTS.md already required a README update in the same change and an `agent-wiki/`
record, but nothing could check either, and both drifted. This change makes them
**part of every change**, with a real gate instead of prose:

- a user-facing make target (one with a `##` help line, i.e. what `make help` prints)
  must be named in `README.md`;
- a target that deliberately stays out of the README must be a dated decision in
  `tests/fixtures/docs-exceptions.json` (reason + date + issue), and that record goes
  STALE — and fails — the moment the README documents it, so the file cannot rot;
- every `agent-wiki/*.md` work record must reference the issue or PR it implements
  (`#<n>`);
- everything else a change alters (a workflow/job/stage/gate, a renamed target, a new
  behaviour) is mirrored in the README's matching section in the same commit.

## How it is enforced

`scripts/check_docs.py` (`check` / `report`), driven by the make targets `check-docs`
and `docs-report`. `ci-unit` runs `$(MAKE) check-docs`, so a target the README never
learned about turns the pipeline red at the stage that is already the repo's contract
guard (it sits next to `check-wiring`), and `make test-unit` runs
`tests/test_check_docs.py` (7 tests: the real tree, the whole-token / pattern-stem
matching, the exception lifecycle including staleness, the work-record reference, and
the guard's own wiring in `ci-unit` + `test-unit` + `.PHONY`).

## Measured before/after (real output, `main` at `9cefc19`)

- Before: `make docs-report` → **112 user-facing targets, 19 not documented** in
  `README.md` (`lint-fix`, `openspec-new/status/shell`, `queued-alarm`,
  `check-registry-keys`, `check-strata-models`, `engine-detect`, `engine-smoke`,
  `generate-build-engine-params`, `run-engine-%`, `test-health-host`,
  `test-top-tier-ci`, `test-top-tier-serve-ci`, `test-variant-image`,
  `install-prism-cpu/cuda`, `install-upstream-cpu/cuda`).
- After: all 19 are documented in the README (Install targets block, verification
  block, and the new "Documentation is part of the change" section), so the guard is
  green with **zero** exceptions: `[check-docs] ok: every one of the 114 user-facing
  make targets is documented in README.md (or a recorded exception), and every 38
  agent-wiki/ entry references an issue or PR`.
- `python3 scripts/check_wiring.py check` stays green (98 documents; the new script is
  wired through `check-docs` → `ci-unit`, the new test through `test-unit`), and
  `python3 scripts/lint_linefeeds.py` reports `LINT OK`.

## Rebase onto main after PR #253 merged: the gate caught main's own gap

Rebasing onto `87039e9` (the squashed PR #253, the fix-bot) conflicted only in the
`Makefile`, in exactly the two union regions the wiring guard's own rebase had: the
`.PHONY` continuation line and the single `test-unit` recipe line naming every test
file. Both sides were kept (main's `fix-loop*` / `fix-bot-*` / `agent-image*` targets +
my `check-docs`/`docs-report`; main's `test_fix_loop.py`/`test_fix_bot_sweep.py` + my
`test_check_docs.py`), and the stray `\` -followed-by-space continuation main's line
carried was normalised to one clean line (same tokens, no behaviour change). Markers
were cleared with a deterministic line-splice, not `patch`.

The rebased tree then went red on the new gate — **PR #253 added 8 user-facing targets
with no README sentence** (`fix-loop`, `fix-loop-image`, `fix-bot-sweep`,
`fix-bot-report`, `agent-image`, `agent-image-pull`, `agent-image-ref`,
`publish-agent-image`). That is the gate doing its job on a merge artifact, so they are
documented here as part of this change (a "PR fix-bot & the agent (Hermes) image"
section plus the target block), keeping the merged tree green with still **zero**
recorded exceptions.

## AGENTS.md behaviour

The short "README must always be kept in sync" section is replaced by **"Documentation
is part of the change: README + the work record (MANDATORY, durable)"**, which states the
two obligations (README in the same commit; the `agent-wiki/` entry, referencing the
issue and the PR) plus the gate that enforces them, and `## Record of work` now points
at it. `AGENTS.md` was written under the user's explicit approval: writes to that file
are gated behind a protected-file approval prompt, and the first attempt was refused
when the prompt timed out.

## Status

Open PR #258 for review; not merged. `make check-docs`, `make test-unit` and the
Hermes context-file threat scan of `AGENTS.md` (`scan_for_threats(..., scope="context")`
→ `[]`) all pass on the branch.
