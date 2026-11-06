# llgenie-pr-merge-conflict: point the rebase skill at the failing-job-log-read procedure (#1849)

The `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/SKILL.md` references block now points
at the canonical read-the-failing-job-log-first procedure
(`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`,
merged via #1840). This is #1791-AC3's per-lane rollout for the rebase lane: a pointer only, no rewrite
— the lane's existing reproduce-on-rebased-tree discipline is kept verbatim. It names the run and head,
finds the failing job, reads that job's own log, quotes the failing step before attributing the root
cause to that gate, and reports green only off a completed run id + head sha. The pointer did not change
any rebase mechanic; it routes the lane's red-bot-gate reads to the fleet's canonical procedure so the
read-the-failing-job-log-first discipline loads at the moment the lane reports.
