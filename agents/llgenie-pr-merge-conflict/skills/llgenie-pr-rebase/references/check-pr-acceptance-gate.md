# check-pr-acceptance gate — body format that clears it

A PR that closes an issue whose `## Acceptance criteria` boxes are still `- [ ]`
reds `make check-pr-acceptance` (guard job). This is the designed acceptance
hold (#745 / #1644 / #1792): a PR may not close an issue a reviewer hasn't
ticked. Remedy is a reviewer verdict write-back (`acceptance_writeback`), OR the
PR body names the unticked criteria out of scope under a `## Not covered`
section. A rebaser must NOT invent the implementer's scope for them (#1706 — the
lane that opened the PR owns its acceptance content).

If you do write a `## Not covered` section (your own PR), the parser is strict:

- The heading must be **exactly** `## Not covered` on its own line. A subtitle
  after it (`## Not covered — …`) is NOT recognised; put any explanation as the
  first paragraph under the bare heading.
- Each out-of-scope bullet must **end with a `#<n>` work-item link**, with no
  trailing paren/period after it. `_declared_out_of_scope()` matches bullets
  that terminate in the issue reference.
- Each acceptance criterion's first ~3 lead words must appear in the section for
  the gate to treat it as declared.

The body is read LIVE (issue #1589): fixing the body alone clears the gate on a
rerun without a new commit. Rerun (`gh run rerun --failed`) only the guard/CI
runs that red on this gate.

## Attribution before you act

A conflicting PR, or one whose base is well behind, may red this gate on a
fresh head while the OLD head's guard passed — because the criteria-enforcement
is newer than the old run. Confirm by diffing old-head vs new-head guard step
conclusions; don't attribute it to your rebase or your body refresh. Measure the
linked issues' unticked count (`grep -cE '^-\s\[ \]'` on each issue body).
