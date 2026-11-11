# Dispatching a reviewer, and telling a real red from a cascade

## Rule 1 — never dispatch a reviewer off `mergeStateStatus` alone

`ms=BLOCKED` + `reviewDecision=REVIEW_REQUIRED` looks exactly like "own gates green, only the
review is missing". It is not a licence to dispatch: the same PR can carry two or three genuine
own-gate FAILUREs underneath. Check the **full check-run rollup** before any reviewer dispatch —
head/base/mergeable/ms are not enough.

Minimum prefetch before dispatching a reviewer:

```bash
gh pr view <n> --json headRefOid,baseRefName,mergeable,mergeStateStatus,reviewDecision
gh api "repos/$REPO/commits/$SHA/check-runs" \
  --jq '[.check_runs[]|"\(.name)=\(.conclusion // .status)"]'
```

Any FAILURE in that list means **do not dispatch a reviewer** — the diff has no stable green
baseline to measure acceptance against, and the review is wasted. Route the red to its owner lane
instead (see Rule 3). A dispatch that skipped this check is a misfire: correct it out loud, tell
the reviewer to stand down, and record that the full-rollup check is now mandatory.

### Carve-out — the by-design `check-pr-acceptance` hold IS the dispatch trigger

One FAILURE is not a blocker: `check-pr-acceptance` red whose violations are **all the linked
issue's own `## Acceptance criteria` items still `- [ ]`** while the PR body `closes #<n>`. That is
the designed verdict-gated hold (#745/#1644), not a code defect — an implementer cannot tick its
own criteria, so the red persists by construction and clears only via a reviewer verdict followed by
`acceptance_writeback`. Read the guard log to confirm the shape:

```bash
gh api "repos/$REPO/actions/jobs/<guard-job>/logs" --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -E 'check-pr-acceptance|violation|still `- \[ \]`'
```

If every violation names a criterion of the *linked issue* (not the PR's own code/gates), dispatching
the reviewer is the correct forward step: ask it to review against the named criteria, issue the
verdict, and run `acceptance_writeback` to tick them. This is the opposite of Rule 1's default — the
red is the *reason to dispatch*, and the review is not wasted because the criteria are exactly what
it is reviewing. Distinguish this from a genuine own-gate FAILURE (lint, unit, base, scope, guard-diff):
those still stand the reviewer down. When in doubt, quote the violation text in the dispatch and say
explicitly "this red is by-design, verdict+write-back is the unblock."

**Classify the red BEFORE bouncing it to the implementer.** A verdict-gated `check-pr-acceptance`
hold is not an implementer task: the lane cannot tick its own criteria, so a correction demanding
"prove each AC" only earns a `## Verify` section + `AGENTS:` line in the body, which looks like
progress but clears nothing — the guard re-reds identically at the next head. Read the guard log's
violation shape first; if all violations are the linked issue's unticked criteria, route straight to
the reviewer. A body `## Verify` block or per-AC prose is evidence the reviewer weighs, never a tick.
When a previously-dispatched implementer does respond with a body `## Verify` + `AGENTS:` line and the
head moves, re-measure at the NEW head and re-classify: the surviving red may now be *only* the
verdict-gated acceptance hold, which is your cue to stop pressing the implementer and dispatch the
reviewer, not to re-post the same correction.

## Rule 2 — a reporting gate's red may be a CASCADE of another gate's red

Some checks do not test code; they render a verdict about *other* checks. The check-run summary
is where that shows:

```bash
gh api "repos/$REPO/commits/$SHA/check-runs" \
  --jq '[.check_runs[]|select(.name=="<verdict-gate>")|{conclusion:.conclusion,summary:.output.summary}]'
```

A verdict gate whose summary enumerates per-job outcomes (e.g. `verdict=red success=9 failure=1`
with the failing job named) is **red because that job is red**, not because of its own defect. It
clears the instant the underlying job does. Never file it as an independent product defect, and
never route it to a different lane than the failing job's owner.

Note: `gh api .../jobs/<id>/logs` can 404 for a job that only renders another run's verdict — the
log-free fallback is the check-run `output.summary`, which carries the same verdict table.

## Rule 3 — diagnose the ROOT gate, from the failing job's own log

The underlying red must be read from the failing job's log, not inferred. The common root hides in
the pre-push gate step, and the log names it verbatim:

```bash
gh api "repos/$REPO/actions/runs/<run>/jobs" --jq '.jobs[]|"\(.id) \(.name) \(.conclusion)"'
gh api "repos/$REPO/actions/jobs/<job>/logs" --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -nE 'FAILED|Error [0-9]|##\[error\]'
```

Two recurring roots and their remedies:

| Log line | Root | Remedy |
| --- | --- | --- |
| `[check-pr-base] FAILED: merge-base ... is not origin/main itself` | stale/diverged base | rebase the branch onto the current `origin/main` tip and re-push |
| `trailing bytes` / lint gate failure | the head is not the last no-op-free push | re-push a clean head |

Confirm a diverged base with one call instead of guessing:

```bash
gh api "repos/$REPO/compare/<main-tip>...<head>" --jq '{ahead:.ahead_by,behind:.behind_by,status:.status}'
```

`status=diverged` (ahead >=1, behind >=1) means main moved after the branch was cut — a rebase is
required, not cosmetic, and it is the single fix that clears every gate that cascades from it.

## Rule 4 — `gh --jq` concatenation gotcha

`"job=" + .id` fails with `cannot add: string ("job=") and number (...)`. Use interpolation:
`"job=\(.id)"`. Same for any numeric field. This silently costs a round-trip when a batch of
job-id reads comes back as one error.
