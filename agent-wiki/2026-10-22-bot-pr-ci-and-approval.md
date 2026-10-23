# 2026-10-22 — a bot's PR is validated and can be approved (#497, #529)

**Issues:** [#497](https://github.com/asimov-agent/llgenie/issues/497), [#529](https://github.com/asimov-agent/llgenie/issues/529) ·
**PR:** the PR that closes them

## What was wrong

PR [#527](https://github.com/asimov-agent/llgenie/pull/527) — the architecture refresh — had **no checks at
all** (`gh pr checks 527` → "no checks reported on the 'agent/architecture-20261022T1842' branch") and
`mergeStateStatus: BLOCKED`, `reviewDecision: REVIEW_REQUIRED`, `author: app/github-actions`.

Two independent causes:

1. `architecture-bot.yml` opened the PR with `GH_TOKEN: ${{ github.token }}`. A pull request created with
   `GITHUB_TOKEN` starts **no** workflows, so there was nothing to go green (#497).
2. `scripts/auto_merge.py::try_approve()` accepted only `ALLOWED_AUTHORS = ("andyholst", "asimov-agent")`, so
   this repo's own Actions app was treated as a stranger and the `--admin` fallback was refused by GitHub
   (#529). The author gate (`author_may_merge`) already admitted it via `BOT_LOGINS` — the two halves of the
   job disagreed.

## What changed

- `scripts/architecture_bot.py`: `_gh()` / `_gh_retry()` take a `token` override and pass it through the
  child's **environment**; `publish()` reads `PR_TOKEN` and uses it for `gh pr create` only. The issue keeps
  the job token (the only one with Issues write, #412).
- `.github/workflows/architecture-bot.yml`: the publish step supplies
  `PR_TOKEN: ${{ secrets.BUMP_TOKEN }}`.
- `scripts/auto_merge.py`: `try_approve()` accepts an author this repo's bot identity owns (`_is_bot`), so the
  merge token — a different account from the app — can approve it. A third-party author is still refused.

## Verified

- `pytest tests/test_auto_merge.py tests/test_architecture_bot.py` in `llgenie/test:latest` → 50 passed.
- The architecture fake `gh` now records the credential per call, so the test proves the PR create carried the
  PAT and the issue create kept the job token, and that neither value reached argv.
- `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`,
  `make openspec-validate NAME=bot-pr-ci-and-approval`, `make test-unit` → recorded in the PR.

## Still needed for a fully unattended bot PR

A PR authored `asimov-agent` (every issue-bot/architecture-bot PR created with the PAT) still needs the
`APPROVER_TOKEN` secret for the approval — the author is the merge token's own account, and GitHub refuses a
self-approval. Without it — the run defers with the reason on the PR (never a bare red run).
