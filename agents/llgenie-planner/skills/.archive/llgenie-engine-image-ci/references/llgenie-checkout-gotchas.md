# llgenie checkout gotchas (measured in ~/repository/git/llgenie)

Failures that cost a turn each time they are rediscovered. SKILL.md is at its size limit, so these live here.

## The remotes are INVERTED from how AGENTS.md reads

```
origin  https://github.com/asimov-agent/llgenie.git   # UPSTREAM
fork    https://github.com/andyholst/llgenie.git      # the user's fork
```

`git push -u origin <branch>` pushes a branch INTO the upstream repo. AGENTS.md says "push to origin (the
fork)" — in this checkout that is wrong; push PR branches to `fork`, then
`gh pr create --repo asimov-agent/llgenie --base main --head andyholst:<branch>`.

A branch pushed to upstream is not fatal, and it is the only way to live-verify a `workflow_dispatch`-only
workflow before merge: `gh workflow run <wf>.yml --ref <branch>` only accepts refs that exist in
`asimov-agent/llgenie`, so a fork-only branch cannot be dispatched. (Measured: dispatching
`publish-agent-image.yml` on such a branch proved the fix in ~2 min instead of asserting it post-merge.)

## `make openspec-new` leaves a ROOT-owned directory

The openspec container runs `-u root`, so the new change dir is root-owned and `write_file` into it fails
with `Permission denied`. Always follow the CLI with:

```bash
sudo chown -R $(id -u):$(id -g) openspec/changes/<name>
```

## OpenSpec validation shape

- A `### Requirement:` with no `#### Scenario:` block fails with `must include at least one scenario`.
- Every scenario needs a `- **Test:**` line naming the file::case (or the CI job + make command) that locks it.
- Given / When / Then on separate lines; the matching pytest body carries `# Given / # When / # Then` markers.

## A branch whose PR already merged is a dead end

A commit pushed to a branch AFTER its PR merged never reaches a PR, and nothing notices (no CI on the base,
no bot comment). Measured: the #413 fix (`991955e`) sat a day on `feat/bot-model-1017` whose PR #410 had
merged 75 minutes earlier; `main` kept failing for the same reason. Before trusting "this branch already has
a PR": `gh pr list --repo asimov-agent/llgenie --head <branch> --state all`. If the PR is MERGED and the
branch moved, cut a fresh branch off main and carry the commits over (cherry-pick).

## Worktrees

They live at `../llgenie-wt/<kebab>` and dozens persist. `git worktree list` first: a branch may already be
checked out in its own worktree (`git branch -a` marks it with `+`), and that worktree is where the work
goess. Never `git switch` the user's primary checkout (`/home/asimov/repository/git/llgenie`).

## `macos / top-tier` reds on Hub slowness, not on the diff

A read-phase socket timeout arrives as the builtin `TimeoutError`, raised inside `http.client`/`ssl` after
the connection exists — it is NOT a `urllib.error.URLError` subclass, so a retry loop that catches only
`URLError` lets one slow read escape as a traceback and exit 1. Check
`scripts/llgenie_serve.py::_hf_get` and `tests/test_top_tier_acceptance.py` before blaming the commit that
happened to be pushed. The run-failure reactor files its own duplicate issue per red run (#548 vs #549 for
the same run), and #399 owns the "live Hub inside a blocking gate" question.

## Nerve guard false positive

After a long autonomous run the guard can report "no task-relevant mutation" even though commits landed in
a sibling worktree — it appears to watch only the primary checkout. State what changed (shas, paths, remote
verification) and ask the user instead of mutating the primary checkout to appease it.
