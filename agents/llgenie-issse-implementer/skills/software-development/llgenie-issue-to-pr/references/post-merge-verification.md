# Did my merged change leave main green?

After your PR is merged by the gate, verifying main is a SEPARATE measurement at the merge
commit sha. It is easy to conclude falsely in both directions: chasing a red that is not
yours, or declaring green from a run that has not concluded.

## A null arm readback is NOT proof the arm failed — it may mean it already merged

`gh pr merge <n> --squash --auto` returning 0 proves nothing about whether auto-merge armed.
A read-back of `autoMergeRequest:null` right after the call is likewise NOT proof it failed:
auto-merge can have **consumed the PR already** the instant its last gate cleared (e.g. the
required review landed between your `--auto` call and your read-back), so the PR is
`state:MERGED` with `autoMergeRequest:null` — a null readback then looks identical to a failed
arm. Read `state`/`mergedAt` BEFORE concluding "arm did not register" or re-issuing `--auto`:
re-arming an already-`MERGED` PR no-ops/fails, and a polling loop that keeps retrying the arm
reads as a broken arm while the deliverable already shipped. Only arm while `state:OPEN`.
Also `gh pr merge` has NO `--verbose` flag — a bogus flag exits 1 on the flag itself and masks
whether the arm would have worked; pass only real flags (`--squash --auto --match-head-commit`).

## Verify at the LANDED squash commit, not your branch head

When a dispatched issue turns out to be **already merged** (the issue is closed and a merge
commit whose squash subject names it sits on main), do not verify against your fork/branch
head — that head is the pre-squash tree and can differ from what landed. Measure at the merge
sha in a throwaway detached worktree:

```bash
wt=$(mktemp -d); git worktree add --detach "$wt" <mergeSha>
(cd "$wt" && <venv-python> -m pytest <acceptance-test> -q -p no:cacheprovider)
git worktree remove "$wt"
```

An acceptance criterion phrased "the test passes UNCHANGED" (no weakened assertion) needs a
second proof: hash the test file across the three shas — pre-fix base, landed merge, your head
— and confirm byte-identity (same line count, same assertion line) BEFORE running it:

```bash
for r in <preFixBase> <mergeSha> HEAD; do echo "$r $(git show "$r:<test-file>" | sha1sum)"; done
```

Issue-body acceptance criteria are literal ("quote the fresh completed run id", "line N
untouched"): tick each against a measured sha/run. "tests pass" is not a stand-in for the
whole list.

## Fetch a single job log from the job endpoint, not the run path

`gh api repos/O/R/actions/jobs/<job_id>/logs` returns the job's own log (job id from
`actions/runs/<run>/jobs`). `actions/runs/<run>/jobs/<job_id>/logs` is a **404** — a wrong
endpoint, not a missing log; do not read that 404 as "no log available".

`gh` refuses the log body with `the response contains terminal escape sequences` — pass
`--allow-escape-sequences` and redirect to a file, then strip ANSI before reading:

```bash
gh api repos/O/R/actions/jobs/<job_id>/logs --allow-escape-sequences > /tmp/job.log
# sed/`re.sub(r'\x1b\[[0-9;]*m','',txt)` the colour codes out, then grep the error line
```

The error line you want is the verdict's own attribution line, not the 404 and not the
escape warning: `[ci-verdict] run <judgedRunId> CI head=<judgedSha> conclusion=failure`
(then `[ci-scope] summary: ... success=N failure=M`). Compare `judgedSha` to your merge
sha. If it differs — and the corresponding check-run's `pull_requests[].number` names a
different PR — the red is that PR's run being judged on your merge commit's suite
(`event: workflow_run`), NOT a defect in your merge.

## A red at your merge sha is not necessarily your change

Many workflows run at a main sha. Besides the genuine `push`-event CI, CI-verdict / reactor
workflows (`event: workflow_run`) fire when ANY other PR's run finishes, and they are recorded
at the current main head sha even though the run they evaluate belongs to a different branch.
So `gh run list --branch main` at your merge sha can show `conclusion: failure` rows that will
never turn green and have nothing to do with your commit.

Filter and identify before believing a red:

```bash
gh run list --repo <owner>/<repo> --branch main --event push --limit 8 \
  --json databaseId,headSha,event,status,conclusion
gh run view <id> --repo <owner>/<repo> --json displayTitle,headBranch,event,status,conclusion,jobs
```

- The run whose `displayTitle` names YOUR change (the commit/squash subject) and whose
  `headBranch` is `main` is the one that measures your merge. Its `jobs[]` is the verdict.
- A red row whose `headBranch` is another lane's branch is that lane's artifact — report it to
  the owning lane if worth it, never "fix" or chase it as your own.
- `main` advances quickly; runs at LATER shas are other lanes' merges. Only the sha equal to
  your `mergeCommit.oid` speaks about your change.

### A `ci-verdict` reactor red at your sha can be a run-listing truncation, not your change

A recurring reactor failure shape reads:

```
[ci-verdict] FAILED: could not reach a verdict — branch main reports 2500 run(s) and one page
returned 50: a truncated listing cannot be a verdict
[ci-verdict] no `ci-scope-decision` artifact on run <id> — this run published no decision
```

