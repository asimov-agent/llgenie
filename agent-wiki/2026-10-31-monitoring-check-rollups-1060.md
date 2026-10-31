# Version the monitoring-check-rollups reference into the ci-pipelines-maintainer tree (issue #1060)

## Drift
The live ci-pipelines-maintainer profile carries `references/monitoring-check-rollups.md` — this
lane's CI rollup-reading, poll-budget, arm-read-back and red-classification procedures — but the
merged tree never did. The tree SKILL.md at `c64cebf0` references a `references/monitoring-check-rollups.md`
that `git ls-tree` showed absent: live→tree drift of the exact class #1060 was filed to close (and
#1200 closed a sibling). A new check-rollups lesson (the Makefile `--repo "$(REPO)"` shape-defect that
`test_repo_slug` caught on #1208) is also folded into this file, so versioning it carries the fresh
lesson into the tree too.

## Fix
Copy the live reference byte-identical (sha256 `2c26cb82…`) into
`agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/references/monitoring-check-rollups.md`
on branch `fix/1060-version-monitoring-rollups` off `upstream/main = c64cebf0`,
commit `fd7ef716`.

## Verified
`sha256sum` live == tree (`2c26cb82…`); `check_pr_authors --base upstream/main --head HEAD` OK
(Andy Holst); `check_docs change->note` reds until this note + `docs/changes.d` row are present —
paid, as the #1123 rule requires for a new `agents/**/skills/**` reference.
