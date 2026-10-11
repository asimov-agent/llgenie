# fix-bump-token-pr — proposal

Issue: [#136](https://github.com/asimov-agent/llgenie/issues/136)

## Why

`engine-bump.yml` and `registry-sync.yml` open their PRs with
`secrets.GITHUB_TOKEN`. A PR authored by `github-actions[bot]` holds every
`pull_request` workflow for manual approval (`action_required`), and a push
made with `GITHUB_TOKEN` starts no workflows. Run 38112265327 failed
`gh pr create` until the Actions checkbox was enabled; the re-run (38112740157)
created PRs #130–#135, and CI on those branches stayed `action_required`
(run 38113858713 on #130).

trending-local-llms already solved this: checkout, push and `gh pr create` use
an owner-scoped PAT, so the PR is authored by the owner and CI starts on its own.

## What Changes

- The bump job and the sync job check out with the repo secret `BUMP_TOKEN`
  and use it for the push and `gh pr create` / `gh pr edit`.
- The commit is authored as the token owner, not `github-actions[bot]`.
- The default `GITHUB_TOKEN` stays on the collaborator guard only.
- The workflows still never merge.

## Out of scope

- Creating or rotating the PAT. `BUMP_TOKEN` is a repo secret, set by hand.
- Merging the bump or sync PRs.
