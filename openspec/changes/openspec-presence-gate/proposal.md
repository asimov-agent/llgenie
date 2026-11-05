# An implementing PR must carry (or name) its own OpenSpec change

## Why

`make ci-openspec` (Makefile:1835) = `openspec-validate-all` (validate the STRUCTURE of every ACTIVE
change, issue #156) + `openspec-tasks-check` (no ACTIVE change has an unchecked `- [ ]` task box,
`scripts/check_openspec_tasks.py`). Both iterate over **existing** changes under
`openspec/changes/*` — neither can detect "this PR implements work that has no OpenSpec change at
all". An implementing PR that adds no change directory is structurally invisible to the gate and is
CI-green.

AGENTS.md (lines 27–53, **MANDATORY**) requires every change to start as an OpenSpec change
(`make openspec-new NAME=<name>` → `proposal.md` + `specs/<cap>/spec.md` + `tasks.md`, created before
the feature branch / PR). The fleet historically obeyed (104 commits adding `openspec/changes/*`),
but the last several implementing PRs shipped with zero OpenSpec files: #1805-implementing #1806, and
earlier #1803, #1801, #1799, #1797, #1795 — all carry 0 files under `openspec/`. The discipline lapsed
without any CI catching it.

Evidence (issue #1806): files list = `[CHANGES.md, agent-wiki, docs/BOTS.md, docs/changes.d,
scripts/issue_refiner.py, tests/test_issue_refiner_form.py]` — no `openspec/` at all.

## What changes

A new hygiene gate `check-pr-openspec-change` (subcommand `openspec-change` of
`scripts/check_pr_hygiene.py`, mirroring `sync-line`) that reds an implementing bot PR whose diff adds
no file under `openspec/` — unless one of three exemptions applies:

1. **The PR's own diff adds an OpenSpec change** — the range carries at least one new file under
   `openspec/changes/<name>/`. The existing `openspec-validate-all` + `openspec-tasks-check` already
   validate its structure and task ticks; the presence gate does not re-validate (no hand-rolled
   change validation, no weakening of either existing gate).
2. **The body names an existing change** — a `OPENSPEC: <name>` body line references an exact,
   currently-ACTIVE change under `openspec/changes/` that the PR implements against. A legitimately
   change-less implementing PR (a pure docs/regen/CHANGES-only PR) can opt out deliberately this way,
   rather than by silence.
3. **The change is pure docs/regen** — every file the range touches is under `docs/`, `agent-wiki/`,
   `CHANGES.md`, `README.md`, or the change-note trio; no product code. Such a PR has nothing to
   spec-track and names no change.

Any other implementing bot PR whose final diff adds no `openspec/` file is refused with a finding
naming the missing directory and pointing at `make openspec-new`.

The gate is bot-gated (`is_bot_pr`, the same gate `agents-line`/`sync-line`/`acceptance` use): a human
leg is not held to a rule the repo does not force on its own automation. It is verification-only by
construction — it reads the diff and the body, never writes a tick.

## Impact

- `scripts/check_pr_hygiene.py` — a new `openspec-change` subcommand + `openspec_change_findings()`
  (+ the bot-gated `pr_openspec_change_findings`), reusing the existing `_git`, `is_bot_pr` and
  live-body plumbing; no new subprocess site.
- `Makefile` — a new `check-pr-openspec-change` target with a `##` help line, registered in `.PHONY`.
- `.github/workflows/ci.yml` + `.github/workflows/scope.yml` — the guard+scope jobs run
  `make check-pr-openspec-change` with the same live-body read as `check-pr-sync-line`.
- `tests/test_pr_hygiene_openspec_change.py` — red-on-old (an openspec-empty implementing PR passes
  today) / green-on-fixed (now red), with the working exemptions pinned.

Not in this change: retroactively adding OpenSpec changes to #1803/#1801/#1799/#1797/#1795 (those PRs
are merged/historical; the presence gate guards the wedge going forward). Also not: weakening
`openspec-validate-all`/`openspec-tasks-check` — they stay exactly as they are.

