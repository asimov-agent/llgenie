# PR bodies and commit messages state the issue, the fix and the benefit (#313)

Implemented by PR [#315](https://github.com/asimov-agent/llgenie/pull/315) (issue #313).

## Why

`AGENTS.md` required a PR body to reference its issue and end with `closes #N`, and every commit to
be a typed Conventional Commit — but nothing said what the message must **contain**, and nothing
enforced it. Measured on `main`, the repo's own producers shipped subject-only commits:

| producer | commit before |
|---|---|
| `.github/workflows/engine-bump.yml` | `chore(engine): bump <id> to <ref>@<sha>` (no body) |
| `.github/workflows/issue-bot.yml` | `feat(issue-bot): implement #<n>` (no body) |
| `.github/workflows/registry-sync.yml` | `chore(registry): sync …` (no body) |

A `git log` reader of any of them learned the *what* and never the issue it answered, the mechanism
that fixed it, or the benefit — and a `gh pr create` could be opened with no `--body` at all with no
gate noticing.

## What landed

- **`AGENTS.md`** carries a durable, mandatory section: a commit/PR message carries three labelled
  parts — `Issue:` (with `#N`), `Fix:`, `Benefit:` — then a `Technical:` extension (files, targets,
  tests, gates, measured numbers); the subject stays a typed Conventional Commit; empty and
  placeholder messages are forbidden.
- **`make check-pr-hygiene`** (`scripts/check_pr_hygiene.py check`, wired into `ci-unit`): reads
  every producer the repo owns — `.github/workflows/*.yml`, the `Makefile`, `scripts/**/*.sh` (shell
  invocations) and `scripts/**/*.py` (the argv list the `_gh` helper builds) — and fails on a commit
  with no message, a placeholder message, a subject that is not a typed Conventional Commit, or no
  body; on a PR opened with no body or a placeholder body; and on an `AGENTS.md` that lost the
  mandate heading. `make pr-hygiene-report` prints what it reads.
- **The three producers emit a real body**: each builds `msg=$(printf 'Issue: … Fix: … Benefit: …
  Technical: …')` and commits `-m "<subject>" -m "$msg"`; `engine-bump.yml` passes `bash -n` per line
  as its test requires.
- **`tests/test_pr_hygiene.py`** (wired into `test-unit`): 13 cases — bodiless commit, placeholder
  subject, untyped subject, no message at all, no/empty/placeholder PR body, the accepted variable
  and body-file shapes, the Python argv form, the missing AGENTS.md mandate, the exit-code contract
  (`1` on a fixture, `0` on this tree), this repo passing its own guard, and the three producers
  naming all four parts.
- **README** documents both targets and the mandate.

## Verification

- `python3 scripts/check_pr_hygiene.py check` on `main`'s tree: **4 violations** (3 bodiless commits +
  the missing mandate); on this branch: **0**. That is the guard firing on the real code and then
  passing on the fixed one.
- `tests/test_pr_hygiene.py`: **13 passed** in `llgenie/test:latest`
  (`docker run --rm -v "$PWD":/repo:ro … -m pytest tests/test_pr_hygiene.py --noconftest`).
- `tests/test_engine_bump_pr_body.py`: **6 passed** — the commit-message line changed, the PR-body
  assembly it pins did not.
- `make lint`, `make check-pr-hygiene`, `make check-docs`, `make check-wiring`,
  `make check-dispatch-forms`, `make check-secret-output`,
  `make openspec-validate NAME=pr-message-substance`.

## Note

The guard checks that a **real message/body is passed** (presence, not prose): a body built into a
variable or a file is accepted, and `tests/test_pr_hygiene.py` pins the content of the three
producers' messages. The mandate's section heading is itself checked, so the rule cannot be deleted
by an edit that leaves the code green.
