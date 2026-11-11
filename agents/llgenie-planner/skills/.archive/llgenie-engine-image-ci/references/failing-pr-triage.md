# Repairing red PRs in llgenie

The recurring task: "go over the open PRs and make them work". Most open PRs are NOT red —
they are waiting on macOS runner capacity. Separate the two before touching any branch.

## 1. Triage: which PR is actually failing

```bash
gh pr list --repo asimov-agent/llgenie --state open --limit 50 \
  --json number,title,headRefName,isDraft,mergeStateStatus,statusCheckRollup
```

Read the rollup with these rules — each one has cost a wrong diagnosis:

- **Only `conclusion == "FAILURE"` (or `CANCELLED` / `TIMED_OUT`) is a failure.** An entry whose
  `conclusion` is empty/`null` is still pending; `statusCheckRollup` mixes check-runs and statuses,
  so filter on the field, never on the presence of a name.
- **`mergeStateStatus == "BLOCKED"` is not a failure.** It means a required check has not reported
  yet (usually the macOS half). `MERGEABLE` next to it confirms the diff is fine.
- **`SKIPPED` matrix placeholders are normal**: a job named `test-published-${{ matrix.engine }}-${{ matrix.variant }}`
  appears unexpanded when the whole matrix job was skipped (an unchanged engine). Not a red.
- **A run's own `status` lies.** `gh run list --commit <sha>` can say `queued` while 26 of that run's
  jobs are `completed` — one macOS job holds the run open. Ask the run for its jobs:
  ```bash
  gh run view <run-id> --repo asimov-agent/llgenie --json jobs \
    --jq '[.jobs[]|{n:.name,s:.status}] | group_by(.s) | map({status:.[0].s,count:length})'
  ```
  macOS (`macos-15-intel`) is the scarce runner; a PR can sit hours with every linux job green.
- Then read the failure itself, never guess from the check name:
  ```bash
  gh run view <run-id> --repo asimov-agent/llgenie --json jobs \
    --jq '.jobs[]|select(.conclusion=="failure")|"\(.name)\t\(.databaseId)"'
  gh run view --repo asimov-agent/llgenie --job <job-id> --log-failed | tail -60
  ```
  `--log-failed` is empty while the run is `in_progress`; check the annotations instead
  (`gh api repos/<repo>/check-runs/<job-id>/annotations`) or reproduce the gate locally.

## 2. Work in a worktree, never the user's checkout

```bash
git worktree list                     # a previous session's worktree for this branch may exist — reuse it
git worktree add ../llgenie-wt/<kebab> <branch>
```

For a fork-head branch, fetch it first (`git fetch fork 'refs/heads/*:refs/remotes/fork/*'`) and
check the PR's `headRepositoryOwner`: `origin` is the upstream (`asimov-agent/llgenie`), `fork` is
`andyholst/llgenie`, and the push target follows the head repo, not habit.

## 3. Iterate on ONE test file, not the suite

`make test-unit` is 12–20 minutes. To run a single file, copy the docker invocation `make` itself
would use and swap the command:

```bash
make -n test-unit   # prints the exact docker run line for this host
docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root \
  llgenie/test:latest python -m pytest tests/test_x.py -q
```

Keep the parent-repo mount from that printed line (`-v "<main checkout>":<same path>:rw`) when the
checkout is a worktree — `.git` is a file there and some tests resolve the parent.

## 4. Pitfalls that red a branch after the code is already right

- **A test that shells out to `make` must survive GNU Make 3.81.** macOS CI ships 3.81, Linux ships
  4.x, so a 4.0-only flag (`--eval=`, `--output-sync`, `-O`) passes on Linux and reds `macos / unit`
  with an empty stdout and the reason on stderr. Print a variable through a target fed on stdin,
  which every release supports: `make -s -f Makefile -f - print-var` with
  `input="print-var: ; @echo $(VAR)\n"`. Always assert with `(stdout, stderr)` in the message so the
  next break names itself.
- **When a change flips a contract, grep the test tree for the OLD assertion text before pushing.**
  A sibling test that still locks the previous behaviour reds `linux / unit` AND `macos / unit` on a
  correct implementation; the fix is to restate the test against the new contract, deriving expected
  values from the committed data (a params `ref`) rather than a literal, so a bump cannot red it.
- **A fork-head PR that changes engine params cannot publish its images.** `make push-engine` fails
  with `denied: installation not allowed to Write organization package`: a fork PR's token is
  read-only against the base repo's packages. Build and post-build test pass; only publish fails.
  This is the known open fork-token case, not a defect in the change — do not chase it, do not add a
  silent skip, and say so in the PR body. It clears once the branch is carried in the base repo.

## 5. Gates to run in the worktree before pushing

```bash
make lint check-workflows check-wiring check-docs check-pr-hygiene
make openspec-validate-all          # every active change, not just yours
make openspec-validate NAME=<change>
```

OpenSpec failure shapes worth recognising:

- `ADDED "<requirement>" must include at least one scenario` — every `### Requirement:` needs at
  least one `#### Scenario:` in Given/When/Then with a `- **Test:**` line naming the test.
- The mirror defect: a requirement whose claim no test asserts. When the scenario is missing, check
  whether the claim is ALSO unproven and add the guard + test (e.g. a wiring claim that nothing
  verifies), rather than writing a scenario over an unverified sentence.

## 6. Push, then sync the record

- Rebase onto `origin/main` first (`git fetch origin main && git rebase origin/main`); a rebased PR
  branch is never a fast-forward, so publish with `git push --force-with-lease <remote> <branch>` —
  and only on your own PR branch.
- Append a short **CI follow-up** section to the PR body: the failing check and its symptom, the
  root cause, the fixing commit sha, and the measured verification. Issue, OpenSpec change, code and
  PR body must not contradict each other after the repair.
- Then stop: CI's `auto-merge` job lands a green, conflict-free PR. Never `gh pr merge`.
