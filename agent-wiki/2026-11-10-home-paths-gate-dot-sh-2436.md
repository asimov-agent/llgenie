# The $HOME rule now bites executed shell lines in agent scripts too (issue #2436)

Issue #2145 made `$HOME` the required form in authored text and `check_agent_profiles.py` enforced
it across `agents/**/*.md`. Measured gap: `agents/**/*.sh` was outside the scan, and the rebase
lane's `stack-replay.sh` carried a hard-coded `/home/<user>` fallback — a literal that silently
breaks on any lane host that is not that account (issue #2436, PR #2441).

## What was verified

- The scan (this PR, rebased onto main `954134135eea5945ac9227a2efcd9a48c291e70d` at sweep 2026-11-10):
  `scripts/check_agent_profiles.py` now walks `agents/**/*.sh` for the home-path literal on executed
  lines; a line whose first non-blank character is `#` is skipped — a comment recounting a past
  defect keeps its absolute path (`skill-script-hygiene.md`), and `scripts/*.py` stays excluded
  because a Python literal rewritten to `$HOME` never expands.
- `tests/test_home_paths_gate.py` carries the new scenarios (executed literal in a `.sh` → finding;
  comment → no finding; `.md` coverage unchanged); runs in CI `ci-unit`.
- `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/scripts/stack-replay.sh` fallback
  converted to `$HOME`, so lane replay works on every host.
- OpenSpec change `home-paths-gate-dot-sh` (proposal + `specs/home-paths-gate/spec.md` + all-ticked
  `tasks.md`) rides the same branch; `make openspec-validate` rc=0 locally, CI re-validates.

## Decisions

- Comments are NOT shipped behaviour: the gate flags only executed lines, mirroring the hygiene
  reference rather than blanket-banning the literal anywhere in a `.sh`.
- No product-code change by the sweep itself; the sweep added the OpenSpec change, this note and
  its fragment, and rebased the branch (the #2145 lineage's own change is archived).

## Status

Open as PR #2441 (branch `fix/2436-stack-replay-home`, head re-stamped `AGENTS:`/`BASE:` at the
sweep main sha); CI at the new head decides lint/unit/guard verdicts.
