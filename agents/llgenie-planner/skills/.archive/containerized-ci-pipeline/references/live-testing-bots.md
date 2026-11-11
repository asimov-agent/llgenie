# Live-testing the bot pipelines end-to-end (one at a time)

When the pipeline is a set of generated-`make` bot workflows and the queue is long, exercise
EVERY bot in its own live dispatch, one at a time.

## Procedure

1. **One dispatch at a time.** `gh workflow run <wf>` (or `gh workflow run <wf> -f key=v`
   for the deferred `inputs` path), then read that ONE run and its logs before moving to the
   next bot. Never fire several bots at once: an implementer, a reviewer and a filer share one
   issue queue, and cron/run can race on the same issue.
2. **Do not stop at green.** Read whether the bot's REAL verb executed or was SKIPPED. A run
   whose implement/review/fix step logged `skipped` (empty queue, `all-deferred`, probe found
   no label, dry-run) proves nothing about the pipeline — an empty queue is what hides a broken
   trigger for months. A run is a pass only when its substantive job ran AND reported a concrete
   outcome.
3. **Turn each structural defect into its own issue, then its own fix.** File the defect
   (deduped, with a signature), then fix it in its own worktree + reviewed PR per the
   `worktree-base-seam` reference. The run that found it never fixes it in place. Order the
   fixes by dependency (a missing trigger label starves every picker downstream, so that fix
   lands first).
   4. **Audit what actually happened, not the run's conclusion.** `gh run list`'s conclusion is
    the weakest signal — a "success" run can be `guard=success`, `pick`+`implement`/`review`
    `skipped` (a no-op). Read per-JOB step outcomes; they discriminate three shapes, and only
    a real verb executing is a pass:
    - **green no-op** — the substantive job `skipped`, the issue holds NO comment and no
      `ci/*-N` branch: the trigger or `pick`'s label admitted nothing (a hand-filed issue whose
      label no picker reads, an `issues: opened` event for a label the implementer does not
      admit). This is the defect, not an empty queue.
    - **picked-but-died** — `pick=success`, the verb job `failure` at a NAMED step:
      `gh run view <id> --json jobs --jq '.jobs[] | "\(.name)=\(.conclusion)", (.steps[] | "  \(.conclusion)\t\(.name)")'`,
      then `gh run view <id> --log-failed` (or `--log | grep -iE '##\[error\]|verdict=|Invalid'`)
      for the exact `##[error]` line. Everything AFTER the failing step being `skipped` (commit,
      push, PR, outcome comment) is the tell that ~20 min of model work was discarded.
    - **re-offered same issue** — two `<!-- <bot>-start: … -->` markers on one issue with no
      outcome comment and no pushed branch: each sweep re-picked it, ran the model, and died in
      the same place (the start marker re-announces the same branch name).
    Prove "nothing happened on the issue" before claiming a defect: `gh issue view N --json
    comments --jq '.comments|length'`, `gh api repos/o/r/branches --jq '.[].name'` (no
    `ci/*-N`), and `gh pr list --head ci/*-N`. Then file the defect with the run table as
    evidence — one row per run: id/URL, the issue it picked, the model verdict, the exact
    failing step and the `##[error]` line.

   ## Handling a flaky external gate on a bot's own PR

When your own fix-PR is green on every code check but blocked on a live-network gate (the
`live-smoke` type), classify BEFORE deciding what to do with it:

- **Green `guard` + `validate`, only `live-smoke` red on the external network step
  (e.g. Firecrawl→lightbrd reachability, `--require-hits` 0 hits)** — this is infra, not your
  code. A change touching `qa-validate.yml` + tests + docs only has nothing in it that could
  affect the Firecrawl/lightbrd path.
- **A different external step failing on each attempt** (attempt 1: one query timed out;
  attempt 2: Firecrawl returned 0 hits) is upstream degradation, not a flaky race on your
  runner. Deterministic checks green on every attempt is the tell that the code is sound.
- **The user's standing choice for this case: keep re-running the failed job in a bounded
  loop until upstream recovers and auto-merge lands it.** Do NOT ask to merge manually with an
  admin override, and do NOT skip ahead to the next bot leaving the PR unmerged — offer those
  only as alternatives, and only after the rerun loop has had a real shot.

Technique (each attempt = one `gh run rerun <id> --failed` on the SAME run id, then poll):

```bash
gh run rerun "$ID" --failed && \
  until gh run view "$ID" --json status --jq .status | grep -q completed; do sleep 15; done
gh run view "$ID" --json jobs --jq '.jobs[] | "\(.name): \(.conclusion)"'
gh run view "$ID" --json jobs \
  --jq '.jobs[] | select(.name=="live-smoke") | .steps[] | select(.conclusion=="failure") | .name'
```

A reusable bounded-loop driver lives in `scripts/rerun-flaky-gate.sh` — run it, report each
attempt (run id + each job's conclusion + the failed step name), and stop after N attempts so
you don't spin forever on a sustained outage. When it exhausts its budget the PR is still red:
come back to the user with the per-attempt trace rather than looping further.

## Pitfalls (each surfaced live; each a reusable rule)

- **A `make` call in a workflow step needs the job's `actions/checkout` to have run first.**
  The target can exist in the Makefile yet die on a bare runner with
  `make: *** No rule to make target '<t>'.  Stop.` — and every step after it is then SKIPPED,
  so the bot implements nothing while the run stays otherwise green. Decision/resolver steps
  that must run before the checkout (so they can gate it) are restricted to `gh` reads only;
  any repo-target call moves to its own step after the checkout, and fails loudly when its
  output file is empty. Guard with a CLASS test that scans every workflow for a step whose
  `run` calls `make` and asserts it sits past that job's checkout — and asserts the check is
  not vacuous (at least N make-calling steps exist).
- **Never pipe `make`'s raw stdout into `$GITHUB_OUTPUT`.** Make echoes every recipe line to
  stdout unless that target's recipe is `@`-silenced, so the first line a pipe sees is the
  echoed command — not `key=value` — and GitHub fails the whole step with
  `##[error]Invalid format 'python3 scripts/… '`, skipping every later step (push, PR, outcome
  comment). Capture with `OUT=$(make <t>)` and write parsed `k=v` lines, or silence the recipe
  with `@`. Guard with a CLASS test that flags ANY workflow step redirecting `make`'s output
  into `$GITHUB_OUTPUT` — it is the same class whether it is `tee >> "$GITHUB_OUTPUT"` or a
  plain redirect.
- **Prove a new regression guard FAILS on the old code before it passes on new.** Restore
  `git show origin/master:<file>`, run the test, confirm it goes red, restore the new version.
  A guard that only ever passes on the fixed code and never reddens the old one locks nothing.
- **A bot that keys its trigger/pick on a label must CREATE the label before filing.**
  `gh issue create -l <unknown>` returns 0 and lands the issue UNLABELLED (GitHub silently
  ignores a repo-unknown label), so the sweep/pick that scans by that label sees zero candidates
  and the whole bot no-ops while staying green. Create the label explicitly (idempotent), and
  file via a token with the Issues scope — an owner PAT scoped to Actions/Contents/PRs alone
  cannot create a label or comment, and its 403 (`Resource not accessible by personal access
  token`) is exactly how the drop happens in the first place.
