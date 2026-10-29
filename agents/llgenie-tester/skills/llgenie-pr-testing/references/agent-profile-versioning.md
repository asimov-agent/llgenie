# Versioning a host-agent profile in the repo (`agents/`)

The repository holds the canonical copy of each bot's behaviour; the live profile home is a copy of
it. Changing behaviour is therefore an issue + PR against `agents/<profile>/`, never a private edit to
`~/.hermes/profiles/<profile>/`.

## What the tree contains

| path | role |
|---|---|
| `agents/<profile>/SOUL.md` | the text the agent runs under: identity, the **canonical fleet block**, then `## This lane's rules` |
| `agents/<profile>/skills/<name>/SKILL.md` + `references/` | that lane's versioned skills, at a **flat** path |
| `agents/standing-rules.md` | the one copy of the fleet block; each SOUL states it verbatim |
| `agents/manifest.json` | which profiles are versioned and which rules each SOUL must state |
| `scripts/agent_profile_sync.py` | repo → live home copy; `--check` compares |

Gates: `make check-agent-profiles` (structure, declared rules stated, no secrets, and a `live-longer`
check) and `tests/test_agent_profiles.py` (includes a **byte-for-byte** comparison of the canonical
block against one SOUL).

## Procedure

1. **Find the real base.** These PRs stack. Do not assume the branch with the most files is the base;
   prove it:

   ```
   for b in $(gh pr list --state open --json headRefName -q '.[].headRefName'); do
     git merge-base --is-ancestor origin/<candidate-base> origin/$b && echo "$b descends from it"
   done
   ```

   The right base is the branch every lane's PR targets (the one carrying `agents/` itself → `main`).
2. **Create the lane** by copying the live profile's SOUL and the skill you want versioned. Keep the
   skill at `agents/<profile>/skills/<name>/` — a category subdirectory (`skills/software-development/
   <name>/`) syncs as "missing in the profile" because the comparison is flat.
3. **Register it** in `agents/manifest.json` with the rules the SOUL must state (`never-implement`,
   `never-merge`). The gate fails if a declared rule is absent from the SOUL.
4. **Adding a fleet rule:** write the bullet into `agents/standing-rules.md` **and** into every SOUL that
   carries the block, in the same commit. The byte-for-byte test compares a SOUL against the canonical
   file, so a bullet in one and not the other is an immediate red. Leave lanes whose SOUL is still a
   *seed* to their own PR — editing them only manufactures conflicts.
5. **Sync, then compare** — the sync is repo → live, so it changes your own profile:

   ```
   make sync-agent-profile PROFILE=<name>            # writes and reads back
   make sync-agent-profile PROFILE=<name> CHECK=1    # must print OK, N file(s) byte for byte
   ```
6. **Run the gates**: `make check-agent-profiles`, `pytest tests/test_agent_profiles.py`, plus
   `check-docs` and `check-wiring`. **The change record is a fragment, not a row in `CHANGES.md`**:
   one row per file at `docs/changes.d/<note-stem>.md` (plus the `agent-wiki/` note itself). Hand-editing
   the rendered `CHANGES.md` fails `check-docs` with "is not indexed", because the page is generated.
   Baseline the finding count: run `check-docs` on a clean worktree at the base sha too and report the
   identical count rather than assuming the red is yours.
7. **Open it ready, never draft**, and state in the body that a base other than `main` schedules **no
   CI at all** — list the local gate results and the sha they were measured at, so an empty rollup is
   not later read as a verdict. That same fact decides the merge step: a stacked base has no required
   checks, so arming auto-merge there is an **immediate merge** into the parent branch, not a queue
   position. Report `auto=none (stacked base: no required checks)` and let the stack be merged
deliberately, top first.

## Failure shapes worth naming in the PR body

- **`TRUNCATED? … the tree copy is N b and the profile's is M b — syncing would REPLACE … of live
  behaviour`** — the live half moved and the tree is behind. This is not a sync: copy **live → tree**,
  commit it, then `--check` again. Re-run `--check` at the start of every editing round for that
  reason: the profile is the half that changes while your PR sits open (including from a lane that is
  not you), so a green `--check` ten minutes ago says nothing about now, and the direction to fix it
  is whichever side the guard calls truncated.
- **`live-longer` finding** — "the tree has N b, the live profile has M b — the seed is a prefix of the
  rulebook". This fires on lanes whose SOUL is still a seed. Prove it is not yours: run the same gate
  on a clean worktree at the base sha and report the identical finding count, naming whose PR clears it.
- **`sync ... DIFFERS ... (missing in the profile)`** — the skill sits under a category directory, or
  was copied under a different name than the directory it lives in.
- **`check-agent-profiles` red for a rule the manifest declares** — the SOUL states the rule in prose
  that does not match the manifest's rule name; state it verbatim.
- **`sync ... REFUSED ... the live file was edited AFTER the tree copy was committed`** — the guard is
  **mtime**, not content, so it fires on your own earlier sync too. Diff first (`diff` the live file
  against the tree copy) and only force when the bytes are identical. **`make sync-agent-profile`
  documents `FORCE=1` but its recipe never passes `--force`** — the target help promises an option the
  command does not receive, so call the script directly:
  `python3 scripts/agent_profile_sync.py --profile <name> --force`, then `--check` to prove the result.
  Report the missing flag as a finding; it belongs to whoever owns the Makefile.

## Pitfall: trust the recipe, not the `##` help line

Every `##`-documented option on a repo make target is prose until you read the recipe under it. Open
`Makefile` and confirm the flag is actually passed (`$(if $(FORCE),--force,)`) before you rely on it —
a target that documents an escape hatch it does not forward turns a two-minute sync into a detour.
