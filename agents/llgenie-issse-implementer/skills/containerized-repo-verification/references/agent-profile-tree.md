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
