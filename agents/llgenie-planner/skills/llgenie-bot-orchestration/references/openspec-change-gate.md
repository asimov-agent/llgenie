# `check-pr-openspec-change`: the gate that reds BEFORE acceptance even evaluates

A PR that **changes product code** but adds no file under `openspec/changes/` and names no existing
change reds `check-pr-hygiene.py openspec-change` inside the `guard` job. Its message is exact:

> PR diff: this PR changes product code but adds no file under `openspec/changes/` and names no
existing change — AGENTS.md requires every change to start as an OpenSpec change: run
`make openspec-new NAME=<kebab-name>` before implementing, or add a `OPENSPEC: <name>` body line
naming the active change this PR implements against

**Fix (on the PR's own branch, by its own lane — never patch another lane's vehicle yourself):**
`make openspec-new NAME=<kebab-name>` and add a matching `OPENSPEC: <kebab-name>` body line. This is
the owner's OPENSPEC floor for any product-code change; no merge until it is green.

## It TERMINATES the guard first — do not read it as "acceptance"

The step runs early in the guard's chain, so its `Error 1` exits the job (typically exit 2) before
`check-pr-acceptance` produces its lines. A guard job whose log ends at
`make: *** [Makefile:<n>: check-pr-openspec-change] Error 1` is reporting the openspec gap as the
root, not acceptance. When you open the same job's log you may see BOTH: the openspec failure line
AND, further down or in a sibling run, the `check-pr-acceptance K violation(s)` lines. They are TWO
independent causes — report them as two fixes (openspec record + acceptance write-back), never as one
"guard red".

## The lane's "no CI run id yet, will report when it lands" is a stale framing

A lane often opens the PR and reports "dispatch just fired; I'll report the guard run id when the
check lands." Treat that as a claim about a moment. Measure immediately — the run usually HAS landed
and frequently reds hard within a minute of the push. If it red, the "pending" framing is stale by
however long you spent, and reporting it forward as "still pending" propagates a dead claim.

```bash
# head-first; a head_sha FILTER on the API needs the FULL 40-char OID or it silently returns []
gh pr view <n> --repo <o>/<r> --json headRefOid --jq .headRefOid
# read the fail/pending split from the rollup, then go read the actual job log
tok=$(gh auth token)
curl -sL -H "Authorization: token $tok" "https://api.github.com/repos/<o>/<r>/actions/jobs/<job_id>/logs" \
  | grep -iE "openspec|check-pr-acceptance|violation|Error [12]" | tail -30
```

- **Prefer `detailsUrl` from `statusCheckRollup` for the job id directly** — each red entry carries
  `.../actions/runs/<run>/job/<job>`, so you never have to reconstruct run→job by hand.
- **`scope` FAILURE beside a `guard` FAILURE is usually cascade, not a second defect** — a guard red
  means scope published no clean verdict (same downstream pattern as `ci-verdict NO DECISION`). Attribute
  by reading the failing step name, not the check name.

## Split the acceptance red honestly: satisfiable-now vs deferred-post-merge

If `check-pr-acceptance` also reds on a PR closing an issue the lane implemented, the guard reads the
linked issue's `## Acceptance criteria` and reports one violation per unticked box. **A lane's
"criterion N satisfied+x" is its own self-assessment, not a tick** — the wire still reads `- [ ]` until
a verdict-gated `acceptance_writeback` (#1644) runs. Never tick it yourself, and never read the lane's
claim as a passed box.

Partition the criteria before routing:

- **Satisfiable by this PR now** (the diff proves it, e.g. a matrix-aware cap present in the workflow;
  a change-note trio present) → route to a **reviewer verdict** then
  `acceptance_writeback --proven <k,...>` citing the verdict comment and the green guard step runs.
- **Honestly deferred post-merge** (a proof only obtainable after merge, e.g. a `push=true` live cell
  that is owner-guarded, or a criterion naming an artifact the merge produces) → leave it `[ ]` as the
  correctly-held box (the same pattern as a legitimately-unprovable criterion). Never fabricate a run id,
  and never tick it pre-merge. State the release condition that will prove it.

This is the same "close proves the issue was NAMED, not that its criteria were MET" distinction as
`pr-closing-gate.md`, applied when the PR is still open and the lane is asserting done-ness in prose.
