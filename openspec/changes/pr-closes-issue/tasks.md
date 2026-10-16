# Tasks

- [x] 1. Write the proposal + spec for the closing rule (issue #324).
- [x] 2. `AGENTS.md`: the closing rule loses the loophole — a PR that implements an issue closes it
      (`closes #<n>`); a PR that implements only PART of an issue does not close it and names what
      remains as a linked work item; an issue is not closed by hand while a PR implements it. The
      "still end with the issue reference" sentence goes. The one-line restatement inside the
      message-mandate section is aligned to the same wording, so the two cannot drift.
- [x] 3. `scripts/check_pr_hygiene.py`: the closing rule is its own named constant
      (`AGENTS_CLOSING_RULE`) and its own required text — `check_agents_mandate` reports a missing
      closing rule under its own key (`agents-closing-rule`), separate from the message mandate's
      key, and the module docstring documents the finding.
- [x] 4. `tests/test_pr_hygiene.py`: a case per requirement — the baseline fixture carries BOTH
      required texts, a fixture missing the closing rule fails with its own key (and NOT the
      mandate key), a fixture carrying both reports neither, and this repository's own `AGENTS.md`
      carries the closing rule verbatim. 16 cases, all passing.
- [x] 5. Update the PR/issue body of this change so both state the closing rule and the reason for it.
- [x] 6. Verify: the touched suites in `llgenie/test:latest` (60 passed), `make check-pr-hygiene`
      (the guard catches the pre-fix `AGENTS.md` as a closing-rule violation and passes on this
      tree), `make lint`, `make check-wiring`, `make check-docs`, `make check-secret-output`,
      `make openspec-validate NAME=pr-closes-issue`, and CI green on the PR.
