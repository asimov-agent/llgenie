# Auto-merge: who may open the PR

Issue: #499. PR: #500.

Measured on `main` at `677ffee`: every open PR (#481, #492, #495, #498) was `MERGEABLE` with every check
`success` and still `BLOCKED` / `REVIEW_REQUIRED`. The `auto-merge` job in `ci.yml` ran on the
`pull_request` event, so a fork head (`andyholst/llgenie`) saw `secrets.BUMP_TOKEN` as the empty string and
deferred. A same-repo bot PR (#495) had no checks at all, because its PR was opened with the job token.

The merge now lives in `.github/workflows/auto-merge.yml` (`workflow_run` on `CI`), where the base
repository's PAT exists. A green PR blocked only by a required review is squash-merged with `--admin`,
because the owner PAT is the account that opens these PRs and GitHub refuses that self-approval. The
bypass runs only after the author gate: the repository owner, a write collaborator, or the bot. A bot PR
is authorised by the CI run's actor. A stranger is deferred, not bypassed.
