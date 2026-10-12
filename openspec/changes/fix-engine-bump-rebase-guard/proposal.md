# fix-engine-bump-rebase-guard — proposal

Issue: [#212](https://github.com/asimov-agent/llgenie/issues/212)

## Why

A write collaborator can dispatch `engine-bump` and cannot dispatch
`engine-bump-rebase`. Run
[38315109038](https://github.com/asimov-agent/llgenie/actions/runs/38315109038)
is a `workflow_dispatch` by `andyholst` on `main` at `99ce5b9`. The guard
exits 1 with `actor andyholst is not a collaborator, bot, or owner` and the
rebase job is skipped.

`andyholst` has write on this repo. The same guard in `engine-bump` printed
`actor andyholst is a collaborator` on run
[38285390832](https://github.com/asimov-agent/llgenie/actions/runs/38285390832).

`.github/workflows/engine-bump-rebase.yml` calls the collaborators API with
the literal header `Authorization: Bearer ***`. `TOKEN` is set to
`secrets.GITHUB_TOKEN` and is not used. `ci.yml`, `engine-bump.yml`, and
`registry-sync.yml` send `Authorization: Bearer $TOKEN`. The literal is not
a credential, so the status is not 204 and every person is refused. The
daily cron fails the same way when `github.actor` is a person.

## What Changes

- The rebase guard sends `Authorization: Bearer $TOKEN`.
- `TOKEN` stays `${{ secrets.GITHUB_TOKEN }}`.
- A unit test reads `ci.yml`, `engine-bump.yml`, `engine-bump-rebase.yml`,
  and `registry-sync.yml` and rejects a literal `Bearer ***`.
- Checkout, push, and the rebase script stay on `secrets.BUMP_TOKEN`.

## Out of scope

- Changing who counts as a collaborator.
- Re-running the failed dispatch. That happens after this lands on `main`.
