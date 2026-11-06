# llgenie-pr-reviever — #1791-AC3 failing-job-log-read pointer on the lane skill surface (#1849)

Landed the pr-reviever lane's vehicle for the #1791-AC3 multi-lane rollout tracked by #1849: the
fifth and final lane pointer to the canonical read-the-failing-job-log-first procedure.

The `llgenie-pr-reviever` lane skill (`agents/llgenie-pr-reviever/skills/software-development/llgenie-pr-review/`)
now carries a pointer block in `SKILL.md` and a dedicated
`references/read-the-failing-job-log-pointer.md` that names the implementer-lane canonical
`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`
(merged via #1840): on a red bot-gate, read the failing job's OWN log first — name the run id +
head sha, find the failing job, read that job's log verbatim, quote the failing step, attribute to
THAT gate via its gate→defect map, and report green only off a completed run id + head with no
`linux/*`/guard/scope row `in_progress`/`cancelled`.

The lane already enforced this discipline in SOUL/procedure; the rollout surfaces it so the pointer
loads where the review skill is read, per #791 versioning (one PR under `agents/<lane>/`, no
cross-lane edits). Pointer + change-note trio + this openspec change only — no product code,
scripts, or workflows (`make check-pr-openspec-change` presence half, #1807). This PR is
pr-reviever's single vehicle; it does NOT close #1849 (five-lane rollout — engine-improver #1851,
pr-merge-conflict #1850, security, ci-pipelines, pr-reviever).
