# `check-pr-acceptance` gained the found-headings canary the #1644 seam already had (#1811)

`scripts/check_pr_acceptance.py` reads a closed issue's `## Acceptance criteria` through
`issue_body.section_body`, which matches that heading **exactly** (issue #745's canonical-form
contract — the form gate is unchanged). A producer-authored, non-canonical heading such as
`## Fix (acceptance criteria)` (the measured shape of closed issue **#1807**) made `section_body`
return empty, so `_acceptance_items` produced `[]`, `acceptance_verdict` returned `[]`, and the gate
printed **`OK`** on an issue whose 5 acceptance boxes were all `- [ ]` — a close verified green
against nothing, structurally invisible to the verdict. #1800/#1802 gave the **write-back seam**
(lenient prefix match + a canary naming the headings present); the **gate** side had neither.

This fix, measured at the corrected head:

- `check_pr_acceptance` now calls `_acceptance_headings_elsewhere(body)` when the canonical
  `## Acceptance criteria` section is empty: if the issue body carries `- [ ]` checkboxes under a
  DIFFERENT `##` heading, the gate emits one `acceptance-heading-masked` finding (exit 1) **naming the
  headings found** (via `issue_body.HEADING_RE`, so gate and renderer agree) instead of silently
  passing. The unproven close is refused until the section is re-headed to the `## Acceptance
  criteria` definitive form and the proven boxes are ticked.
- `issue_body.section_body` keeps its exact-match behavior unchanged; the canary lives beside it in
  the gate, reusing the same `HEADING_RE`. No weakening of `check-pr-acceptance` or
  `openspec-validate-all`.
- A genuinely criteria-less issue body (no checkboxes anywhere) stays green — nothing to prove;
  a canonical `## Acceptance criteria` issue is judged exactly as today.

Measured red-on-old / green-on-fixed: the pre-fix gate returned `[]` (OK) on the `## Fix (acceptance
criteria)` shape and the new regression test reds; the fixed gate returns exit 1 naming the heading.
