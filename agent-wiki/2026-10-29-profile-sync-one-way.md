# Profile sync is one-way: a live-only edit is a named finding

**Issue:** [#968](https://github.com/asimov-agent/llgenie/issues/968) · **PR:** _this change_
(supersedes the unlanded attempt on `fix/968-sync-one-way`).

## What this changes

`make sync-agent-profile` copies the tree INTO the live profile — one-way. A live file that is
edited by hand after its tree copy was committed, and whose content differs, is no longer something
the tree can "catch up" to by re-taking it; that re-take laundered an unversioned edit into the repo
as a normal commit nobody reviewed. The gate now reports it as a `live-edited-not-tree` finding that
names the profile, both byte sizes and the remedy (commit the edit via an issue+PR under
`agents/<profile>/`, then `make sync-agent-profile PROFILE=<profile>` clears it).

## What was verified

- `test_a_live_file_edited_after_sync_is_a_finding_naming_the_profile` — a live file edited after
  its tree copy is a single `live-edited-not-tree` finding naming the profile, both sizes and the
  one-way remedy.
- `test_a_tree_to_live_sync_clears_the_live_edited_finding` — once the edit lands in the tree, a
  real tree→live sync makes the files identical and the finding clears (drives the real
  `agent_profile_sync.py`, not a copy).
- The two added tests pass alongside the existing suite
  (`68 passed, 0 failed` in the CI-equivalent isolated env; the 5 host-only failures are
  environmental — this host has real `~/.hermes/profiles`, CI has none).

The existing `live-longer`/`live-lines-missing`/truncated-seed findings stay: `live-edited-not-tree`
is the mtime-based direction (live edited AFTER the commit), distinct from the content-based
truncated-seed story about the tree.

## Not covered

- The read-time "the live reference moved during the check" caveat — that is #924 / PR #969,
  referenced but not copied here.
