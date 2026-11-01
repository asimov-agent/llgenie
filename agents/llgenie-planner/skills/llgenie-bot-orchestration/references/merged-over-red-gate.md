# Merged-over-red: verify a merge on the HEAD check-set, never mergeStateStatus

An llgenie PR can be MERGED (by the owner) while its **head-instance** check-set is red.
The merge-commit re-run sometimes clears it; when it doesn't, a red defect ships to `main`
(the #1382 class: 3 `test_agent_profiles.py` failures landed on main).

Measured instances: #1385 (merged `e91b42c9`, head `65fdf69b` = `ci-verdict`/`scope`/`guard`
failure + `linux` skipped; cleared only by merge re-run `41320696487`), #1374 (merged
`fd3efd67`, head `7ebff155` = `linux/unit` + `ci-verdict` failure), and the documented
#1309-#1321 range.

## Rule

Verify a merge **on the head-instance check-set**, not on `mergeStateStatus` and not on the
merge event (its `skipped`/`cancelled` semantics are the trap — `gh pr checks`'s `fail`
column lies about cancelled; a fully-green check list can still be `BLOCKED`/`REVIEW_REQUIRED`).

- Read: `GET /repos/{owner}/{repo}/commits/{head_sha}/check-runs` (the PR's head sha, not the merge sha).
- **`conclusion` is lowercase in the REST payload** (`"failure"`, `"success"`, `"null"` for in-progress). A
  filter written `.check_runs[]|select(.conclusion=="FAILURE")` matches nothing and reads as "no red at the
  tip" — the single most dangerous false-negative in post-merge verification. Compare case-insensitively
  (`select((.conclusion//"")|ascii_downcase=="failure")`) or group by `conclusion` first and see the actual
  casing; never eyeball a zero-length select as "clean" unless a `group_by(.conclusion)` alongside it shows
  no `"failure"` bucket.
- A head whose `ci-verdict` or `linux/unit` is anything but `success` was NOT gated green — even if closed.
- When you find a merged-red, measure the acceptance criteria **on `main` at the merge tip**, not on the PR diff (the diff is now main's).

A persistent `make` merge-gate check enforcing this is tracked as issue #1386 (CI-pipelines lane).

## Acceptance criteria that live in a FILE are read AT the merge sha, never from the working tree

Most merged PRs prove their acceptance in a file they changed (a workflow's `cron:` minutes, a `Makefile`
target, a CI step, a recorded baseline count). Verify that by reading the file **at the merge commit**:

```bash
git fetch origin main
git merge-base --is-ancestor <merge-sha> origin/main && echo "ON MAIN"   # landing proof, not a guess
git show <merge-sha>:<path>                     # content AS MERGED
git show <merge-sha> --stat && git show <merge-sha> --format=%B -s   # what the commit claims it changed
gh api "repos/<o>/<r>/commits/<merge-sha>/check-runs" --jq '.check_runs[]|"\(.conclusion) \(.name)"'
```

- **The local checkout is routinely behind `origin/main`** (owner-mediated primary clone), so grepping the
  tree can show the PRE-merge content and read as "the acceptance did not hold" when it did — or hide a
  regression as if it were still fine. `git show <sha>:<path>` is the only tree-independent read.
- `git merge-base --is-ancestor <merge-sha> origin/main` is the proof the merge is on main; a stacked PR's
  merge commit is not, and `state=MERGED` does not say which base it landed on.
- Record the criterion, the value you read, and the sha. Distinguish a **config/file criterion** (the intent
  landed: cron minutes moved, the gate step exists) from a **behavioural one** (it was exercised: a green gate
  at the tip). A merged config change with a green tip is both; a merged config change whose tip run never
  executed the new step is only the former — say which you proved.
- **Read what the artifact DOES, not just that it exists — the merged trigger can diverge from the body's
  stated acceptance.** A PR body can promise "scheduled twice-hourly + workflow_dispatch" while the merged
  workflow actually files no `schedule:` at all and instead hooks `workflow_run: <other-workflow>: completed`
  (a real, legitimate reason: the fleet's bot minute-budget is exhausted and a new cron would collide). The
  file is present and the intent is served, but the *trigger* differs from what the acceptance text says. Rule:
  when a "file criterion" is a trigger/schedule/threshold, read the `on:`/condition lines at the merge sha and
  compare them to the acceptance wording; if they differ, report it as **acceptance-met-with-a-different-trigger**
  — a precise owner-facing note, explicitly *not* a blocker and *not* a fresh defect — rather than "acceptance met"
  (which hides the divergence) or a filed issue (which over-rates a design choice).

## "The tip is red" — bind every failing run to its `head_sha` first

At a merge-commit tip, two different things can look like "main is red" and they need opposite handling.
Resolve each failing run's `head_sha` before concluding anything:

```bash
TIP=$(git rev-parse origin/main)
gh api "repos/<o>/<r>/actions/runs?head_sha=$TIP&per_page=20" \
  --jq '.workflow_runs[]|{name,id,databaseId,status,conclusion,head_sha}'
# for any failing id: is its head_sha actually the tip?
gh api repos/<o>/<r>/actions/runs/<id> --jq '{name,event,head_sha,conclusion}'
```

- **A `ci-verdict` run whose `head_sha` is an older, pre-merge PR head** is a post-merge RECHECK of that
  merged PR's own CI (the #1309-latitude pattern), not evidence the tip is bad. It re-evaluates the
  triggering run's head, so it keeps failing on a head the merge already superseded — report it as
  "recheck of `<old head>`, already handled", never as a fresh main red, and never file it.
- **A `ci-verdict` check attached to the merge commit can judge a DIFFERENT run than its own `head_sha`.**
  The workflow stamps its own run with the repo's current head but evaluates the `RUN_ID`/`HEAD_SHA` env
  it was triggered with — so a `ci-verdict` failure at the merge tip may be the verdict for a *sibling*
  PR's CI run entirely (measured: a verdict run stamped `d94d3280` whose `RUN_ID`/`HEAD_SHA` env pointed
  at `7ad820bf`, a different PR's red). Before attributing a merge-tip `ci-verdict` red to the merged
  change, read the job's env: `gh run view <verdict-run> --log | grep -E 'RUN_ID|HEAD_SHA'`. If `HEAD_SHA`
  is not the merge tip, it is a cross-run verdict — report it against the *other* head, never as main red.
  **Cheaper attribution first (no log pull):** resolve the failing check-run to its producing workflow run
  via `details_url` — `gh api repos/<o>/<r>/check-runs/<check_run_id> --jq '{name,head_sha,details:.details_url}'`.
  If `details_url` names a run whose evaluated head ≠ the merge tip, it is a cross-run verdict; only fall
  back to reading the run's `RUN_ID`/`HEAD_SHA` env when `details_url` is ambiguous.
- **Enumerate ALL non-success rows; do not key a dict by check `name`.** A commit's check-set carries
  duplicate rows (`merge` appears as N skipped entries), so building `{name: conclusion}` collapses them and
  can let a `failure` row vanish behind a same-named skipped row — you then read "3 skipped, 1 null" and miss
  the red. Print every non-`success` run as `conclusion | name | id` in a list, and cross-check the count
  buckets (`group_by(.conclusion)`) against it; a `failure` bucket with no named failure row means the dict
  collapsed it. Also: `conclusion` is lowercase in REST (`"failure"`, not `"FAILURE"`) — a
  `select(.conclusion=="FAILURE")` filter silently matches nothing.
- **`[ci-scope] NO DECISION` is red even at 0 failures.** A run that published no `ci-scope-decision`
  artifact leaves its skipped legs `no-verdict` ("N jobs unaccounted for — 0 failures is not a verdict")
  and the verdict job FAILS by design. Do not read that as "no failing test": the cause is the missing
  decision artifact (usually a red `scope`/`guard` leg), so trace the deciding leg, not a test count.
- **The tip's OWN `ci.yml` run failing concrete jobs** (`linux/lint` at `make ci-lint`, `linux/openspec`
  at `make ci-openspec`) is a genuine red that needs an incident. Name the failing **step** from the jobs
  payload (see `verifying-lane-claims.md` §7 — never grep the raw log), then check whether the cause
  predates the most recent merges: `git merge-base --is-ancestor <suspect-commit> origin/main` plus a
  local reproduction of the named gate (e.g. `make check-docs`) separates "newly broken" from "has been
  red since the gate landed, and nobody filed it".
- A red that is pre-existing but untracked is still your incident to file — "it predates today's merges"
  is attribution, not an excuse. Route it to the lane owning the failing surface (docs-alignment gate →
  documentation lane; workflow/gate design → ci-pipelines), with the run id, the failing job+step, and
  the commit that introduced it.

## Cancelled-with-zero-jobs is a non-verdict: not red, not green

A merge-tip run can conclude `cancelled` with an **empty job list**. That is neither a defect nor a
pass: runner starvation / queue eviction means the matrix never executed, so there is no failure leg
to attribute and nothing to file.

```bash
gh run view <id> --json status,conclusion,jobs \
  --jq '{run:"\(.status)/\(.conclusion)",jobs:[.jobs[]|"\(.name) \(.conclusion//.status)"]}'
```

- `conclusion:cancelled` + `jobs: []` ⇒ record the disposition on the merged PR's issue ("merge-tip run
  cancelled, zero jobs, matrix unproven — runner condition, no incident") and re-load the sibling live
  pipeline on the next pass. Do NOT file an incident (there is no failing leg) and do NOT report "green at
  the merge tip" (the matrix never ran). When the change is docs-only and its governing docs gate was green
  at head, that residual is evidence for the runner/gate tracker, not a new finding.
- `conclusion:cancelled` WITH completed jobs where some are `failure` ⇒ still red (worst-job rule); the
  cancellation happened after the verdict landed.

## Merged-red: check for an existing tracker before filing another issue

A PR that merges over a red head is not automatically a *new* incident. First map each failing leg to an
owning issue: if the failing leg is already the subject of an open un-owned-red tracker (or derives from
it — `ci-verdict` failing because `linux/unit` failed), the correct action is **evidence accretion on that
tracker**, naming this merge sha and head, plus the concrete rubric consequence (e.g. "the gate's
required-status list may name only legs that are green at the tip, not this red one, until its tracker
lands"). File a fresh issue only for a leg with no owner. Say explicitly that the diagnosis was not
duplicated.

## A run's verdict is its WORST job, and it lands before the run finishes

Do not read a merge-commit re-run as undecided because its top-level `status` is `in_progress`,
and do not verify a merge against the two or three gates you happen to care about. The run is
RED the moment any single job concludes `failure`; the other legs still running change nothing
about that verdict.

```bash
gh run view <id> --json status,conclusion,jobs \
  --jq '{run:"\(.status)/\(.conclusion)",jobs:[.jobs[]|"\(.name) \(.conclusion // .status)"]}'
```

- Any job `failure` ⇒ the run is red. Quote the failing **job name** and the gate it runs; a
  `conclusion:""`/`in_progress` at the run level is not a stay of execution.
- Verify the merge against the **whole job matrix at the merge-commit sha**, not a subset. A
  "gate-green" report that checked `check-docs` + `check_agent_profiles` but never looked at
  `linux/openspec` is how a red main gets reported as green — say which jobs you actually read.
- The merge-commit re-run at `head_sha == origin/main` **is** the post-merge verdict for main.
  `gh run list --workflow CI --json databaseId,headSha,status,conclusion` filtered to the tip
  sha gives it directly; do not substitute a PR-head check-set for it.

## A live main-red outranks queued non-gate work — escalate, never park it

When the failing run is at the merge tip (main itself), the owning issue is an **incident**, not
backlog. If the defect already has an issue, it goes to the **front** of the implementer queue —
ahead of any queued nit whose gate is advisory (planner-live fold drift, note polish, refactor
comfort) — and the escalation comment names the run id, the failing job, the merge sha and that
**main is red**, addressed to the owner.

- A live main-red that was filed and then queued *behind* a non-gate item is the same defect as
  not filing it: the board stays red until something unrelated lands first. Re-order at once.
- The escalation asks the owner for the one decision only they can give (confirm the re-order, or
  a different route) rather than waiting for the queue to drain.
- Say plainly that the merge was not yours (owner/`asimov-agent` merges) **and** that your own
  post-merge check missed the leg — the correction is the evidence, not a defence.

## Re-running acceptance at the TRUE tip, not the lane's cited sha

A lane's post-merge verification ("both red tests now PASS on main @ `<sha>`") is measured at whatever sha
that lane fetched. `main` advances between its measurement and yours, so the report can be one or more
merges behind. Never repeat "passes on main" — re-run the named tests yourself at a FRESHLY fetched tip:

```bash
git fetch origin main && TIP=$(git rev-parse origin/main)
git worktree add /tmp/wt-verify "$TIP"     # clean checkout of the true tip, not the lane's tree
```

Run the repo's own test invocation, not a host `python`. The local/agent venv frequently has no `pytest`
(`No module named pytest`); the project ships a test image — use it:

```bash
docker run --rm -v /tmp/wt-verify:/repo -w /repo -e HOME=/root llgenie/test:latest \
  python -m pytest "tests/test_x.py::test_name" -q --no-header -p no:cacheprovider
```

- **`-k` applies across ALL files passed in one invocation.** `pytest a.py -k foo b.py -k bar` silently
deselects one of them (the last `-k` wins over the whole argv). Confirm each named criterion by its
**node id** (`file::test_name`) in a separate run so a deselected test can't masquerade as a pass.
- **Container runs as `root` (the default) leave root-owned `__pycache__`/`.pytest_cache` in the worktree.**
  `git worktree remove` and `rm -rf` then fail with `Permission denied` (passwordless sudo may be
  unavailable). Wipe the caches with a root container BEFORE removing the worktree:

```bash
docker run --rm -u root -v /tmp/wt-verify:/wipe -w /wipe alpine \
  sh -c 'rm -rf /wipe/tests/__pycache__ /wipe/scripts/__pycache__ /wipe/.pytest_cache /wipe/.git'
git worktree remove /tmp/wt-verify --force && echo clean
```

- **A change→note gate that reads `rc=0` at main needs no follow-up PR for an unpushed local note.** If
the file a merge edited already has an on-main `agent-wiki/` note covering it (e.g. the merge that
introduced the edit shipped its note), the gate passes at the tip and a locally-held note for the SAME
edit is redundant — say "no follow-up owed, do not push it," matching the no-churn-on-closed-vehicle rule.
