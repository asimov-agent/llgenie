# Version the ci-pipelines-maintainer skill tree into the repo (issue #1060)

Issue #1060 (row) — version this lane's live `agents/llgenie-ci-pipelines-maintainer/` skill
(`SKILL.md` + 11 references/templates) byte-for-byte into the tree, clearing the fresh
ci-pipelines-maintainer absent-from-tree row of #1060.

## What was measured

The versioned tree carries the live skill as edited during the #1060 population: the
`check-pr-authors` re-author remedy (a red `check-pr-authors` on a commit authored under a foreign
address is fixed by `git commit --amend --reset-author` on the branch's own allowed identity, then
`--force-with-lease`; verify with `check_pr_authors.py check --base origin/main --head HEAD`),
alongside the pre-existing pipeline-monitoring lessons (docs /* reference pages and the
`workflow-step-probe.py` template). Byte-identical to the live profile at branch head `72b46505`
(rebased onto `upstream/main` `6f49d645`).

This clears the ci-pipelines-maintainer row of #1060; it does not close #1060.
