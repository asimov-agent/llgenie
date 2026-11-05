# Acceptance write-back: a review verdict ticks the issue's boxes (#1644)

An issue's `## Acceptance criteria` — the repository's own definition of "done"
(issue #745: "a criterion a reviewer cannot tick is not one") — was never
transcribed after a PR merged: `scripts/auto_merge.py` had zero acceptance
write-back, and no PATCH `issues/{n}` existed anywhere. Measured at `75f85118`:
issue #1638, closed by PR #1640 at `0d5150a9` with all five criteria proven by
the reviewer's COMMENTED verdict (`5746530389`), still read **5/5 `- [ ]`
unticked, 0 ticked**; scanned closed issues #1638/#1634/#1622/#1594/#1633 ended
with zero ticked (their bodies never carried the tick state). A reader of the
closed issue alone could not tell which criteria were proven and which were
waived.

## The change

A review→issue-body write-back seam, `scripts/acceptance_writeback.py`, turns the
transcription into a checked state: on a reviewed-green merge, the lane holding
the COMMENTED verdict calls the seam with the issue number and the acceptance
items the verdict proved, and it ticks exactly those `- [ ]` items to `- [x]`
(`PATCH /repos/{owner}/{repo}/issues/{n}`), leaving every item the verdict did
NOT prove unticked and named (a trailing `- unproven: <n>. <text>` bullet). Each
tick carries provenance — reviewer + review id + head sha + run id
(`(proven: ...)` on the line) — so a reader goes from the tick to the measured
evidence.

The seam is driven by the verdict, never the merge: an auto-merged PR with no
reviewer verdict (#1088-class) ticks nothing — an un-reviewed merge stays honest
(boxes unticked). `tick_acceptance` is pure and stdlib-only (the unit suite
proves it on a bare host); the `gh api PATCH` is the thin wrapper. It renders
through `issue_body` (`section_body`/`missing`/`HEADING_RE`), keeping the
issue-body shape single-sourced (issue #745).

## Prove-the-guard

`tests/test_acceptance_writeback.py` pins it: a merged-and-reviewed issue carries
`- [x]` where the verdict proved it while an unproved item stays `- [ ]` and is
named; a full verdict ticks every box; an empty verdict (the #1088-class absence
of a reviewer) is a `BodyError`, never a silent no-op; an out-of-range position
and a body with no acceptance section are named errors; and the seam is
idempotent (a re-run does not double-tick or duplicate the naming bullet). The
gate is never weakened — the write-back is the only thing that mutates a box to
`- [x]`. Implements #1644.
