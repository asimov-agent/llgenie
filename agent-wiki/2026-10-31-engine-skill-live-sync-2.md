# Engine skill live-sync, second pass (skill grows after its first merge)

**What the change does.** `#1115` first versioned the engine-improver skill into the tree at `ca5f514e`
(merged as `0da8eeb5`). The live profile did not stop moving: tonight's session added two lessons to
`SKILL.md` and one reference grew. This second PR syncs the two drifted files verbatim into the tree so
the repo copy is again the whole live skill.

**The sync recipe that clears a profile row** (belongs in `references/agent-profile-soul.md`):

1. Enumerate `~/.hermes/profiles/<profile>/skills/*/` with sizes and *match the row by bytes/file-count* —
   a dispatch's `skills/trending-engine-sync/` was a stale label for what is actually
   `skills/llgenie-engine-improver/` (both ~127 KB, same row). The directory-name word is a claim about a
   filename, not a measurement.
2. Cut a fresh worktree off `origin/main` and copy the whole live directory (`diff -rq` must be empty).
3. Verify every reference `SKILL.md` names ships (the skill-reference-missing guard, #1152 class).
4. Attribute any failing test legs to their base (measure main at your fetch sha) so a pre-existing
   live-drift failure is not blamed on the new files.

**Verification.** `diff -rq` tree vs live = empty; 5 files, 130,729 b; SOUL.md already identical (no change).
LINT OK; skill-reference guard legs pass; the 9 remaining `test_agent_profiles.py` failures are pre-existing
on main (live-drift in other lanes), measured at the branch's base.

Filing under #1097; does not re-open the closed #1115.
