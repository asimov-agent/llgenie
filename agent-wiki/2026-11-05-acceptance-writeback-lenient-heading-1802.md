# Acceptance write-back lenient heading match (#1802)

`scripts/acceptance_writeback.py` (the #1644 seam that ticks `## Acceptance criteria` boxes
from a reviewer verdict) previously matched that heading **exactly**. A producer-authored,
human-readable heading such as `## Acceptance criteria (what closing means)` (the real shape in
#1800) made the seam raise `BodyError: the body has no '## Acceptance criteria' section` — even
when every criterion was genuinely proven and byte-exact on `main`. The generic message read as
"the criteria aren't there", so a merged-and-proven issue sat at `0/5` on the wire with no canary
and no actionable remedy, and #1644's tick never landed.

This fix, measured at `37ab0621`:

- `acceptance_writeback.acceptance_items()` and `_bounds()` now match a `## Acceptance criteria`
  heading **by prefix** (`_is_acceptance_heading`), so `## Acceptance criteria (what closing
  means)` selects the section and ticks its boxes. `issue_body.section_body` stays exact-match
  (#745 canonical-form check) — the lenient match lives in the seam only, so the form gate is
  unchanged.
- When no acceptance heading exists at all, the seam now raises a `BodyError` whose message
  **names the headings actually present** (canary), e.g. `found headings: \`## Problem\`,
  \`## Technical\`` — absence is distinguishable from a spelling variant.
- The seam ticks only the acceptance section: a `- [ ]` under an earlier, differently-named
  section is never touched, and a suffixed heading is preserved verbatim (the write-back mutates
  checkbox lines, not headings).

Reproduced deterministically against the real #1800 body (`## Acceptance criteria (what closing
means)`, 5 boxes): `apply --proven 1..5` now rc=0 and ticks all five, where the exact-match seam
reds with `BodyError`. `tests/test_acceptance_writeback.py` gains coverage for the exact heading
still ticking, the suffixed heading ticking 1–5, an unrelated earlier checkbox surviving
untouched, the heading text preserved, and the found-headings canary. `issue_body.py` and
`changes_index.check()` are unchanged (no marker scan in the conflict-marker gate, per the
Technical note).

This closes the #1792 / issue-form failure class at the seam side: a proven merge always lands as
a ticked issue, and a non-canonical-but-harmless acceptance heading no longer strands `0/5`.

Branch: `agent/issue-1802-acceptance-prefix-match` from `37ab0621`. Changed: `scripts/acceptance_writeback.py`,
`tests/test_acceptance_writeback.py`, this note + fragment, CHANGES.md re-render. Closes #1802.
