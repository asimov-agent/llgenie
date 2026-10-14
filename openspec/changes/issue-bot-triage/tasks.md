# Tasks

- [x] 1. Proposal + spec for reading the thread and deciding (issue #261).
- [x] 2. `dispatch`: fetch `--comments`, render the thread + the decision block into `issue.md`,
      and skip issues labelled `agent:refined` / `agent:closed`.
- [x] 3. `parse_verdict` + `apply_verdict` + the `apply-verdict` subcommand, with the two loud
      refusals (no `EVIDENCE:` for a close, no `REFINED:` for a refine).
- [x] 4. Makefile: `issue-bot-triage` (the Hermes review inside the agent image) and
      `issue-bot-verdict`, both phony and documented.
- [x] 5. Workflow: triage -> verdict -> implement/push/PR only on `implement`.
- [x] 6. Tests: the thread fetch and render, the decided-skip, the verdict grammar, the two
      refusals, and each outcome's argv (no PR from a refine/close).
- [x] 7. README + agent-wiki + this change, so #257's docs gate is satisfied by the change itself.
- [x] 8. Verify: the suite, `make check-docs`, `make lint`, `make check-wiring`,
      `openspec-validate NAME=issue-bot-triage`.
