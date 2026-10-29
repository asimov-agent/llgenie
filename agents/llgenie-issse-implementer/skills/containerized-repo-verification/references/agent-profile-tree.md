# Keeping a host agent's SOUL and skills in the repo

Depth for the `agents/<profile>/` tree: what belongs in it, and the two ways a re-seed goes wrong.

## A re-seed must name the files it copies, never walk a profile home

A profile home (`~/.hermes/profiles/<p>/`) is a **runtime directory that happens to contain a rulebook** —
`SOUL.md` and `skills/`, but also `state.db` (tens of MB), `cache/`, `plugins/` with a nested `.git`, and the
entire installed skill library. `rglob("*")` over it copied **15,963 files** into `agents/<profile>/` in one
run; only the command's own output revealed it, and it was cleaned before committing.

- Copy an explicit allowlist (`SOUL.md`, `skills/<the profile's OWN skill>/…`) and print each file with its
  size, so a 73 MB `state.db` is obvious in the output rather than in the PR diff.
- Verify after: `git ls-tree -r <head> agents/<profile>` should be a handful of files, and
  `git ls-tree -r <head> | grep -cE 'state\.db|\.curator_backups|plugins/|cache/'` must be `0`.
- `git clean -fd <dir>` does **not** remove a directory holding a nested `.git`; clean with an explicit
  keep-list (`SOUL.md`, `skills`) and remove the rest by name.

## A replacement that is LARGER while dropping lines defeats every size guard

Comparing a lane's PR copy of a SOUL with its live profile by size passes the dangerous case: measured on
four lanes, the PR versions were 4,936 / 6,346 / 6,046 / 5,714 b against live 431 / 722 / 4,936 / 2,811 b —
**all larger, and all dropping live lines** (4 / 4 / 32 / 30 respectively). Size is the signal an operator
and a gate both read first, so a "bigger means newer" heuristic replaces a rulebook with different text and
reports success.

- The test is **set-of-lines**: every non-blank line the tree carries must appear in the live file, and the
  live file must not carry lines the tree lacks. Subset means prefix means truncation.
- Choose the **live** text for the tree, and let each lane land its rewrite as its own one-file PR where its
owner can defend the deletions.
- `manifest.json` is a **shared** file: N lanes each adding "one line" is N PRs editing the same JSON, and
  that is where a merge resolution drops a profile entry silently. Land the tree once with every entry, then
  a lane's follow-up touches only its own `SOUL.md` and, at most, its own entry's `rules` array.

## The write path needs an AGE guard, and the source time is a COMMIT, not an mtime

A live-vs-tree comparison is a read; `sync` is the write, and no read-time caveat can see a write it
already allowed. The live profile is a **moving reference** — its owner edits it while a PR is under
review — so a sync into a file edited after the source commit is a silent merge in the wrong direction.

- **Refuse when `mtime(live) > source_time(tree)` unless `--force`.** Name **both times**, both sizes and
the line count the overwrite would cost, say **would overwrite**, never say "verified", and write nothing.
- **The source time is `git log -1 --format=%ct -- <path>`, never the tree file's mtime.** A fresh clone
  sets every mtime to checkout time, so an mtime comparison says the tree is newer than any live file and
  the guard **silently disarms on exactly the checkout that runs the sync**. Fall back to mtime only for an
  untracked fixture, and pin it with a test that `utime`s a committed file into the future and asserts the
  source time does not move.
- **Negative control is mandatory**: a live file OLDER than the source commit must not be refused, or the
  guard is just a red gate. And the refusal must leave the file byte-unchanged — assert that too.
- `--force` must then say what it did: `overwrote a live file NEWER than the source commit by --force
  (live <t> vs source <t>)`, with `identical` absent from both paths.

**And compute "what changed" from a snapshot taken BEFORE the write.** Asking after the copy answers
"all of them" on every run — `replaced an existing file` computed post-copy is a property the instrument
never checked, inside the very file whose job is to refuse exactly that.

**Re-take the tree after EVERY live edit.** The live-longer finding only fires where live profiles exist,
so a tree that has not been re-seeded since the last edit to the live file is a prefix, and a reviewer who
merges it ships the truncation the guard refuses. `CHECK=1` must say `N file(s) … match byte for byte`
before the push, and the count is expected to grow as references are added.

## A skip must be audible, and a home must HOLD a profile

A runner has no `~/.hermes/profiles/`, so a live-vs-tree comparison cannot run there: fail it and every CI
run is red for a condition the runner cannot fix; stay silent and a reader concludes it compared.

- Print the skip, **and put the caveat on the success line too** — `EXIT=0` is what a `&&` chain reads:
  `OK: N profile(s) … — tree checks only, LIVE RULEBOOKS NOT COMPARED`.
- `exists()` is not the test for a profiles home. `Path(env).parent` always exists (a typo, a bare filename,
  `/nonexistent-home` all have a parent), so require **at least one `<base>/<name>/SOUL.md`** before treating
  it as a home; otherwise take the skip path with the caveat.
- Two env vars can mean different things: one names a single profile's home, the other the directory holding
  them all. Accepting the singular name without deriving its parent sends the gate looking for
  `<a profile>/<lane>/SOUL.md`, finding nothing, and reporting a green with the comparison skipped.
- **"Holds at least one profile" is still too weak.** Any directory of probe folders with a `SOUL.md` each
  passes it, so a junk path reports a comparison it did not make. The durable test is a **manifest match**:
  `<base>/<name>/SOUL.md` for at least one name in `manifest.json`. An existence test and a count are both
  satisfiable by accident; a name is not.
