# Version the change-note-gate reference into the ci-pipelines-maintainer tree (issue #1060)

Issue #1060 — follow-up to the #1164 skill-tree merge (main `f75e54da`): the merged tree carried 11
references but not `references/change-note-gate.md`, which the live profile gained during the #1164
fix cycle (the #1123 change→note gate lesson). This PR versions that reference byte-identical to the
live profile, restoring the #1060 mandate that the versioned tree equal live.

## What was measured

Live profile reference `change-note-gate.md` (2,941 b) exists; the merged tree at `f75e54da` did not
carry it (verified via `git ls-tree`). Copied byte-identical (sha256 MATCH: `892b439f…`), committed
alone as `87bab031` on `fix/1060-skilltree-drift-change-note` (off `f75e54da`). The change→note gate
(issue #1123) correctly requires a note for a new `agents/<lane>/skills/` reference, so this note +
`docs/changes.d/<stem>.md` row are the paired record, exactly as #1187 did for its sync cycle.

Clears/advances the ci-pipelines-maintainer row of #1060; #1060 stays open for the other lanes' rows.
