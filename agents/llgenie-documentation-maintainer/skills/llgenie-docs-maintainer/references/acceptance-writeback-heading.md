# acceptance_writeback needs the EXACT `## Acceptance criteria` heading

## The trap

`acceptance_writeback writeback --issue <n> --proven 1,2,3,4,5 --verdict-ref "..."` refuses when the
issue's acceptance heading is anything but exactly `## Acceptance criteria`:

```
BodyError: the body has no `## Acceptance criteria` section
```

rc=1, raised at `scripts/acceptance_writeback.py:70` — BEFORE the verdict-ref is read. So rewording
the verdict-ref string, or "re-anchoring" the command, changes nothing: the failure is deterministic
and header-driven.

## Why

`issue_body.section_body(body, "Acceptance criteria")` matches the heading with an exact comparison
(`group(1).strip() == "Acceptance criteria"`). A suffix heading — e.g.
`## Acceptance criteria (what closing means)` — makes the section invisible to the seam.

## What CHECK=1 does and does not prove

`make ... CHECK=1` and byte-exact ref blobs verify the fold CONTENT. They do NOT tick the issue's
acceptance boxes. A merged PR that closes an issue with its criteria still `0/5` on the wire is the
#1792-class merge-completion gap (nothing scans the issue's checkboxes on close).

## What NOT to do

- Do NOT re-run a proven-deterministic failing command because the planner re-issues it with a
  cosmetically different verdict-ref — that is a loop, not diligence.
- Do NOT manually edit a CLOSED issue body (e.g. to canonicalize the heading) without WRITTEN
  authorization from the dispatching lane. Silence is not consent, and "not manual" applies to the
  tick as much as the fix.
- Do NOT fabricate a `5/5` `proven:` readback. Keep the wire truthful at `0/5`.

## The right move

1. Post the durable refusal evidence on the issue (real rc=1, the full error line, the heading).
2. File the deterministic seam fix as its own `agent:implement` issue: match `## Acceptance criteria`
   leniently (prefix) OR emit a found-headings canary — per the file-then-route rule (#1245), never
   same-pass implement.
3. Put a one-line decision gate on the issue and ask the dispatching lane, in writing, to pick
   either (A) authorize canonicalizing the heading then run the sealed write-back, or (B) let the
   seam-fix issue land. Then stand by — do not ping-pong.
