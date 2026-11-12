# Proposal: merge-checkbox-parity

## Why

PR #2509 was auto-merged into `main` as squash commit `49f0cc3be` whose commit text carries
**3 unchecked acceptance checkboxes** (`- [ ]`, measured: `checked=0 unchecked=3` in
`git show 49f0cc3be -s --format=%B`) — the architecture bot pasted the issue's unticked
`## Acceptance criteria` straight into its commit message, and no gate reads **commit content**
for checkbox state. The issue/PR-body pair is already locked (issue #2511's `acceptance-body-lag`),
but the third artifact — the text that permanently lands on `main` — was ungated. GitHub issue #2519.

## What Changes

ONE tick, three mirrors, two gates:

- A criterion is ticked once, at the moment its work is verified; the same ticked set mirrors
  into the PR body (existing gate) and, newly, into the implementing **commit messages**, so the
  squash text inherits it. The `closes #N` keyword stays the ONE automatic act that closes the
  issue on merge — closing is never a substitute for ticking, and closing twice is never done.
- New gate `commit-checkboxes` in `scripts/check_pr_hygiene.py` (subcommand +
  `make check-pr-commit-checkboxes`): the joined `origin/main..HEAD` commit text (bot ranges) is
  RED when it carries an unchecked `- [ ]` under an acceptance heading, and RED when the PR body
  declares acceptance items whose count is not matched by `- [x]` mirrors in the commit text.
- The `auto-merge` merge lane (`scripts/auto_merge.py::_merge`) runs the same check against the
  PR's live commit messages + live body before `gh pr merge`; a failure is a **deferral with the
  reason on the PR** (the existing one-comment-per-head deferral machinery), never a red run.
- Wired as a live-body gate in the `ci.yml` guard job, beside `check-pr-agents-line`, and classified
  in `scripts/issue_bot_gates.py::DEFERRED` with a reason (the `FAST_GATES` roster is the fixed
  #475 list — widening it is that issue's follow-up, exactly as `check-pr-closing` is classified).
- AGENTS.md gains the durable mandate: issue body, PR body and commit message carry the SAME
  ticked acceptance set before a merge is armed; every implementation commit ends with a ticked
  `Acceptance:` block; closing remains the single automatic act.

## Impact

- Affected specs: `merge-checkbox-parity` (new capability)
- Affected code: `scripts/check_pr_hygiene.py`, `scripts/auto_merge.py`, `scripts/issue_bot_gates.py`,
  `mk/gates.mk`, `Makefile` (.PHONY), `.github/workflows/ci.yml`, `AGENTS.md`
- New tests: `tests/test_pr_hygiene_commit_checkboxes.py` (runs inside `ci-unit`)
- No history rewrite: `49f0cc3be` and closed issue #2508 (measured fully ticked: 3 `- [x]`,
  0 `- [ ]`) stay as they are; the gate is forward-only.
