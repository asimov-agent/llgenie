# Admitting a new workflow, and triaging a red on your own PR

## 1. A new workflow file is not admitted until it is in the reactor roster

Adding any `.github/workflows/*.yml` to llgenie requires, **in the same atomic commit**, adding that
workflow's exact `name:` string to the `workflows:` list in `.github/workflows/run-failure-reactor.yml`.

Why: GitHub matches `workflow_run.workflows` against the producing workflow's `name:` **verbatim** and
takes no wildcard. An unlisted workflow's failures go to nobody. The repo enforces this with three
assertions in `tests/test_workflows_valid.py`:

- `test_the_repository_roster_matches_the_workflows_on_disk` — reports `unwatched: [<name>]`
- `test_this_repository_passes_its_own_gate` — `[workflows] 1 violation(s)`
- `test_check_exits_non_zero_on_a_violation_and_zero_on_this_repo` — bad/good exit codes

These land in the `linux / unit` job (`make ci-unit`), i.e. many minutes into a run. Add the roster
line before the first push; do not wait for the red.

Check before pushing, without pytest and without a venv — run the gate's own reader in-process:

```bash
docker run --rm -u root -e PYTHONPATH=/repo/scripts -v "$PWD":/repo:rw \
  -e HOME=/root -w /repo llgenie/test:latest \
  python -m pytest tests/test_workflows_valid.py -q
```

The pass bar is the gate's own output (`unwatched: []`), not a count of green tests — grepping a
`lineno:name:` prefixed roster print will hand you names with the prefix attached and produce a false
miss. Let `check_workflows` say it.

## 2. Reading the failing job's log

Get the step name from the job first (`gh api repos/{owner}/{repo}/actions/runs/{run}/jobs`), then
read the log:

```bash
gh run view --log --job <job_id> --repo asimov-agent/llgenie > /tmp/job.log
```

REST paths: the log endpoint is `repos/{owner}/{repo}/actions/jobs/{job_id}/logs`. The intuitive
`actions/runs/{run_id}/jobs/{job_id}/logs` returns **404**, and the `/logs` payload can be a
binary/zip redirect — write it to a file and read it as text via `gh run view --log --job` instead.

Never report a red from the check colour. A cancelled run reads `fail`; a job that cannot load has
zero jobs; a provider red reds its dependents' gates.

## 3. Pin the sha before you read any run

`gh run list --branch <branch>` returns runs from **every previous head** of that branch. An amended
head leaves the old head's red sitting in the list, and a stale-red is indistinguishable from a live
one by eye. Filter on equality with the current sha:

```bash
SHA=$(git rev-parse HEAD)
gh run list --repo asimov-agent/llgenie --branch "$BRANCH" --limit 20 \
  --json databaseId,name,status,conclusion,headSha \
  --jq '.[] | select(.headSha=="'$SHA'") | [.databaseId,.name,.status,(.conclusion//"")] | @csv'
```

Note `--jq` string concatenation: `databaseId` is a number and `.name` a string — `+` between them
fails with `cannot add: string and number`. Use `@csv`/`@tsv` or `"\\(…)"` interpolation.

## 4. Fixing on a pushed PR branch (amend, not a second commit)

The lane delivers one atomic commit per vehicle. A correction to a pushed branch is an amend, so the
`Issue:` / `Fix:` / `Benefit:` / `Technical:` body keeps describing the whole change:

```bash
git add <files>
git commit -q --amend --no-edit
git push --force-if-includes --force-with-lease origin <branch>
```

`--force-with-lease` alone protects against strangers, not against your own stale knowledge: fetch or
let `--force-if-includes` do it. Then prove the push landed — read all three back, because the PR's
`headRefOid` lags a forced update by seconds and a single read will show the old sha:

```bash
git rev-parse HEAD
git ls-remote origin <branch>
gh pr view <n> --repo asimov-agent/llgenie --json headRefOid -q .headRefOid
```

Only when all three agree may the re-push be reported. Then post one comment on the PR naming the
defect, the mechanism, the before/after proof and the new sha — the record must exist on the PR, not
only in this lane's memory.

## 5. Prove the guard catches the defect

Run the new/roster rule against the pre-fix tree and count the violations it names; then against the
fixed tree and count zero. A rule only ever run on the fixed tree has demonstrated nothing. State the
before-count and after-count in the PR comment.
