# Several PRs red the same gate: shared root cause or per-lane?

When PRs from different lanes all fail the **same** check in the same window (same check name, timestamps
minutes apart), do not fan out one green-drive per PR. Three dispatches on one root cause burn three lane
runs and produce three conflicting fixes. Classify first, read-only.

## 1. Is main itself red at that gate?

```bash
gh api repos/<o>/<r>/commits/<main_sha>/check-runs \
  --jq '(.check_runs // .)[]|select(.name|test("unit|verdict";"i"))|[.name,.conclusion//.status,started_at]|@tsv'
gh api repos/<o>/<r>/actions/runs/<tip_run_id>/jobs --jq '.jobs[]|[.name,.conclusion//.status]|@tsv'
```

- Main's own gate **red or in-progress** at the same gate -> suspect a **shared root cause**. Dispatch ONE owner
  (ci-pipelines for an environment/pipeline cause) with the shared evidence, not one per PR.
- Main's gate **green at the tip** -> the reds are **per-lane**. The lane that opens a PR owns its CI until every
  gate is green; dispatch each opening lane, quoting the failing sub-check.

## 2. A shared gate name is not a shared cause

`make ci-unit` is the *gate*; it bundles `test-unit`, `skills-validate`, `check-registry`,
`check-strata-models`, `check-engine-params`. Several PRs red on `linux / unit` can red for unrelated reasons.
Read the failing **step**, then the failing **sub-check**: the job's `steps[].name` with `conclusion=failure`
gives the make target; the log tail names the exact test.

## 2b. Open vehicle ↔ open vehicle: measure the file-set overlap BEFORE dispatching the second one

Concurrent redness is usually the symptom; two live branches sharing one path is the cause. Before you dispatch
anything that touches a shared file, diff the *open* vehicles against each other (not only against merges):

```bash
for n in <open prs>; do
  gh api repos/<o>/<r>/pulls/$n/files --paginate --jq '.[].filename' | sort > /tmp/f$n.txt
done
comm -12 /tmp/f$a.txt /tmp/f$b.txt      # exact shared paths, per pair
```

A rule-mirroring change is the dangerous case: adding one standing rule to the canonical fleet block forces a
byte-identical mirror line into **every** `agents/<profile>/SOUL.md`, so that vehicle overlaps every open
per-profile SOUL change plus `agents/standing-rules.md` and `CHANGES.md`. With fleet-block-drift, the change-note
gate and the regenerated `CHANGES.md` all keyed to those same files, whichever lands first reddens the others and
concurrent pushes triple-fire CI on one file set.

Disposition: don't cancel anyone. Post a **land order** (e.g. the all-profile vehicle first, then the per-profile
ones, each rebased onto the prior merge before its own green run) on the board and in the owning lane's DM, then
re-verify each one merge-tree-clean at its new base (`git merge-tree` rc=0) after the prior lands.

## 2c. The inverse: several different red gate NAMES can be ONE cause

The mirror of §2 — do not treat each red name as its own defect when they share a decision path. A PR can show
`ci-verdict`, `scope` and `guard` all red at one head because one upstream decision never happened and each gate
simply refuses without it; nothing in that PR's diff is wrong. The tell: the three jobs' run ids are close in
time, they sit in different workflows, and the PR's own diff cannot plausibly break all three (a docs-only or
test-only patch red in `scope` + `guard` + `verdict` is nearly always this cascade).

When you reconcile such a PR on-issue, **map each red to the tracked issue that owns it** and say explicitly that
the reds are not a defect of this PR (name the class issue) so the reviewer does not read the cascade as the new
work failing. Simultaneously name the ONE thing that IS this PR's own to prove (its new behaviour's unit tests at
the head). A reconcile that lists reds without assigning ownership teaches the next reader to close a good PR.

## 2d. One matrix run, several failing CELLS: classify each from its OWN failing step, never inherit a sibling's root

The cross-PR rules above also apply WITHIN a single multi-cell run (an engine-build matrix is the recurring
case). Several cells can conclude `failure` in one run for **categorically different reasons**, and each routes
to a different owner. Do not lift one cell's root onto its siblings because they red in the same run, and do not
report "the run failed for <root>" as if it were one cause. Read each failing cell's own failing step and log,
then classify per cell:

```bash
gh api repos/<o>/<r>/actions/runs/<RUN>/jobs \
  --jq '.jobs[]|select(.conclusion=="failure")|.name+" -> "+([.steps[]|select(.conclusion=="failure")|.name]|join(","))'
for J in <each failing job id>; do
  gh api repos/<o>/<r>/actions/jobs/$J/logs --allow-escape-sequences \
    | grep -ciE 'pyproject|exclude-dependencies'                  # dependency-install class (a poetry/pin defect)
  gh api repos/<o>/<r>/actions/jobs/$J/logs --allow-escape-sequences \
    | grep -ciE 'No child processes|exit code 143|shutdown signal' # runner-kill class (infra, not the branch)
  gh api repos/<o>/<r>/actions/jobs/$J/logs --allow-escape-sequences \
    | grep -ciE 'failed to fetch anonymous token|403 Forbidden|writing layer blob' # registry-auth class
 done
```

A grep count >0 on one signature and 0 on the others in the SAME cell is the classification; quote the matching
error line with its cell + job id + head sha. Real example shape: one run had a `vllm-rocm` cell red on a
pyproject/dependency-install error, a `vllm-cuda` cell red with 0 pyproject hits but a SIGTERM/`exit 143` /
`make: *** wait: No child processes` runner shutdown after a long cold buildx, and a `tensorfold-cuda` cell red
on a GHCR `403 failed to fetch anonymous token` — three DIFFERENT owners (implementer dependency fix, an
infra/cross-cell monitor for the kill, the registry-credential lane for the 403). Folding them into one
"<dependency> root" would mis-route two of the three. Only fold cells that share a measured signature; split the
rest, and state "N failing cells, M distinct root classes" with each cell→class→owner mapping.

## 3. When the job log is unavailable, decide from facts that need no log

A zero-byte or degraded log fetch is not a reason to stall a pass. Two measurements settle most cases:

```bash
# each PR's base vs the live main tip
for n in <prs>; do gh api repos/<o>/<r>/pulls/$n --jq '[.number,.base.sha,.head.sha]|@tsv'; done
git -C <repo> rev-parse origin/main

# does a recently merged PR's diff intersect this PR's files?
git diff --name-only <old_main> <new_main> | sort > /tmp/merged.txt
gh api repos/<o>/<r>/pulls/<n>/files --paginate --jq '.[].filename' | sort > /tmp/pr.txt
comm -12 /tmp/merged.txt /tmp/pr.txt        # the paths that actually collide
```

A stale `base.sha` (main moved under the branch) reds `check-pr-base` **regardless of the gate the lane aimed
at**, so "gate cleared but still red" is usually the base, not the fix. One intersecting path (a `CHANGES.md`
each PR appends a row to) is the whole conflict surface; the branch's own files are clean. Hand that single
path to the rebase lane with both sides named: a rebase resolving only it keeps the rest of the patch intact.

## 4. State the classification with the evidence you read

Never upgrade an `in_progress` run into a verdict. Report as `measured at <sha>`, naming the run ids and job
ids you read: main's gate state, each PR's base sha, and the intersecting paths (or "no intersection").
