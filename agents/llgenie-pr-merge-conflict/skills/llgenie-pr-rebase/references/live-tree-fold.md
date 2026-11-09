# Folding live profile drift into the tree (version-here)

When the live profile's skill content is ahead of the tree (running behaviour is authoritative and the
tree lags), the fold is a **versioned PR**, never a tree→live sync and never a wholesale copy of the
live skills directory.

## Procedure

1. **Measure the drift in both directions, per file.** Diff the live lane skill dir against the tree
   copy file-by-file (`diff <(git show :<path>) <live path>`). The result names which side is ahead
   for each file — the fold is rarely one-directional.
2. **Branch from fresh upstream main.** `git fetch upstream main` (canonical remote is
   `asimov-agent/llgenie`; a fork named `origin` is not upstream), branch from `origin/main` at the sha
   fetched in that moment, work in a worktree outside the canonical repo, record the base sha in the
   start comment.
3. **Byte-copy only the live-ahead files.** Acceptance is the diff being *empty* (byte-identity), not
   "it looks updated": `diff <(git show :<path>) <live path>` → rc 0. Same for every added reference.
4. **Never blind-copy a file where the TREE is ahead.** A reference that carries a corrected framing the
   live copy lacks (tree larger than live) would lose that content on a byte-copy. Compare before
   copying; keep the tree version when the tree is ahead, and say so in the PR body.
5. **Do not fold the general hub skill library.** The live skills store holds every installed skill
   (hundreds of files, tens of MB); that is the global library, not lane drift. Only the lane's own
   skill directory is versioned content. Enumerating and committing the whole store bakes unrelated
   skills into the tree.
6. **Change-note pair, both files, same stem:**
   - `docs/changes.d/<stem>.md` — ONE table row: `| <date> | <title> | [note](agent-wiki/<stem>.md) | #<issue> |`
   - `agent-wiki/<stem>.md` — the prose note (what changed, which files, what was deliberately not folded).
   - `make changes-index` regenerates `CHANGES.md` from the fragment set; the doc gate fails if a note
     has no fragment, a fragment has no note, or a note references no issue/PR.
7. **Push the branch to the canonical remote BEFORE opening the PR** (see pitfall).
8. **Open ready-for-review (never draft), bookend with a start + finish comment, then hand to the
   planner for the reviewer.** Do not self-clear and do not arm where the owner gates merges.

## The two sync commands move content in OPPOSITE directions, and both can destroy the other side

`make sync-agent-profile` copies **tree → live**: it REPLACES live behaviour, so any line the live
profile carries that the tree lacks is gone. `make tester-fold-live … COPY=1` copies **live → tree**:
it overwrites tree files with live content, so any line only the tree carries is gone. Neither merges.
Measured cost of a blind `COPY=1`: dozens of tree-only rule lines across a dozen files, recoverable
only with `git checkout -- agents/<profile>`.

Before either command, prove no line disappears — run both read-only forms and read the counts:

```bash
make tester-fold-live PROFILE=<profile>            # no COPY: reports same/drifted/live-missing/live-only
make sync-agent-profile PROFILE=<profile> CHECK=1  # no write: byte-identity verdict
```

- `N drifted` / `DIFFERS` = the two sides disagree; a sync or fold will pick one and drop the other.
  Diff first and decide per file which side is authoritative.
- A sync is safe only when the diff is **additions-on-`>`, no `<` lines** — i.e. the live side is purely
  behind. Prove it (`diff live tree | grep -c '^<'` must be 0) before running the write form.
- `live-only` files that no SKILL.md links (`grep -c 'references/<f>.md' SKILL.md` → 0) are unversioned
  working notes, not lost behaviour — report them, do not treat them as blocking.

## A live profile can hold TWO copies of one skill, and then it loads as neither

`skill_view` refuses with "Ambiguous skill name …" and `hermes prompt-size` reports the skill's
`SKILL.md` as `n/a` when the same frontmatter `name:` exists under two paths in the profile
(`skills/<name>/` and a category subdir `skills/<category>/<name>/`). The symptom reads like a broken
tool; it is a duplicate directory. Diagnose and fix:

```bash
# every copy, then compare: the tree copy's md5 is the authority
find <profile>/skills -maxdepth 2 -type d -name '<skill>'
md5sum <profile>/skills*/*<skill>/SKILL.md <repo>/agents/<profile>/skills/<skill>/SKILL.md
```

Quarantine the stale copy by **moving** it out of the skills tree (never delete — it may hold
un-versioned notes), then confirm the fix from three independent reads: `skill_view(name)` loads
without the ambiguity error, `hermes prompt-size` prints a real byte count instead of `n/a`, and
`hermes skills list` shows exactly one entry.

## Pitfalls

- **`gh pr create --head <branch>` fails with "Head sha can't be blank / No commits between main and
  <branch>" when the branch exists only locally.** `git push ... HEAD:refs/heads/<branch>` first, then
  create the PR; a branch that was committed in a worktree is not on the remote until pushed.
- **A generated index file is never hand-merged.** Regenerate it from its source fragment set so both
  sides' rows survive; a token-level union that drops a row is wrong even when the gate passes.
- **Author must stay allowlisted.** Commit as `Asimov Agent` (the allowlisted identity); a non-allowlisted
  author reds the author guard regardless of content.
- **Verify byte-identity from the INDEX, not the working tree.** Line-ending or autocrlf noise can make
  a working-tree diff falsely non-empty; compare `git show :<path>` (staged) against live.
