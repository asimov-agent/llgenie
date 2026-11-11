# Fork sync + PR workflow (gh CLI)

Reusable recipe for contributing to an upstream repo from a fork, when the fork's
`main` must track upstream and the working branch must stay on top of it.

## Sync the fork's main to upstream

Remotes: `origin` = upstream (the repo you contribute to), `fork` = your fork.

```sh
cd <repo>
git fetch -q origin && git fetch -q fork
# confirm fork main is an ancestor of upstream main (fast-forward possible)
git merge-base --is-ancestor fork/main origin/main && echo FF-OK
# fast-forward the fork's main to upstream
git push fork origin/main:main
git fetch -q fork   # re-fetch so fork/main ref is current
```

`git push fork origin/main:main` fast-forwards the fork's `main` branch to the
upstream commit without a PR. Verify with `git rev-parse --short fork/main` after.

## Rebase the working branch onto the synced main

```sh
git rebase -q origin/main   # replay your branch on top of the new upstream main
```

Do this after the fork sync so the PR branch is based on the latest upstream, not
an old fork main.

## Open the PR to upstream

```sh
git push -q -u fork <branch>
gh pr create --repo <upstream-owner>/<repo> --base main --head <you>:<branch> \
  --title "..." --body-file <path>
```

`--head <you>:<branch>` targets the fork branch; `--base main` targets upstream.
Use `--body-file` for any non-trivial body (see SKILL.md pitfall).

## Verify the CI run you are watching

```sh
gh run view <run-id> --repo <owner>/<repo> --json status,jobs \
  -q '.status as $s | ([.jobs[] | "\(.status)/\(.conclusion)"] | group_by(.) | map("\(.[0]) \(length)")) + [$s] | .[]'
```

Groups jobs by status/conclusion so you can see at a glance how many are green,
how many still run, and whether anything failed — without dumping every job line.

## Docs follow-up after a merged feature PR

When a feature PR changes how a tool is installed/used (e.g. native build →
container-only), the README almost always still describes the old model. After the
feature merges, diff the README against the new behavior and ship the doc fixes as
a separate docs-only PR. Verify with the repo's lint (`make lint`) before pushing.
