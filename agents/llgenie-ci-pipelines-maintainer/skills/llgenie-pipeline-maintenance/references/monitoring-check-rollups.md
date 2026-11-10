# Reading CI check rollups and polling a head

## Never read a rollup from a badge or a single status line

`gh pr checks <n> --repo <owner>/<repo>` prints `name / state / duration / url` per job. Read that
list and count the states at the head you care about:

```bash
gh pr checks <n> --repo <o>/<r> | grep -cE $'\tpass'
gh pr checks <n> --repo <o>/<r> | grep -cE $'\tfail'
```

A `pending` job is not green. A `cancelled` job reads as failure and is UNTESTED. A workflow that fails
to load contributes zero jobs, so every rollup looks clean — confirm the job you intended to gate on is
actually IN the list before declaring a head green.

## Check names contain spaces, slashes and parentheses

Names like `linux / unit` and `linux / top-tier (none)` break a shell `case` glob or a grep anchored on
the literal name. Extract the state by field instead of matching the name as a pattern:

```bash
gh pr checks <n> --repo <o>/<r> | awk -F'\t' '/^linux \/ unit/{print $2}'
```

## `gh pr checks --json` has no `conclusion` field — and `--jq` will not concatenate a bool

`gh pr checks <n> --json name,state,conclusion` fails outright with `Unknown JSON field: "conclusion"`
and echoes the valid set: `bucket, completedAt, description, event, link, name, startedAt, state,
workflow`. The verdict is already in `state` (`pass`/`fail`/`pending`/`skipping`). When you want the
API-shaped `status`/`conclusion` pair, read the PR object instead:

```bash
gh pr view <n> --json statusCheckRollup \
  --jq '.statusCheckRollup[] | .name + " = " + (.status|tostring) + " " + ((.conclusion//"")|tostring)'
```

`--jq` is type-strict: `"draft=" + .isDraft` aborts with `cannot add: string (...) and boolean (...)`.
Wrap every non-string field in `tostring`, and default nullables with `//""`. **A query error is the
query's SHAPE, never evidence the check is missing** — fix the field name or the cast and re-run; do not
downgrade to reading a badge, and do not conclude the tool is broken because the same error repeats on
every retry.

**`mergeStateStatus=BLOCKED` while a check is still running is not a red.** BLOCKED covers a review hold,
a required check `IN_PROGRESS`, and a behind base alike; the rollup decides. `guard=SUCCESS,
holds=SUCCESS, scope=IN_PROGRESS` is a LIVE PR whose verdict is pending — report it as standing, never as
failed and never as green.

## Reach a job id through the check-run's `details_url`, not a `runs?head_sha=` query

`gh api 'repos/<o>/<r>/actions/runs?head_sha=<sha>'` frequently returns an EMPTY `workflow_runs` array for a
fresh head (per-commit attribution lag) — parsing it then throws `KeyError: 'jobs'` and reads like a broken
tool. `gh run list` also eats a `--jq` flag after positional args, so `gh run list --jq ...` silently returns
the unfiltered table. The reliable route from a head sha to the exact job:

```bash
gh api "repos/<o>/<r>/commits/<sha>/check-runs" > /tmp/cr.json      # the rollup is always populated
JID=$(python3 -c "import json;d=json.load(open('/tmp/cr.json'));\
print([c['details_url'] for c in d['check_runs'] if 'unit' in c['name']][0].rsplit('/',1)[-1])")
gh api "repos/<o>/<r>/actions/jobs/$JID" --jq '{status,conclusion,started_at,steps}'  # job + step progress
```

The `details_url` carries both the run id and the job id (`/actions/runs/<RID>/job/<JID>`), so extracting
`<JID>` from it gives the live job without a `runs?head_sha=` query at all. Use the per-step list to answer
"is this stuck or just slow" (a `make ci-unit` step `in_progress` at 9 min is the normal ~12-min suite; a job
with no step started for many minutes is a runner-queue problem, see `runner-queue-diagnosis.md`).

## Keep every poll inside the tool timeout

A poll loop that outlives the terminal timeout returns a timeout error and you lose the loop's output.
Budget far under the limit (e.g. 30 iterations x 10 s at a 360 s timeout), break on `pass`/`fail`, then
re-poll in a FRESH call if the job is still running. Never background a sleep to beat the cap, and never
cancel a running job to "clear" a queue.

