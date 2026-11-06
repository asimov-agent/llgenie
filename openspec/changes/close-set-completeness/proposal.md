# close-set-completeness

## Why

`make check-pr-closing` (issues #1329, #1417) validates the *adjacency* of the closing keywords a
PR body and its squash text chose, but has no guard for the reverse failure: a PR whose diff
materially fixes issue X while the body names X under a resolving verb (`resolves`, `fixes`,
`completes`, `repairs`) and grants a *different* issue the closing keyword. Issue #1628 is the
measured casualty: it fixed the #1582 truncation defect, closed only the descoped #1617, and left
the root-cause #1582 orphaned-OPEN. Closes of another issue do not bind a fully-resolved issue.

## What changes

- `scripts/check_pr_closing.py` gains `check_completeness()`: it scans the PR body and the squash
  commit text for resolving references (`fixes/resolves/completes/implements/repairs` + `#N`) and
  REDs when a named-but-unclosed issue is neither adjacent-closed nor on-record justified-open
  (`does not close #N because <reason>`). A bare `see #9` or a `## Not covered` remainder stays
  prose and is not a finding.
- `closing_references()` strips a negated close clause (`We do not close #1582 because …`) wholly,
  so it is never read back as an adjacent close; the squash/body close-set mismatch check then sees
  matching sets.
- `NOT_CLOSED` accepts first- and third-person on-record justifications in the repo's own voice.
- The `clos(e|es|ed|ing)` forms are excluded from `RESOLVING`: narrating that an already-closed
  issue was closed is background, not a claim this change resolves it.

## Out of scope

Adjacency grammar itself is unchanged (#1273/#1556/#1619). No gate or severity is weakened. The
`does not close #N` note is honoured, not added to the tracker (that stays the #1628 NOT_PLANNED
record).