This is the shared verdict gate choking on `main`'s run volume (a supersession/listing-guard
class owned by the ci-pipelines lane), NOT a defect in your diff: a docs/runtime/Dockerfile
change cannot make `main` report 2500 runs. Prove it is external before reporting: read the
failed log's `HEAD_SHA` — if it points at another lane's run or the error is the truncation
line above, it is not yours. After YOUR PR merges, the reactor may judge the now-**superseded
pre-merge branch-head run** (your old PR head sha) and report `no ci-scope-decision artifact →
no verdict → RED`; that is a branch artifact that merged away, not a regression at the current
tip — confirm by matching the judged run's `HEAD_SHA` to your former PR head, and check the
real `push`-event CI at main's tip is green before citing the red at all. And confirm at least ONE green `ci-verdict` concluded at YOUR
merged sha (`gh run list --repo <o>/<r> --commit <mergeSha>`); a green reactor sibling plus a
fully-passing PR check set (`gh pr checks <n>` all `pass`) is a complete task-relative verdict
even while a sibling reactor row shows `failure`.

Use object projections rather than string concatenation in `--jq`: `.databaseId` is a number,
so `--jq '.[] | .databaseId + " " + .status'` dies with `cannot add: number and string`, and an
empty projection then reads like "no runs" — a false premise, not a green.
`--jq 'map({id:.databaseId,sha:(.headSha[0:12]),status,conclusion})'` is safe.

## A red in the genuine main-push run at YOUR merge sha can still pre-exist on main

The filter above removes reactor/workflow_run rows and other branches' runs. But the real
`push`-event CI at your merge sha can red on a test that is failing on `main` **independently
of you** — an engine pin, a dependency image, a fixture another lane bumped. Do not accept the
red as yours just because the run measures your merge; attribute it by diffing the merge
commit against its PARENT (the main state you merged onto):

```bash
git show --no-patch --format=%P <mergeSha>            # squash merges have ONE parent
git diff --stat <parentSha> <mergeSha>                # what your merge actually changed
git show <parentSha>:<path/to/config-or-pin> | grep -i pin   # is the failing dep already there?
```

If the value the failing test keys on (a git pin, an image tag, a version) is **identical in
the parent and the merge tip**, the test fails identically without your change: the red
pre-exists on main and belongs to whoever landed that dependency. Example shape: a
publish-order test asserts `ghcr.io/.../<engine>:<pin>-cpu` exists; the pin is the same in the
pre-merge parent, so the image was simply never published by the lane that bumped it — your
doc/lint diff cannot publish a container image.

Name BOTH sides in the report: the task-relative change is verified (its own tests pass at the
merged sha), AND the pipeline is red for a proven external reason, with the parent-vs-tip
proof and the owning lane. This is the honest completion claim — "#N's acceptance verified,
pipeline red is <lane>'s unpublished dependency, evidence: identical pin in parent `abc123`."

## Do not loop on a standing integrity gate you cannot make green

A post-merge red keyed to CI can fire a completion/integrity gate repeatedly. Making and
verifying the *task-relative* change is the thing you owe; making an unrelated lane's image
appear on a registry is not, and is forbidden by the leave-another-lane's-artifact rule. After
you have (a) run the task-relative tests at the merged sha, (b) proven the red pre-exists via
the parent diff, and (c) routed it to the owning lane, STOP re-polling and re-posting — state
the two-part status above and end the turn. Chasing an external red in a loop produces churn,
not a green.

## Green means the run CONCLUDED, not that the PR's legs passed

A PR can be green on every leg and still have its own post-merge main-push run in `in_progress`
minutes later; the merge gate does not wait for it. Read `status` and `conclusion` on the
specific run and hold until `status: completed` with `conclusion: success`:

```bash
gh run view <id> --repo <owner>/<repo> --json status,conclusion,jobs \
  --jq '{status,conclusion,jobs:[.jobs[]|{name,status,conclusion}]}'
```

- `guard` + `ci-verdict` passing while `hf-live` (the live-network probe) is still running is
  the normal tail: the verdict job is decisive, the live-network job is just slow. Name the
  leg that is still pending rather than calling the whole run green.
- A `failure` on any job of a run whose `headBranch` is not `main` is not evidence against your
  change — attribute it by run id and branch first.
- A `verdict` check-run showing `failure` at your merge sha while a FRESH `ci-verdict`
  re-run at that same sha concludes `success` is a superseded straggler (the stale reactor
  judging an older/foreign run), not a live red. Enumerate check-runs with
  `gh api repos/O/R/commits/<mergeSha>/check-runs --jq '[.check_runs[]|{n:.name,c:.conclusion}]'`;
  if `linux / unit`, `ci-verdict` and the latest `verdict` are all `success`, the merged tree
  is green and the lone `failure verdict` is the foreign PR's report.
- While the merged commit's own `push`-event CI is still `in_progress`, `linux / unit` reads
  `PENDING` — that is "not yet measured", never a red. Hold for `completed` before any
  "landed green" claim.

Report the merge-commit sha, the run id and per-job conclusions; "merged, all good" without a
run id is a claim about time.
