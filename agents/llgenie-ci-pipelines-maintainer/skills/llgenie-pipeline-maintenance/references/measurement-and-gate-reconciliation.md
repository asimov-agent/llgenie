# Measuring a red, reconciling a stale head, and routing per-gate reds

Depth for the always-on rules: measure at the live head, distinguish a base-staleness
red from a code defect, and fix the gates this lane owns without touching another lane's.

## 1. Measure at the live head — a red is a claim about the sha it was read at

Before routing a red or treating a gate as failing:

```bash
# the PR's current head, base, and merge state (authoritative)
gh pr view <n> --repo asimov-agent/llgenie \
  --json headRefOid,baseRefOid,mergeStateStatus,reviewDecision

# every run at that exact head — including OTHER branches' runs that share a sha prefix
gh api "repos/asimov-agent/llgenie/actions/runs?head_sha=<full-sha>" \
  --jq '[.workflow_runs[]|{id,name,status,conclusion,head_branch,head_sha,created_at}]'

# the guard job's per-step conclusions (closing / agents-line / sync-line /
# openspec-change / acceptance / base) — read steps, not the job rollup
gh api repos/asimov-agent/llgenie/actions/runs/<run-id>/jobs \
  --jq '[.jobs[]|select(.name=="guard")|{status,conclusion,\n        steps:[.steps[]|{name,conclusion}]}]'
```

Rules that fall out:

- **A red reported at an older head can already be green at the live head.** If a lane
  routed a red before a rebase, a fix push, or a base merge, its read describes the past.
  Re-measure the current head, then reply with the reconciliation: the old head + the run
  it was read at, the current head + its gate conclusion. Do not route work off the stale read.
- **Confirm `head_sha` AND `head_branch` belong to the PR before citing a run as evidence.**
  A run at a different branch's sha is another PR's run. Attributing it to your PR is a real
  on-wire error that must be retracted with the true run named — not quietly reused.
- **Read the job LOG, not the status badge.** A cancelled run reads `fail`; a job that cannot
  load has zero jobs and every rollup reads clean; a producer red reds its dependents' gates.
  The failure line is in the failing step's log, never the colour.
- **A gate AFTER a failing sibling step reads `skipped`, not `red` — the earlier red halts the
  job.** `check-pr-base` sits after `check-pr-acceptance`; while the acceptance `#1644` hold is
  red, the base step is `skipped` and the base-drift is real but MASKED. Do not cite `skipped`
  as the failing step (measured #1874: run `42255199390` failed on acceptance with base
  `skipped`); the base red only surfaces after the acceptance hold clears and the rebase lands.
- **A late-delivered self-DM from a degraded session is stale — the on-issue Finish wins.**
  While the host channel was degraded a DM composed mid-degradation can arrive minutes late
  asserting something the wire has since contradicted (measured #1867: a DM saying "no PR
  pushed" arrived after the on-issue Finish had already recorded PR #1874 at head `a5bf076d`).
  Never re-implement or open a second vehicle off a late DM; the authoritative record is the
  on-issue/PR comment with a sha and a run id — a DM has no baseline to compare against.
- **Before designing a fix for a reported red, read the live head's commit log — the fix may
  already be landed.** A lane reports against the head it measured, which can be an INTERMEDIATE
  (pre-fix, pre-owner-commit) sha; the live head may already carry the exact remedy they
  recommended as a named commit. Run `git log --oneline <base>..<live-head>` (and
  `git log -S '<the changed shape>' --oneline -- <file>` to find who moved it) before you
  re-implement anything. Confirm by running the SAME failing test/gate in-container at the live
  head: if it is green, the red is RESOLVED and no PR is owed — reply with the proven resolution
  (e.g. `34 passed`) and the fix commit's sha, never a re-implementation. (Measured: a peer
  routed a `test_ci_images.py` allowlist red at `baefb1fb`; the live head `97abfafb` was the
  owner's own `test(ci-images): … closes #N` allowlist extension, and the whole file ran green
  there.)

## 2. check-pr-base — base staleness, not a code defect

`check-pr-base` reds when the branch's merge-base with its base branch is not the base tip:
foreign commits ride on top of the branch, or the base branch advanced past the branch's cut
point (another PR merged, moving `origin/main`).

Diagnose by ancestry at the live head, after re-fetching the base branch:

```bash
git fetch origin main
git merge-base --is-ancestor <base-tip-sha> HEAD && echo "contains base tip" || echo "stale"
git merge-base origin/main HEAD   # should equal the base tip when green
```

- If the head already contains the base tip's merge commit, `merge-base(head, base) == base`
  and the gate is green at that head — **no rebase owed**. The reviewer/lane reporting the
  red was looking at a pre-rebase head.
- When a rebase IS the remedy, a base-staleness rebase is only for a CONFLICTING board state
  and belongs to `llgenie-pr-merge-conflict`, never this lane (issue #1015). Reply with the
  measurement and let that lane route it. Do not rebase, force-push, or arm auto-merge.

## 3. check-proc-gate — the `# proc-allow:` marker must share the call's physical line

`make check-proc-gate` (issue #797) fails when a `subprocess.run` / `check_output` / `Popen`
appears in `scripts/` outside `scripts/proc.py` without an allow marker. The gate's
`ALLOW_RE` scans a **single physical line**: the marker must sit on the SAME line as the
`subprocess.run(` call, not on a preceding line and not on a continuation line. A refactor
that wraps the call onto multiple lines (adding a `timeout=` arg, splitting kwargs) silently
moves the marker off the call line and reddens the gate. Fix by collapsing the call to one
physical line with the marker appended, e.g.:

```python
return subprocess.run(args, capture_output=True, text=True, timeout=T).stdout  # proc-allow: <reason>
```

Verify with `make check-proc-gate` (rc=0) plus the unit shard before committing. This gate is
this lane's own to fix when the red is in a pipeline file.

## 4. A new workflow step `if:` reds the exact step-if allowlist test — extend the allowlist in the SAME commit

`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` collects every job- and step-level
`if:` in `ci.yml` / `pipeline.yml` and asserts each is in a FIXED allowed tuple (OS forms, the
`matrix.* != 'none'` row guards, and the documented event-scope form). Adding a legitimate new
step `if:` — e.g. gating `check-pr-base` to `github.event_name == 'pull_request'` so push-to-main
runs stop false-reddening — reds that test until the exact string is added to the allowlist
with a comment naming the gate and its issue. This is a shape-assertion on the OLD spelling:
before pushing any workflow-shape change, grep the suite for the shape you replaced
(`grep -rn "runner.os ==\|matrix.engine != \|github.event_name ==" tests/`) and extend the
assertion in the SAME commit rather than weakening the workflow. Prove it the guard-prove way:
the extended tuple keeps the whole file green (deterministic `34 passed`), and any genuinely
illegal `if:` outside the tuple still reds — a rule only ever run on the fixed tree has
demonstrated nothing. (Measured #1867: the gate fix `c911799c` + allowlist extension
`97abfafb` ship together; the intermediate head without the extension red the file.)

## 5. Don't merge, don't arm to force green

Fixes arrive as one atomic commit and a ready-for-review PR closing the issue it implements,
carrying `Issue:` / `Fix:` / `Benefit:` / `Technical:` and the `AGENTS:` line. The repo's own
auto-merge lands green PRs. Never merge, never weaken a gate, never arm auto-merge to clear a
red (#1088). Commit as `Asimov Agent <support@docondee.com>` or the author guard reddens.
