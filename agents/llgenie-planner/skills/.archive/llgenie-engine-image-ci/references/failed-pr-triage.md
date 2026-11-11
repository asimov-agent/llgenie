# Triaging red PRs in llgenie

How to answer "go over the failed PRs and make sure they work" without wasting a
CI cycle, and the classes of red a PR in this repo actually produces.

## 1. Separate "queued" from "failing" before anything else

`gh run list` reports the run's status, and a run is `queued` while **any one** of
its jobs is queued — the macOS runner pool lags the Linux one by hours, so six
healthy PRs look stuck. Read the per-PR rollup instead:

```bash
gh pr view <n> --json statusCheckRollup \
  --jq '[.statusCheckRollup[]? | select(.conclusion == "FAILURE" or .conclusion == "TIMED_OUT" or .conclusion == "CANCELLED") | .name]'
```

A check with an **empty/null conclusion is pending, not failed**. `mergeStateStatus
== BLOCKED` with no failure entries means "still waiting on a required check", not
"broken".

Failing job ids for a run:

```bash
gh run view <run-id> --json jobs --jq '.jobs[] | select(.conclusion=="failure") | "\(.name)\t\(.databaseId)"'
```

## 2. Logs are gated on the WHOLE run finishing

`gh run view --job <job-id> --log-failed` answers `run <id> is still in progress;
logs will be available when it is complete` until the last sibling job ends — even
though the failing job itself finished long ago. The check-run annotations
(`gh api repos/<owner>/<repo>/check-runs/<id>/annotations`) only carry
`Process completed with exit code 2`, which is useless for diagnosis.

So while a run is pending: **reproduce locally** in a worktree instead of
waiting. Same for `gh run rerun <id> --failed`, which refuses with `cannot be
retried` until the run completes.

## 3. Fast local iteration (the suite is 28 minutes)

`make test-unit` in the test image is ~5,200 tests / ~28 min. To check one file,
copy the flags `make -n test-unit` prints:

```bash
docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root \
  llgenie/test:latest python -m pytest tests/<file>.py -q
```

Add `-v "$MAIN_REPO":$MAIN_REPO:rw` when the worktree's `.git` is a file (the
conftest mounts the parent repo). Run the full suite only once the targeted
files pass — and run it per branch in parallel background jobs when several PRs
are in play.

## 4. The four reds a PR here actually produces

- **Test and implementation lock contradictory contracts.** A behaviour change
  (a fallback, a tag, a constant) that leaves an older test asserting the old
  contract reds `unit` on a correct branch. Fix the stale test to the new
  contract, and derive the expected value from committed data (e.g. the params'
  `ref`) instead of a literal, so the next bump does not re-red it. Never
  "fix" this by loosening the assertion.
- **A GNU Make 4-only feature, red on macOS only.** The macOS runner ships GNU
  Make 3.81: `make --eval=...` dies on stderr and the target never exists, so a
  test comparing its stdout sees `''`. Feed an ad-hoc target through stdin
  instead — `make -s -f Makefile -f - <target>` with the snippet as `input=` —
  which every GNU Make supports and still expands the real variables.
- **A requirement with no `#### Scenario:`.** `make openspec-validate NAME=<n>`
  (bare `openspec-validate` exits 1 with a usage line; use
  `make openspec-validate-all` for every active change) fails with "must include
  at least one scenario". A scenario-less requirement usually hides an unverified
  claim — e.g. "`ci-unit` calls both targets" that no test asserted. Add the
  scenario **and** the real test it names, plus the guard clause the claim needs;
  prose alone re-reds later.
- **A network-latency timeout on the macOS runner.** The top-tier dry-run tests
  subprocess the real Hub with a fixed budget (~13 min) and pass locally in ~4
  min; on a loaded macOS runner they exceed it. Reproduce the single test
  locally first, then `gh run rerun <id> --failed` once the run is complete. Do
  not touch the code or the timeout for this.

## 5. Fork heads cannot publish engine images — do not chase it

`make push-engine` runs in every `engine-image-*` job, and GitHub downgrades a
fork PR's token to read-only against the base repo's packages, so the job ends
`denied: installation not allowed to Write organization package`. That is the
tracked fork-token case, not a defect in the PR: build and post-build test pass,
only the publish fails. A fork PR that moves an engine tag therefore cannot go
green; say so plainly instead of editing the workflow or the branch. Only a
branch carried in the base repo publishes.

## 6. Finishing a repair

Commit as `Andy Holst <andy.holst@protonmail.com>` (Conventional Commit subject,
body with Issue / Fix / Benefit / Technical, measured numbers). Rebase onto
`origin/main` (`--force-with-lease` on your own PR branch is allowed), push, then
append the same follow-up section to the PR body — the issue/wikis/spec must not
drift from the code. Never merge; the CI `auto-merge` job lands a green,
conflict-free PR.