**The `make ci-unit` matrix runs ~10-11 minutes — do NOT try to cover it in one blocking call.** A loop
like `for i in $(seq 10); do ...; sleep 45; done` at `timeout: 520` sums past the foreground cap (the
hard caps are 420 s normal / 600 s max), so the call times out mid-loop and you lose the state you were
building. Instead: one cheap conclusion query per call — `gh api repos/<o>/<r>/actions/runs/<id> --jq
.conclusion` — and if it still reads `null`/empty, END THE TURN and re-check in a later one.

**`gh run list --json …` returns an ARRAY — a `--jq '{...}'` object filter on it fails with `expected an
object but got: array`.** That error is the query shape, not a missing run: it repeats identically on every
retry and reads like a broken tool. Either filter the element (`--jq '.[0] | {id:.databaseId,status,head:.headSha[0:8]}'`)
or keep the raw array (`--json … > /tmp/r.json`, then read it). The same applies to `gh pr checks`-style
listings and to `headSha[0:8]` slicing: slice the string, never the array. A ~11-minute
matrix legitimately outlasts several turns; polling it in a tight loop is the anti-pattern, and factoring
the failing-test summary out of `--log-failed` in the SAME call you get `failure` saves a whole reopen.

## A poll script must build URLs from a VALIDATED literal id, never from a command substitution

The most expensive poll bug in this lane: a watcher that does `RID=$(gh api .../runs --jq '.workflow_runs[0].id')` and
then `gh api ".../runs/$RID/jobs"`. When the first query faults, `$RID` receives the WHOLE JSON error body, and the
second call becomes `actions/runs/{\n "message": "Not Found" ...}/jobs` → `net/url: invalid control character`. The
loop then runs forever, logging a 404 wall that reads like a repo/permission problem when the real fault is the
interpolated body. Guard the id before you use it, and hardcode the run id you already measured:

```bash
RID=41560255088          # the id you measured; do NOT re-derive it inside the loop
ST=$(gh api "repos/<o>/<r>/actions/runs/$RID" --jq '.status' 2>/dev/null || echo error)
[ "$ST" = completed ] || { sleep 20; continue; }   # any non-completed/`error` value just re-polls
```

Reject a non-numeric id explicitly (`case "$RID" in *[!0-9]*) exit 3;; esac`) so an error body can never become a URL.
Fix a broken watcher by KILLING the old process and starting the corrected one — a live loop never self-heals.

## Report the run's CONCLUSION, not "in progress" — and never re-cite a superseded run

A repeated "CI in progress" self-report is how a lane misses its own concluded red (the run finished `failure` while
the lane kept saying `in_progress` and the planner had to correct it). Poll `.status` AND `.conclusion`: when
`.status=completed` read `.conclusion` (`success`/`failure`/`cancelled`) and the per-job conclusions, and if
`.conclusion=failure`, open the failing job's log in the same turn — do not restate "pending".

When you force-push an amended head, the OLD run's red is history: cite the run id that was created AT the new head,
not the pre-amend one. A planner dispatch that names the superseded head is answered with the live head's run id +
its per-job states, not by re-diagnosing the old run.

**A poller armed with hardcoded run ids keeps watching the SUPERSEDED run after a force-push.** Amend +
push creates NEW run ids at the new head; a watcher still looping the old `CI=<old>` ids reports the old
run's `completed/failure` as if it were the current verdict (measured: a re-armed script kept emitting a
stale `RED` tick from the pre-amend run while the new run was in progress with the guard step green).
After any amend/force-push: re-list at the new head
(`gh run list --branch <b> --limit 4 --json databaseId,status,conclusion,headSha`), confirm `headSha`
matches the pushed head, KILL the old poller, and re-arm with the fresh ids. Distinguish completed from
pending in the loop with `(.conclusion//"")!=""` — a job whose conclusion is empty is still running, not
passed.

