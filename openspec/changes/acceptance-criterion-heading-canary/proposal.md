# acceptance-criterion-heading-canary

## Why

`check_pr_acceptance`'s `claim-unchecked` finding only recognizes criteria under a
canonical `## Acceptance criteria` heading. Issue #1807 was closed (PR #1810) with all 5 of its
`- [ ]` boxes sitting under a non-canonical `## Fix (acceptance criteria)` heading — the gate printed
`OK` (green) even though every box was unticked. A closed issue that merges `- [ ]` must be *seen to be*
unmarked, or the honest "an issue that merges `- [ ]` stays `- [ ]`" contract (#745) is silently broken.

## How

Add a canary beside `section_body(body, "Acceptance criteria")`: when that section is empty but the
issue body still contains acceptance-like `- [ ]` checkboxes, scan for the headings that hold them and
report them by name (exit 1), instead of returning `OK`. The canonical `## Acceptance criteria` path is
unchanged — the canary never fires when the canonical section exists.

## Benefits

- A closed issue with unticked `- [ ]` under a non-canonical heading no longer verifies green.
- The gate names the offending headings so a fix is directly scoped.
- Canonical issues behave exactly as before; `issue_body.section_body` exact-match is untouched.
