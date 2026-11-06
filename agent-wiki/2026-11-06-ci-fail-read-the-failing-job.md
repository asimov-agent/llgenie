# The implementer lane's skill now teaches the failing-job-log-first red bot-gate sequence

Issue #1791: no bot skill taught "when your PR's CI fails, read the failing job's log, root-cause
that step, then fix". A 2026-11-05 fleet sweep showed lanes acting on CI *conclusions* they had not
read — #1785 forwarded a `check-pr-sync-line` red as unrelated drift (it was a one-line `SYNC:` body
omission in the implementer's own vehicle), and several PRs reported green off a pre-conclusion
state. This lands the procedure in a lane that actually loads it, versioned per #791.

**New reference**
`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`
codifies the mandatory sequence on a red bot-gate: name the run and head
(`gh run view --json status,conclusion,headSha`), find the failing job
(`gh api .../actions/runs/<id>/jobs`), read that job's OWN log
(`gh api .../actions/jobs/<job-id>/logs --allow-escape-sequences`) and quote the failing step +
`[step] FAILED` + Makefile target + run id at the real head BEFORE any fix dispatch or any
green/red/reviewable claim; attribute the root cause to THAT gate via the gate→defect map (#792
AGENTS, #845 base/check-pr-base, #1724 SYNC, #1329 closing, #858/#843 cancelled, #1792
acceptance-criteria self-red = reviewer-owned until the verdict write-back #1644). A green report
cites the completed run id + head sha with no `linux/*` or guard/scope row `in_progress`/`cancelled`.
An unretrievable log mid-run is reported as "error line not yet retrievable — unlocks at run
completion", never a fabricated cause.

**Pointer** in `containerized-repo-verification/SKILL.md` so the reference is discoverable from the
skill a lane loads.

The change is text-only under the lane dir + the openspec change dir + the change-note trio; it does
not alter any CI gate, test, or workflow. The fleet ships each affected lane's copy/pointer as its
own #791 vehicle.

Referenced: `agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`,
`agents/llgenie-issse-implementer/skills/containerized-repo-verification/SKILL.md`,
`openspec/changes/ci-fail-read-the-failing-job/`.
