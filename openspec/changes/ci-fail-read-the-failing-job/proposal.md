# Fix: codify the failing-job-log-first red-bot-gate sequence in the implementer lane's skill

## Why

No bot skill teaches "when a PR's CI fails, read the failing job's log, root-cause that step, then
fix accordingly". In a 2026-11-05 fleet sweep lanes repeatedly acted on a CI *conclusion* they had
not read: #1785's implementer forwarded the red as unrelated drift when the actual failing gate was
`check-pr-sync-line` (a one-line `SYNC:` body omission in the implementer's own vehicle); multiple
PRs reported green off a pre-conclusion state rather than a completed run's id + head sha. Each
misattribution costs a lane a full matrix round and routes the fix to the wrong lane. The owner's
standing instruction is explicit: read the failing job's log first, then fix.

## What changes

Adds a versioned reference to the implementer lane's skill
`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`
and a pointer to it in that skill's `SKILL.md`. The reference codifies the mandatory sequence on a
red bot-gate: name the run and head (`gh run view --json status,conclusion,headSha`), find the
failing job (`gh api .../actions/runs/<id>/jobs`), read that job's OWN log
(`gh api .../actions/jobs/<job-id>/logs --allow-escape-sequences`) and quote the failing step +
`[step] FAILED` + Makefile target, then attribute the root cause to THAT gate via the gate→defect
map (#792 AGENTS; #845 BASE/check-pr-base; #1724 SYNC; #1329 closing; #858/#843 cancelled). A
green report must cite the completed run id + head sha with no `linux/*` or guard/scope row
`in_progress`/`cancelled`. When the log is unretrievable mid-run, say "unlocks at run completion"
and never invent a cause.

## Who

llgenie-issse-implementer (this lane owns the versioned skill; the fleet ships each affected
lane's copy/pointer as its own #791 vehicle).
