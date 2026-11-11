# File-hygiene gate — a blanket gitignore and a CI gate for stray run artifacts

Date: 2026-11-11 · Issue: [#2484](https://github.com/asimov-agent/llgenie/issues/2484)

## What was verified against the spec

Every `ADDED` requirement in `specs/file-hygiene-gate/spec.md` is locked by a real-git test in
`tests/test_file_hygiene.py` (tmp repositories read with `git ls-files` / `git check-ignore`):

- the blanket `*.log` rule (+ a dot-scratch `.<word><digits>.<ext>` rule) makes a new `.foo.log`
  ignored while `.env.example` stays trackable;
- `.unit2.log` and `.pr874.md` are removed forward-only (`git rm`) and absent from `git ls-files`;
- a planted tracked `*.log` / dot-scratch file goes the gate red, a clean tree passes, and an
  untracked ignored `.log` is not a finding;
- a dated exception fixture honours an intentional file and a stale exception fails;
- the gate is a `.PHONY:` `##` target, a step of `ci-unit`, and a `FAST_GATES` member, so the unit
  lane and `make lane-preflight` both reach it.

Gate run on the tree: `make check-file-hygiene` → `OK`; `make check-wiring` → OK (256 tests / 162
scripts wired); `make issue-bot-gates-check` → OK (7 fast gates); `make check-empty-files` → OK.

## Decisions taken

- The dot-scratch gitignore pattern is `.[a-zA-Z0-9_]*[0-9].*` — narrow enough that `.env.example`
  (no digits in the stem) is never caught, matching the issue's `.<word><digits>.<ext>` shape.
- The gate scans the **tracked** tree (`git ls-files`), not the working tree, so ignored/unstaged
  logs can never appear; the `.gitignore` blanket rule is the first line of defence and the gate is
  the enforcement.
- Findings are paths only, never file contents, per the log-scrutiny rule.
- `make lane-preflight` reaches the gate by making it a `FAST_GATES` member (the one list the
  issue-bot and lane-preflight both import), so a bot can never push a branch that commits a log.

## Status

Working tree holds the change, uncommitted (the job commits and opens the PR). `make openspec-validate`
and `make lint`/`make test-unit` need the docker test/openspec images and cannot run on this bare host
(no Docker daemon) — those gates, and the full loop, run in CI after the PR opens.
