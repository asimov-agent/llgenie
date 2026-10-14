# Tasks

- [x] 1. Proposal + spec for the backlog refiner (issue #263).
- [x] 2. `scripts/issue_refiner.py`: count, pick (spare capacity + eligibility), render, apply.
- [x] 3. Makefile: `issue-refiner-pick`, `issue-refiner` (the review, inside the agent image),
      `issue-refiner-apply` — phony, documented, and the test wired into the unit list.
- [x] 4. `.github/workflows/issue-refiner.yml`: schedule + owner-guarded dispatch, concurrency 1,
      the decision in code (no CI `if:` that can skip a job, #107).
- [x] 5. `tests/test_issue_refiner.py`: the budget query, the spare-capacity refusal, the
      eligibility skips, the rendered review input, the verdict grammar and its refusal, and the
      "one comment, one label, never a PR" argv.
- [x] 6. README + agent-wiki + this change.
- [x] 7. Verify: the suite, `make lint`, `make check-wiring`,
      `openspec-validate NAME=issue-refiner`.
