# The bots' scratch files are ignored by construction, not by a denylist

## Why

Every bot leg writes its run inputs at the repo root — `issue.md` (the dispatcher), `triage.md` (the
triage verdict), `refine-in.md` / `refine.md` (the refiner), `comment.md` (the outcome comment) — and
the push step stages with `git add -A`. `.gitignore` carries all of them except `triage.md`, and the
workflow papers over the gap with a hand-maintained exclude:

```yaml
git add -A
git reset -q -- issue.md 2>/dev/null || true
```

Measured on run [39513850754](https://github.com/asimov-agent/llgenie/actions/runs/39513850754): the
implement step changed nothing, `triage.md` alone made `git diff --cached` non-empty, and the bot
committed and pushed it as the implementation of #407. PR #424's whole diff was one line —
`TRIAGE: implement` — and it carried `closes #407` (issue #427).

The denylist is the defect, not the missing entry: every new scratch file a leg writes becomes a
candidate "implementation" the moment the real work is missing, and it makes the "did anything change"
test report the opposite of the truth.

## What Changes

- **`.gitignore`** — `triage.md` joins the other run inputs, so the ignore list is the complete set of
  artifacts a leg writes at the repo root (the comment above them says which leg writes which).
- **`.github/workflows/issue-bot.yml`** — the `git reset -q -- issue.md` line is gone: with the
  artifacts ignored, `git add -A` can only stage repository content, so there is no denylist to drift.
- **`tests/test_bot_scratch_ignored.py` (new)** — the roster is checked with **real git**:
  every scratch name must be reported by `git check-ignore`, must be written by a producer (Makefile /
  workflow / `scripts/*.py`), and the push step must not carry a per-file `git reset` exclude again. A
  new scratch file, a dropped ignore line, or a returning denylist reds `make test-unit`.
- **`README.md` + `agent-wiki/`** — the run-input contract and the one place that enforces it.

## Impact

- A bot run can no longer commit its own verdict as an implementation.
- No behaviour change for a run that really implemented something: its files are staged exactly as
  before.
- Not covered here (separate, linked issues): the worktree that escapes the `/repo` mount (#426), the
  exit code being read as "implemented" (#428), the placeholder PR body (#429), the token that cannot
  post the claim comment (#430).
