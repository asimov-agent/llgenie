# The architecture bot's PR carries its own token, so CI runs for it

## Why

PR [#495](https://github.com/asimov-agent/llgenie/pull/495) has **no checks**:

```
$ gh pr checks 495 --repo asimov-agent/llgenie
no checks reported on the 'agent/architecture-20261021T1814' branch
```

`.github/workflows/architecture-bot.yml` opens the issue **and** the PR with the job's own token
(`GH_TOKEN: ${{ github.token }}`, because `secrets.BUMP_TOKEN` carries no Issues write — #412), and
`scripts/architecture_bot.py::publish()` uses that one env var for both `gh issue create` and `gh pr create`.
A pull request opened with `GITHUB_TOKEN` triggers **no workflows** (GitHub's anti-recursion rule), so no check
ever runs, nothing can be green, and every merge gate defers on `BLOCKED` forever. The bot then blocks
itself: `open_architecture_pr()` refuses to publish while an architecture PR is open.

The repository already solved this once: the issue-bot splits its write tokens (#430/#447), and
`engine-bump.yml` / `registry-sync.yml` open their PRs with `secrets.BUMP_TOKEN` and comment why.

## What Changes

- `scripts/architecture_bot.py::_gh(..., token=…)` runs `gh` with its **own** `GH_TOKEN`, so one call can
  authenticate differently from the next.
- `publish(..., pr_token=…)` keeps the job token for `gh issue create` and uses `PR_TOKEN` for
  `gh pr create`; an empty `PR_TOKEN` falls back to the inherited token (a local run) and says so on stderr.
- `.github/workflows/architecture-bot.yml` hands the publish step both:
  `GH_TOKEN: ${{ github.token }}` and `PR_TOKEN: ${{ secrets.BUMP_TOKEN }}`.
- `tests/test_architecture_bot.py`: the recorded `gh` proves the issue call carries the job token, the PR call
  carries the owner PAT, and the workflow's publish step carries both.

## Impact

- The next architecture refresh opens a PR that this repository's CI actually checks, so it can go green and
  be merged by the auto-merge path instead of sitting open with zero checks.
- The bot stops blocking itself on an un-mergeable PR.
- A local run still works with a single token, and warns when the PR will not trigger CI.
