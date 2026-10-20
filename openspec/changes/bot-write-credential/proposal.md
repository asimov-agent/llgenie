# A bot's write uses the credential that can make it

## Why

Two bot legs were red or dead for a credential reason, and the credential was the wrong one all along
(issue #412). Both steps were handed `secrets.BUMP_TOKEN`, an owner PAT scoped to pushing a branch and
opening a PR, while the job's own `permissions:` block already granted the write they make.

`issue-refiner`, every scheduled run for at least five runs:

```
refine  Decide …  [issue-refiner] gh issue comment 91 --repo asimov-agent/llgenie --body <!-- bot-claim … -->
                  `refiner` is refineing this now. …
                  failed (1): GraphQL: Resource not accessible by personal access token (addComment)
```

`fix-bot`, when its sweep selects a PR:

```
sweep  [sweep] dispatch failed: could not create workflow dispatch event:
       HTTP 403: Resource not accessible by personal access token
       (…/actions/workflows/384587805/dispatches)
```

`github.token` is scoped to this repository and to the job's declared permissions, and every one of
these jobs already declares the permission it needs (`issues: write`, `actions: write`). The same
workflows already use `github.token` for their guard, commit-report and checkout steps.

## What Changes

- **`issue-refiner.yml`** — the three issue-writing steps (claim/pick, apply the review, report the
  outcome) use `github.token`; the job declares `issues: write`.
- **`issue-bot.yml`** — the verdict step (ONE comment + `agent:refined`/`agent:closed`) uses
  `github.token`; the **push** step keeps the owner PAT (a `GITHUB_TOKEN` push does not re-trigger CI).
- **`fix-bot.yml`** — the sweep's `gh workflow run` uses `github.token`; that job declares `actions: write`
  (it already did, which the PAT could not honour).
- **`run-failure-reactor.yml`** — filing its deduped issue / dispatching the fix-bot uses `github.token`
  (`actions: write` + `issues: write` are declared).
- **`queued-alarm.yml`** — delivering the alarm (PR comment, else one deduped issue) uses
  `github.token` (`issues: write` is declared).
- **`tests/test_bot_write_tokens.py` (new)** — locks the split: every issue-writing step is handed
  `github.token` and its job declares `issues: write`; every dispatching step is handed `github.token`
  and its job declares `actions: write`; every pushing job still carries the owner PAT (step env, job
  env, or the checkout token that `git push` actually uses).
- Nothing changes for the legs that PUSH: `issue-bot`, `fix-bot`, `rebase-bot`, `engine-bump`,
  `engine-bump-rebase` and `registry-sync` keep `BUMP_TOKEN`, because their push must re-trigger CI.

## Impact

- Affected specs: `bot-write-credential` (new capability).
- Affected code: five workflow files, `tests/test_bot_write_tokens.py` (new), `README.md`,
  `agent-wiki/`.
- No secret is added or widened: `github.token` is narrower than the PAT it replaces (this repository,
  this job, these permissions), so the change reduces what a compromised bot step can reach.
- A human can still widen the PAT if they prefer one credential — but then the permissions block and
  the PAT must agree, and this test does not require the PAT at all.

## Not covered

- The push credential and the fork-PR selection are untouched: #340 (the sweep skips every fork PR) and
  the PAT's push scope stay as they are.
- `BUMP_TOKEN`'s own scope inventory is the owner's decision; this change stops depending on it for
  writes it demonstrably cannot make.
