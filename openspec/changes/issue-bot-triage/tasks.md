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
- [x] 9. Fix the two real-CLI bugs this change shipped with, found by running the dispatch against
      the live repo: (a) `gh issue view --comments --json ...` is REFUSED by `gh` ("specify only one
      of --comments or --json"), so every dispatch failed before it picked an issue — the comments
      now come from `--json` alone; (b) the forced-issue check compared the state against a
      lowercase `"open"` while `gh --json state` returns `OPEN`, so it refused every real issue.
      The fixtures now use the REAL values (`OPEN`/`CLOSED`) and a test scans every argv the
      dispatch builds for the flag combination the CLI rejects.
