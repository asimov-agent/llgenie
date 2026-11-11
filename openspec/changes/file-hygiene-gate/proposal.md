# file-hygiene-gate — proposal

Issue: [#2484](https://github.com/asimov-agent/llgenie/issues/2484)

## Why

Runtime artifacts get committed into the tree and merge with PRs. Measured on `main` at
`ad97febcd`: `.unit2.log` (10 bytes) is tracked — it entered via PR #2277 (commit d6165f409) — and
`.pr874.md` (3,221 bytes) is tracked — it entered via PR #1738 (commit e7ec0795f). Both are stray
output from local runs, named after the run that produced them, not documentation. `.gitignore`
listed only a handful of specific log names (`.run.log`, `*.progress.log`, `hermes-run.log`,
`hermes-run.scrubbed.log`) with no blanket `*.log` rule, so any new `*.log` the tools started writing
was committable.

Three consequences compound:

1. a dot-prefixed `.pr874.md` looks like docs to a reader but is a run artifact, and every future
   agent/bot run can leak a new stray log under a new name;
2. an artifact committed once stays in history and keeps re-appearing in worktrees and PR diffs,
   adding review noise and secret-exposure surface (logs can carry tokens, paths, transcripts);
3. without a gate, "did we gitignore it?" is re-answered by hand for each new tool.

## What Changes

- **`.gitignore`** becomes categorical: a blanket `*.log` rule (the explicit per-name rules stay for
  readability) plus a rule for dot-prefixed run-artifact names `.<word><digits>.<ext>` (e.g.
  `.pr874.md`, `.unit2.log`) — a leading dot, letters/digits with at least one digit before the
  extension dot — so a new log name is ignored without being enumerated.
- **`git rm .unit2.log .pr874.md`** — forward removal; history is not rewritten (the old blobs stay
  in past commits by design, per the issue's `Not covered`).
- **`scripts/check_file_hygiene.py`** (new, stdlib only) — the gate: scans every file git tracks
  and fails when a committed file matches a runtime-artifact shape — any `*.log`, or a dot-prefixed
  `.<word><digits>.<ext>` scratch name — unless a dated exception fixture records why. Findings are
  listed as **paths only**, never file contents (the log-scrutiny rule).
- **`tests/fixtures/file-hygiene-exceptions.json`** — the dated, allowlist-driven exception fixture
  (reason + date + issue per entry), mirroring the docs/skill-size exception pattern. An entry is
  honoured; an entry whose file is no longer tracked or no longer matches a pattern is STALE and
  fails — an exemption cannot outlive its reason.
- **`make check-file-hygiene`** (with `##` help line, declared `.PHONY:`) drives the gate in the
  unit lane (`ci-unit`) and in `make lane-preflight` (as a `FAST_GATES` member, so `scripts/issue_bot_gates.py`
  re-checks it before every bot push). `make file-hygiene-report` prints the picture.
- **`tests/test_file_hygiene.py`** — real-git tests (tmp repositories the gate reads with `git
  ls-files`/`git check-ignore`) proving: a planted violation goes red; a clean tree passes; only
  tracked files are scanned; an exception is honoured; a stale exception fails; `.foo.log` is
  ignored but `.env.example` stays trackable; and the gate is wired into `ci-unit`, `FAST_GATES`
  and `.PHONY`.

## What this does NOT change

- Removing the two blobs from git history (rewriting shared history is a durable NO for this repo).
- Any of the four named log rules already in `.gitignore` (kept for readability).
