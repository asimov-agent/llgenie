# agents(planner): fold the ten live-only bot-orchestration references live→tree — bundle standard #1273

The planner's live profile `llgenie-bot-orchestration/references/` holds **ten reference files the
versioned tree never had** (live 77 refs vs tree 67 at `fd3efd67`). Each is real content
(1,294–3,520 b) and none has any tree match — `git ls-tree` at `fd3efd67` shows 0 bytes for each.
The SKILL.md fold (#1374, merged `fd3efd67`) covered `github-issue-triage/SKILL.md` + the
bot-orchestration SKILL.md; this PR completes the same bundle to `tree==live` for the references
Directory (the standing bundle standard #1273).

The ten files (all added verbatim live→tree, `cmp` byte-identical at the fold head):

agent-profile-fold-cascade.md · autonomous-goal.md · ci-red-vs-host-only.md ·
claim-detection-and-parked-lanes.md · live-tree-fold-discipline.md · live-tree-fold-vehicles.md ·
owner-directive-to-issue.md · planner-idle-slack-and-no-padding.md · rebase-and-ambient-red.md ·
test-classification-before-dismissing-red.md

**Bundle-wide proof (measured 15:10Z at the fold head):** `for f in agents/llgenie-planner/skills/
llgenie-bot-orchestration/references/*.md; do cmp "$f" <live>/references/$(basename $f); done` — all
77 reference files byte-identical to the live profile. `tree==live` for the whole
`llgenie-bot-orchestration/references/` bundle plus the two SKILL.md files already folded (#1374).

**Gates:** `make -s check-docs` rc 0 (census gate OK), `lint` rc 0, `changes-index` rc 0, at the
committed head. Change-note pair ships in this PR (#1123).

`AGENTS:` preflight — base = origin/main `fd3efd67` (15:08Z fetch; read AGENTS.md at that sha:
small self-contained repo, make-target verification, ghost-gate discipline all honoured).
