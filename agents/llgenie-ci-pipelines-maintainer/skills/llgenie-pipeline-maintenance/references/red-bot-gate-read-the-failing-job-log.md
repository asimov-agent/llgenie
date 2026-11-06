# llgenie-ci-pipelines-maintainer — #1791-AC3: the read-the-failing-job-log sequence lands a skill-surface pointer

## Read the failing job's own log before any claim

A red is a verdict, not a cause. Before any dispatch, green/red/reviewable claim, or fix this lane
makes, read the failing job's OWN log and quote the failing step with its run id + job id + head sha
— never a check-run `conclusion` colour alone, never a stale attempt-1 verdict, never an invented
cause while a heavy row is `in_progress` and its log is still unretrievable.

**Pointer (canonical, cross-lane — load it from the merged head):**
`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`
(landed by PR #1840, required by #1791-AC3). The identify-the-failing-job / read-its-log /
attribute-root-cause-to-THAT-gate sequence lives there. This lane's SOUL.md carries the discipline
verbatim; this section makes the same sequence loadable from this lane's skill surface, versioned
per #791. Keep the SOUL line — this is a pointer addition, not a rewrite.
