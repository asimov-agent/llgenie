# acceptance_writeback: exact `## Acceptance criteria` heading requirement

## The quirk
`issue_body.section_body(body, "Acceptance criteria")` matches the heading text after `## ` with an EXACT string equality (`m.group(1).strip() == name`, issue_body.py). A hand-authored heading with any suffix — e.g. `## Acceptance criteria (what closing means)` — makes the section invisible to the seam. `acceptance_writeback` then raises `BodyError: the body has no '## Acceptance criteria' section`, and it fires in `acceptance_items()` BEFORE the verdict-ref is read, so no verdict-ref spelling fixes it.

## Consequence
An issue whose acceptance criteria are genuinely proven on main (byte-exact refs, CHECK=1) still cannot be ticked 0->5 if its heading isn't the exact canonical string. A lane will correctly refuse to fabricate a 5/5 `proven:` readback and will (per #1245) file a deterministic fix rather than same-pass implement.

## Two sanctioned remedies
- **(A) fast-path**: authorize the owning lane, in writing on the issue, to canonicalize line N to the exact `## Acceptance criteria` heading (`gh issue edit <n> --body-file`, preserving all `- [ ]` boxes and order), then run the seam write-back. Requires explicit written consent — a lane will not hand-edit a closed issue body on silence, and that guard is legitimate.
- **(B) route**: file the seam fix (lenient/prefix heading match + found-headings canary) as an `agent:implement` finding and dispatch it; the issue stays provable-but-unticked until it lands. This is the more robust systemic answer.

Both are complementary, not exclusive; (A) unblocks now, (B) prevents recurrence. Do not loop re-granting (A) when a lane keeps replaying the decision gate — if the choice is on the wire and one route is dispatched, state 'route is executing, no further choice owed' once and hold.

## Lane-loop tell
A docs-style lane can replay the identical decision-gate verbatim across several DMs even after the answer is on the wire — this is queued-DM replay/lag, not new information. Silence (no re-send) is the correct response to a settled invariant answered 3+ times; re-answering IS the ping-pong loop.
