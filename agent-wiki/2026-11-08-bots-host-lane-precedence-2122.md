This note is the `agent-wiki/` record for the docs-only change that records the host-lane-over-CI
precedence rule in `docs/BOTS.md` (issue #2122).

The owner rule (#2073) gives host lanes precedence over CI machinery on the host: the fleet's hands
are the host lanes, the CI workflows are support, and a red CI job is evidence, never an invitation
to repair the pipeline locally. `docs/BOTS.md` (issue #2122) gained a subsection beside the
host-agent layout that records:

- the precedence rule (host-lane working takes precedence on the host; CI workflows are support);
- the work-class → owning-host-lane ownership map (rebase → `llgenie-pr-merge-conflict`, product
  code → `llgenie-issse-implementer`, docs → `llgenie-documentation-maintainer`, workflow/gate/script
  → `llgenie-ci-pipelines-maintainer`, engine/serving → `llgenie-engine-improver`, test evidence →
  `llgenie-tester`, review verdict → `llgenie-pr-reviever`);
- the boundary that the planner files and dispatches, never repairs CI, and the two separate trails
  (owning-code-lane issue for the automation defect + host-lane dispatch for the unblock).

The user-facing language is a pointer + the table: the detail stays in
`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/host-lane-precedence.md`,
which the subsection cites as the source of truth, so the doc states the shape and the skill carries
the detail. Docs-only — no `agents/` skill, no `scripts/`, no workflow change.
