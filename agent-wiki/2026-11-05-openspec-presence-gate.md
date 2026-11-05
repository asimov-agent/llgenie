# The OpenSpec-presence gate (#1807)

`make ci-openspec` (Makefile:1835) is `openspec-validate-all` (validate the STRUCTURE of every ACTIVE
change, issue #156) + `openspec-tasks-check` (no ACTIVE change has an unchecked `- [ ]` task box,
`scripts/check_openspec_tasks.py`). Both iterate **existing** changes under `openspec/changes/*`, so an
implementing PR that adds no change directory is structurally invisible and CI-green. AGENTS.md lines
27–53 (**MANDATORY**) require every change to start as an OpenSpec change (`make openspec-new
NAME=<name>` → `proposal.md` + `specs/<cap>/spec.md` + `tasks.md`, created before the feature branch /
PR). The fleet historically obeyed (104 commits adding `openspec/changes/*`), but the last several
implementing PRs shipped zero files: #1806, #1803, #1801, #1799, #1797, #1795.

## What the gate does

`make check-pr-openspec-change` (a `scripts/check_pr_hygiene.py openspec-change` subcommand, bot-gated
by `is_bot_pr` like `agents-line`/`sync-line`/`acceptance`) reds an implementing bot PR whose final diff
adds no file under `openspec/changes/<name>/` — unless one of three exemptions applies:

1. **The PR's own diff adds an OpenSpec change** — the range carries a new file under
   `openspec/changes/<name>/`. The existing `openspec-validate-all` + `openspec-tasks-check` own its
   structure and ticks; the presence gate does not re-validate (no hand-rolled change validation, no
   weakening of either existing gate).
2. **The body names an existing change** — a `OPENSPEC: <name>` body line references an exact,
   currently-ACTIVE change the PR implements against. A legitimately change-less implementing PR opts out
   deliberately rather than by silence.
3. **The change is pure docs/regen** — every file the range touches is under `docs/`, `agent-wiki/`,
   `CHANGES.md`, `README.md`, or the change-note trio; nothing product to spec-track.

Any other implementing bot PR whose final diff adds no `openspec/` file is refused with a finding naming
the missing directory and pointing at `make openspec-new`.

## Surfaces

- `scripts/check_pr_hygiene.py` — `openspec_change_findings()` + the bot-gated
  `pr_openspec_change_findings()`, reusing `_git`, `is_bot_pr` and the live-body plumbing; no new
  subprocess site (`check-proc-gate` green).
- `Makefile` — `check-pr-openspec-change` target with a `##` help line, registered in `.PHONY`.
- `.github/workflows/ci.yml` + `.github/workflows/scope.yml` — the guard+scope jobs run
  `make check-pr-openspec-change` with the same live-body read as `check-pr-sync-line` (issue #1589); a
  push to main has no PR number and prints `nothing to validate` instead of failing.
- `tests/test_pr_hygiene_openspec_change.py` — builds real commits; proves an openspec-empty implementing
  PR is refused (green-on-fixed) and that the pre-fix tree cannot flag it (red-on-old: on the old
  `check_pr_hygiene.py` `openspec_change_findings` does not exist and the refusal tests fail). The
  introducing change `openspec/changes/openspec-presence-gate/` carries its own proposal/spec/tasks.

Implements issue #1807. The two existing openspec gates are untouched.