**A MERGE retires every watcher armed on that PR — kill your own, and read a pre-merge intermediate's red as history.**
After a squash-merge the branch is deleted and new runs (a merge-tip re-run, a post-merge matrix) appear with
fresh ids, while watchers you armed on intermediate heads keep ticking for 15+ minutes and each exit dumps a
`scope=failure` or `CI=failure` line into the transcript. Three rules: (1) when a PR you watch merges, KILL
every watcher you armed on it (`process_manage` kill; expect `already_exited`, that is still the right call);
(2) a `failure` captured on an intermediate head that the final merged head fixed is HISTORICAL forensics,
not a live red — quote it as `at <intermediate sha>, cleared at merged <final sha>` and never route it;
(3) an `in_progress` tick from a post-merge re-run of an already-merged object has no bearing on the merge.
Measured (2026-11-05, #1751): five separate self-armed watchers each emitted a settled/failure line from a
superseded head after the squash-merge at `84e9684c`; the only correct action was killing them and reporting
the merged state, once.

## Arm, then read the arm back

`gh pr merge <n> --squash --auto` exits 0 even when it armed nothing (e.g. base is not the default
branch). The exit code is not the fact — read it back:

```bash
gh pr view <n> --json autoMergeRequest,mergeStateStatus \
  --jq '{arm:(.autoMergeRequest.mergeMethod//"NONE"),at:(.autoMergeRequest.enabledAt//"-"),ms:.mergeStateStatus}'
```

`ms=BLOCKED` with `reviewDecision=REVIEW_REQUIRED` is a review-only hold, not a failed arm. Do not
hand-merge; let the repo's auto-merge land it on approval.

**When every CI check reads SUCCESS and `ms` is still `BLOCKED`, read `reviewDecision` before calling it a red**
(`gh pr view <n> --json mergeStateStatus,reviewDecision`). `BLOCKED` + `REVIEW_REQUIRED` + an all-green rollup
means NO CI red remains on the owner's merge surface — the only hold is the reviewer gate, which is not this
lane's to clear (no arm, no merge, #1088).

## Post PR-level evidence as an ISSUE comment, not a review comment

`POST repos/<o>/<r>/pulls/<n>/comments` is the *review* comment endpoint and 422s without a diff position
(`No subschema in "oneOf" matched … "commit_id", "path", "position" weren't supplied`). For evidence that
belongs to the PR as a whole (a refresh report, a measured verdict, a bookend), use the issue endpoint:

```bash
gh api repos/<o>/<r>/issues/<n>/comments -F body=@/tmp/evidence.md --jq '.id'
```

The PR number IS the issue number, so this lands on the PR conversation and is the durable record; a `gh issue
comment` special-case is unnecessary. Read the returned `.id` back as the post's proof.

## Confirm the merge itself

After approval, `state`, `mergedAt`, `mergeCommit.oid` and `mergedBy` are the record:

```bash
gh pr view <n> --json state,mergedAt,mergeCommit,mergedBy \
  --jq '{state,at:.mergedAt,sha:.mergeCommit.oid,by:.mergedBy.login}'
```

Use `.isDraft` (not `.draft`) when querying draft state — the wrong field name silently yields an empty
answer and makes a draft look like a ready PR.

## A new gh-command make target: grep the shape-guard before you push

The repo asserts the SHAPE of every Makefile recipe that calls `gh`. My #902 PR added a target with
`--repo "$(REPO)"` and `tests/test_repo_slug.py::test_no_recipe_passes_the_checkout_path_to_gh` redded it:
`offenders = [line for line in MAKEFILE if re.search(r'--repo\s+\"?\$\(REPO\)', line)]` — every `gh
--repo` must be the `$(GH_REPO)` slug, never the checkout-path `$(REPO)` form. The guard worked exactly
as built; my recipe was the defect. Fetch the guard BEFORE adding a gh-calling target:

```bash
grep -nE -- '--repo.*\$\(REPO\)' Makefile   # must be empty; use '$(GH_REPO)' instead
```

A correct fix redded by an assertion about the shape it replaced is YOUR defect, not a gate bug —
classify it case 2, fix the branch, and prove the guard (RED on the old line, GREEN on the new) before
claiming green.

## Classify a red: gate defect (this lane) vs code defect (implementer)

A monitor lane reads the failing job's log and MUST decide which of two things a red is before it
reports or acts:

1. **Broken pipeline/gate** — the gate itself is wrong, misfires on valid input, or cannot load. This
   lane opens the gate-fix PR (fresh branch off the just-fetched `main`, one atomic commit).
2. **Code/test defect in the change under test** — the gate is working exactly as specified and the
   branch violated it. This lane reports the verdict + log to the planner/implementer and opens NO fix
   PR.

Read the failure at its source, not the check colour:

```bash
gh run view <run> --repo <o>/<r> --log-failed 2>&1 | grep -nE 'Error|FAIL|assert|over|now,' | head
```

**The ratchet/count-gate rule (the case most easily misread as a pipeline bug).** A gate that records a
COUNT of a thing it wants to keep shrinking (bare import roots, prose/decode debt, warnings) reds the
moment the branch ADDS one. Its log reads like `bare: N now, M recorded — … a new file adding its own
root is refused here`, then lists EVERY counted site. When the baseline stores only a count (not a
set), the gate cannot name the culprit — find the one the PR introduced by intersecting that list with
the diff:

```bash
gh pr diff <n> --repo <o>/<r> --name-only   # only a changed test/module can be the +1
```

That red is a **code/test defect (case 2)** — the ratchet is working as designed. Route it to the
implementer with the exact new line; **never 'fix' it by bumping the recorded count** (that defeats the
ratchet) and never open a gate-fix PR for it. Guard against the inverse: a red naming a DELETION on the
branch (`X is not indexed`) is a branch-local gap whose fix is restoring the row — classify the two
classify the two separately (addition→implementer, deletion→restore), report both, and let the owning lane act.

**A count-ratchet gate runs BEFORE pytest inside `make ci-unit`, so a green module probe says nothing about
it.** `check-import-roots` (the bare-import-root ratchet) is a make prerequisite of the unit target: a new
test file can pass its whole module in the container and still red `linux / unit` on that step. Before you
push a NEW test module, run the ratchet's CI subcommand yourself — read the real command out of the Makefile
first (`grep -n 'check-import-roots' Makefile`), then run it (`python3 scripts/check_import_roots.py ratchet`);
the sibling `check` subcommand is an unfiltered report that reds on a pristine tree and will mislead you
(§4 of `verification.md`).

**The sanctioned shape for a test that imports a `scripts/` module is the packaged import through
`tests/conftest.py`, never a module-level `sys.path.insert` plus a bare import.** `import scripts.<mod> as x`
resolves through the one import root conftest installs; `sys.path.insert(...)` + `import <mod>` adds TWO new
roots and is refused. When the gate names your file at two lines, that pair is the tell — replace both with
the packaged import, then re-run the ratchet (expect rc=0) and the module's tests.

## A third class: a pre-existing red on `main` that reddens EVERY PR

Not every red is this lane's gate bug (case 1) or the branch's defect (case 2). A gate that reads a
file FROM `main` — `docs/ARCHITECTURE.md`'s `measured at <sha>` census pointer, a shared table, a pinned
baseline — can go red on `main` itself, and then EVERY open PR inherits that red regardless of its diff.
Three signs together confirm it is external:

- the failing step lives in a file your `git diff --name-only` does NOT touch, and the same check passes
at your own HEAD (e.g. your HEAD's pointer is a real ancestor while `main`'s is not);
- the IDENTICAL gate reddens on an unrelated open PR (`gh pr checks <other-n> | grep <gate>`);
- the failing log names a value that is wrong at `main`, not at your base.

The decisive probe (do this before assigning blame): export pure `main` to a scratch tree and run the
failing test there. If it reds on a checkout with NONE of your files, the red is external and your PR
adds zero net-new failure — say so with the run id and the failing-test list, do not fix it, route it to
its owner. Then re-run the SAME test on your branch: if YOUR former failure is absent from the branch's
failed list, that is the proof your fix worked and the residue is only the inherited red.

```bash
git archive upstream/main | tar -x -C /tmp/maincheck-<n>   # pure main, no branch files
(cd /tmp/maincheck-<n> && python -m pytest <the-failing-test> -q)   # reds ⇒ external
```

When all three hold: (1) report the red with the file:line, the sha, the run id, AND the unrelated PR
that reddens identically — that third fact is what proves it external; (2) check whether a canonical fix
already exists (`gh pr list --state open --search <topic>`, or the issue/PR the planner cited) and route
the finding there; do NOT open a second fix. If a fix you already opened is closed as a duplicate, leave
it closed — re-cutting `main`'s shared file a second time is the duplicate the board rejects. Never fold a
`main`-wide fix into an unrelated PR: its diff must stay exactly the change under review.

## "My tests pass" is NOT "the PR is green"

The decisive verification is the PR's CI at its head, never your local or container suite. A locally
green suite plus a red `scope` / `linux/unit` leg is a RED PR: do not arm, merge, or claim completion.
State the attribution honestly — what your diff does and passes, what the external blocker is, and that
the PR goes green once that blocker merges and the branch re-runs. Claiming completion while a required
check is red is the exact overclaim the completion-integrity guard rejects; report standing, not victory.
