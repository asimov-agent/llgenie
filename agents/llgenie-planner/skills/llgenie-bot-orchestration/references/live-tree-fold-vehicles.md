# Live→tree profile fold vehicles (recurring "round-N" folds)

When a lane's live profile (what the credential actually runs, under `~/.hermes/profiles/<lane>/`)
drifts above the reviewed tree (`agents/<lane>/...`), the fix is a **fold vehicle**: an issue + PR
that copies the live file into the tree byte-identical. It recurs round after round because the
live profile keeps growing between folds. Size-cap remedy when the lane SKILL body is what
overflowed: `agent-profile-sync.md`.

NOTE: the plan](SKILL.md) of this skill is itself past 100 KB, so new lessons land in
`references/*.md` — SKILL.md patches are refused by the size gate.

## Rules that held across every round

- **One vehicle per round.** A fold fixes the files it bound to at branch time. Live growing
  mid-run is not a failure and not a licence to widen scope — record the new delta as the *next*
  round's residual in the PR/issue comment and stop.
- **Bind to the sha you measured.** Name the live blob and byte size in the issue
  (`live <path> <blob7> (<N> B) is +Δ above tree <blob7>`). A size claim with no sha is a claim
  about a moment, not about the file.
- **Byte-identical, never "equivalent".** Acceptance is the same git blob hash in tree as in live,
  not a rewritten equivalent — a rewrite destroys the audit trail an incident report needs.
- **Reference-only once the body is at the ceiling.** At/over ~100 KB of `SKILL.md`, folds target
  `references/*.md` only; never grow the body. Moving rule prose *out* of the body is itself a
  versioned change (issue + PR, never a private edit).
- **Verify on `main` by blob, not ancestry.** `git rev-parse origin/main:<path>` must equal the
  recorded live blob. A squash-merged head is never an ancestor of `main`, so
  `merge-base --is-ancestor` proves nothing about a fold.
- **Owner merges mid-suite.** Merges routinely go through pending/failed legs. Do not re-run or
  "repair" merged content; the blobs on `main` are the fact and the tracker closes via the literal
  `Closes #n` keyword.
- **Never merge or arm** in the fold lane (#1088). Report a run id + head sha from a *completed*
  verdict only.

## Dispatch shape

Issue body: exact live path + blob sha + byte size, the tree blob it replaces, byte-identical
acceptance, `sync-agent-profile CHECK=1`, gold-gate list, change-note pair + regenerated CHANGES,
literal `Closes #n`, base = fresh `origin/main@<sha>` fetched at dispatch time. Add an explicit
out-of-scope line ("do NOT touch the SKILL body / other lanes' dirs") so the lane does not
helpfully widen the fold.
