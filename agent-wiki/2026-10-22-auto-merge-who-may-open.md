# Auto-merge: who may open the PR

Issue: #499. PR: opened from `feat/auto-merge-from-base`.

Measured on `main` at `677ffee`: every open PR (#481, #492, #495, #498) was `MERGEABLE` with every check
`success` and still `BLOCKED` / `REVIEW_REQUIRED`. The `auto-merge` job in `ci.yml` ran on the
`pull_request` event, so a fork head (`andyholst/llgenie`) saw `secrets.BUMP_TOKEN` as the empty string and
deferred. A same-repo bot PR (#495) had no checks at all, because its PR was opened with the job token.

The merge now lives in `.github/workflows/auto-merge.yml` (`workflow_run` on `CI`), where the base
repository's PAT exists, and it approves a green PR whose only blocker is a required review. It merges only
when the author is the owner, a write collaborator, or the bot — a bot PR is authorised by the CI run's
actor, the same gate `ci.yml`'s `guard` job already applies.
