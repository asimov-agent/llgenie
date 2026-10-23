# A bot's PR is validated and can be approved

## Why

Two measurements, one outcome — a workflow PR can never merge:

1. **PR #527 (architecture refresh) has no checks at all.** `gh pr checks 527` answers "no checks reported",
   and `gh pr view 527` shows `author=app/github-actions`. `.github/workflows/architecture-bot.yml` opens the
   PR with `GH_TOKEN: ${{ github.token }}`, and a pull request created with `GITHUB_TOKEN` starts **no**
   workflows (issue #497). Nothing can go green, so the merge job can never act.
2. **The auto-merge job refuses to approve that author.** `try_approve()` accepts only
   `ALLOWED_AUTHORS = ("andyholst", "asimov-agent")`, so `app/github-actions` — this repo's own Actions app —
   is treated as a stranger:

```
[auto-merge] PR #527 cannot be approved: … the author `app/github-actions` is not one of this repo's
identities (andyholst, asimov-agent) — a bot does not approve a stranger's PR
```

   and the `--admin` fallback is refused by GitHub. The author gate (`author_may_merge`) *does* admit the bot
   (`BOT_LOGINS`), so the two halves of the job disagreed.

## What Changes

- **The architecture bot creates its PR with the owner PAT**, not the job token, so `pull_request` workflows
  run: `scripts/architecture_bot.py::publish()` passes `PR_TOKEN` through the child's environment for
  `gh pr create` only, and `architecture-bot.yml` supplies `PR_TOKEN: ${{ secrets.BUMP_TOKEN }}`. The issue
  keeps `github.token` — the only one of the two with Issues write (#412).
- **`try_approve()` accepts this repo's own bot as an author.** A `BOT_LOGINS` / `…[bot]` author may be
  approved by the merge token (a different account from the app, so GitHub's self-approval rule holds). A
  third-party author is still refused, unchanged.
- **Tokens never reach argv**: `_gh()` in both scripts passes an override through the child environment.

## Impact

- An architecture refresh now carries a real CI run, so a human — or the merge gate — can see it validated.
- A bot-authored PR is approvable by the other identity instead of being permanently stuck.
- No policy change: the bot still never merges its own PR, and a stranger's PR is still refused.
