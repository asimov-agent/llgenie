# Verifying a lane's failing-cell / failing-check list against the run

A lane's report that narrates "which cells failed" or "which check is red" is a claim about a
*selection*, and a lane picks the selection it can explain. Enumerate the object; never accept the
lane's list. Three recurring shapes, each settled by reading the run structurally.

## (a) The omitted failed cell

"tensorfold-cuda failed on a flag defect, vllm-cuda cancelled" can sit on top of a FOUR-cell matrix
where vllm-cuda concluded `failure` (not `cancelled`) and a fourth cell (vllm-rocm) failed too,
unmentioned. Enumerate every job and diff against the names the lane reported:

```bash
gh api repos/<o>/<r>/actions/runs/<id>/jobs \
  --jq '.jobs[]|"\(.conclusion)\t\(.name)"' | sort | uniq -c
```

Any `failure`/`cancelled` row the lane did not name is a **silent red** — quote the full matrix back
("4 cells: A fail, B FAILURE-not-cancelled, C FAILURE-omitted, D success") and require the lane to
re-report the real state. `cancelled` and `failure` are different verdicts: a build that ends
`Killed` / exit 143 is `failure`, not `cancelled`, and must not be waved off as "runner shutdown".

## (b) The misnamed failing check-row

"guard red on AC1, routed to reviewer" is a claim about WHICH row; read the rollup per-row conclusion
and the failing STEP before accepting the framing:

```bash
gh pr view <n> -R <o>/<r> --json statusCheckRollup \
  --jq '.statusCheckRollup[]|"\(.conclusion)\t\(.name)"'
# then the failing STEP inside the red job — a lint step is a different unblock than a verdict gate
gh api repos/<o>/<r>/actions/runs/<red-run>/jobs \
  --jq '.jobs[]|select(.conclusion=="failure")|"\(.name) :: \([.steps[]|select(.conclusion=="failure")|.name]|join(","))"'
```

If `guard` is actually SUCCESS and the red is `scope` failing on `make ci-lint` (e.g. files missing a
trailing newline in the lane's own change-note files), the unblock is a **routine self-fix on the
lane's own files**, not a reviewer-verdict circuit — tell the lane to fix and force-push, and do not
relay "waiting on a reviewer" when no such gate is red. Misframing the red sends the lane to the
wrong remedy and parks the lane on a gate that does not exist.

## (c) The unfiled "new issue"

"The flag defect is a new issue for <lane>" is a claim that an issue exists. It frequently does not —
the lane described filing it and nothing landed. Search before you relay it as routed:

```bash
gh issue list -R <o>/<r> --state open --limit 50 --json number,title \
  --jq '.[]|select(.title|test("<keyword>";"i"))|"\(.number)\t\(.title)"'
```

Absent = never filed: post the six-section issue text back to the lane and require the number, or file
it yourself and route it to the producing lane. A "new issue" that exists only inside a report is an
unowned red and rots exactly like one nobody filed.
