# check-pr-closing: an `agent/*` PR must close its issue in the body (#1329)

A merged PR that does not carry a GitHub closing keyword in its **body** leaves its issue OPEN
forever. GitHub's auto-close fires only when the keyword is ADJACENT to the issue reference
(`closes #1327`), and a keyword with markdown between (`closes **#1327**`), a bare `#N` in the title,
or a number only in the first-line prose does NOT close it.

Measured on main `010ea8d9`: PR #1328 (round-10 fold) read `Addresses and closes **#1327**`, merged,
yet #1327 stayed OPEN (`stateReason:""`, `closedAt:null`); PR #1326's first line `Fixes #1322`
closed #1322 correctly. The enforcing lanes' "cite the issue" guidance was unenforced prose.

## Gate

`scripts/check_pr_closing.py` (make `check-pr-closing`, run at the top of the cheapest CI job and in
the `scope` PR suite):

- reads the PR body (`--body-file`) and head branch (`--head`);
- for an `agent/*` PR head, fails RED unless the body carries the closing keyword adjacent to `#N`
  (`fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved` + whitespace + `#\d+`);
- a non-`agent/*` head is out of scope (owner pushes, charts, renovate bumps);
- always enforces the `AGENTS.md` mandate section, so deleting the rule is a red gate, not an edit.

The regex mirrors GitHub's parser: keyword then horizontal space then `#<n>`, nothing else between.
`closes:#1327`, `closes#1327` and `closes **#1327**` all MISS — each was verified to mirror GitHub's
actual non-close.

## Fixture-pair proof (also versioned as tests)

- `tests/fixtures/pr-1328-body.md` (the defect) + `agent/*` head -> **RED**
- `tests/fixtures/pr-1326-body.md` (the control) + `agent/*` head -> **GREEN**
- any non-`agent/*` head -> **GREEN** (out of scope)

`closes #N` in the body is now the enforceable contract, not guidance that sails through.
