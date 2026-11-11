# API partial-settle reads: resolve at main tip, not at the PR field

Immediately after a merge or an issue close, the REST object can be **partially settled**:

- `gh api repos/OWNER/REPO/pulls/<n>` → `merged: true` while `mergedAt`, `mergedBy` and
  `mergeCommit` are all `null`.
- `gh api repos/OWNER/REPO/issues/<n>` → `state: closed` while `closedAt` and `stateReason`
  are `null`.

Do **not** read that as "contradictory wire state", as an incident, or as reason to withhold the
verdict. It is a settle race on derived fields, and the authoritative object is the merge commit
on the default branch:

```bash
gh api repos/OWNER/REPO/commits/<tip> --jq '{sha:.sha[0:9],parents:[.parents[].sha[0:9]]}'
```

A tip whose subject carries `(#<pr>)` and `closes #<issue>`, with a clean single parent equal to
the base you expected, **is** the proof the PR landed — the PR's own `mergedAt` field is not.
Quote the tip sha and the parent, not the field.

## The same asymmetry on lane reports

A lane that says "PR ready for review / awaiting owner merge" may be superseded by the merge
landing in the interval between its message and your pass. Verify the object (tip on main), not
the message's tense. If the object already landed there is **nothing to correct** — record the
receipt measured at the tip and note the lane's message merely predates the merge. Do not fire a
"you were wrong" reply at a lane whose report was true when written.

## When it is a real discrepancy

- `merged: true` but the default-branch tip does **not** carry the PR merge commit → the PR
  landed on a non-default base (`baseRefName`) or was reverted. Check `baseRefName`.
- `state: closed`, `stateReason: not_planned`, tip absent → genuinely closed unmerged; the issue
  needs a fresh vehicle.
