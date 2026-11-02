# Folding a live agent-profile file into the tree — the authorship race

When the task is "commit this live `~/.hermes/profiles/<lane>/**` file into the repo tree
byte-identically, then point SKILL.md at it", the live file may be under active authorship by the
lane that owns it at the very moment you fold. This is the failure mode: your fold is a snapshot of
a file that is still being written, so by the time it lands it is either stale (fails a byte-identity
check) or, if you copy your tree version back over live to "re-sync", you truncate a richer live
copy (#791 — silent truncation). Both outcomes are worse than filing nothing.

## Procedure

1. **Measure the live file immediately before the fold AND again immediately before landing.**
   For every candidate: `stat -c 'mtime=%y size=%s'`, `wc -c`, and `md5sum`. Stamp each measurement
   with `date -u +%H:%MZ`. A single md5 taken once is not enough — the whole question is whether it
   moved between two moments.
2. **If mtime / size / md5 moved between the fold and the land, stop.** The live is being authored
   by another lane. Do **not** land your fold (it is stale) and do **not** push your tree version
   over live to make them match (that is the truncation defect). The live is authoritative.
3. **Park the PR and hand the decision back.** Post one consolidated comment on the filing issue
   with: the measured-now size/md5/mtime of each file vs what you folded, the PR numbers that are
   now stale, and an explicit ask — (a) owner holds authoring / names a stable snapshot sha and you
   re-fold+re-anchor to it, (b) stand down the stale PRs and redo them from a quiescent snapshot, or
   (c) owner is mid-authorship so you pause until they say quiescent. DM the owning lane the same
   ask. If the DM returns `queue_full`, do not resend — the issue comment is the durable record.
4. **Detect an authoring storm early.** If several files in the same profile show mtimes minutes
   apart and sizes growing across your session, the lane is mid-refactor; assume *all* of that
   profile's files are in flight, not just the one you happened to re-measure.

## A fold that merged STALE needs a corrective fold, not a rebase of the merged PR

A fold PR can merge while the live file was already richer than the snapshot it committed — the
landing succeeds (`state=MERGED`) but the tree blob is stale against live (measured: a 5,106 B tree
copy against a 7,282 B live `md5`). The merged PR is closed history; you cannot rebase it. Open a
**new corrective fold PR** that copies the *current* live bytes over the stale tree blob and
commits that single-file diff. Prove it with `cmp -s tree live` + `md5sum`/`wc -c` on both sides, and
say in the body what the stale md5 was and what it now is. A corrective fold of a file that already
has an in-tree change-note does not need a second note (the #1123 gate is satisfied by the change,
not per-copy), but a fresh note is harmless — check `docs/changes.d/` for one before adding.

## Re-cut the fold branch from a fresh `origin/main` — do NOT rebase an old-base fold branch

When the fold PR was cut at an old base and several merges have landed since, **re-cut**: fetch
`origin/main`, then `git checkout -B <branch> origin/main`, copy the frozen live bytes over the
target paths, add the note+row, and commit. This yields a clean single-file (or small set) diff.
Rebasing the old branch re-introduces every intermediate file the fold base lacked (the diff then
carries unrelated refs that merged in the meantime) and re-runs the whole conflict surface for no
benefit. Re-cut before every attempt where the base moved; confirm `git diff --name-only
origin/main..HEAD` is exactly the files you intended.

- **Fold to the CURRENT measured live md5, never a hash quoted in the dispatch or issue body.** A
  quoted md5 is a claim about a past moment; re-measure `md5sum` + `wc -c` on live this minute and
  fold that. The quoted value and the measured value routinely differ (measured: issue quoted
  `17435e22…`, live was `7fade46f…`); folding to the quote lands stale. Branch from the sha you
  fetched a moment ago, never one quoted in a message.
- **Verify EACH acceptance ref file-by-file against the tree — the dispatch's scope can lag the
  planner's current finding.** A dispatch brief may name N refs while a later post-merge finding
  defines a larger acceptance set; the fleet assumes "the open PRs carry the rest" but one named ref
  can be in *neither* PR. For each named path, run `git cat-file -e origin/main:<path>` and compare
  its `md5`/size against live — classify PRESENT-fresh / PRESENT-stale / ABSENT and build the fix
  set from that table, not from the prose. A ref nobody folded gets its own single-file vehicle.
- **`scripts/lint_linefeeds.py` takes NO positional args.** It scans every *tracked* file; passing a
  path errors `unrecognized arguments`. To lint a fold: stage/commit it first (so it is tracked),
  then run the bare `python3 scripts/lint_linefeeds.py` and expect `LINT OK`.

## Does the fold need a slim? Measure CHARACTERS, not bytes

A folded `SKILL.md` can read as "over the cap" in a dispatch while being perfectly landable, because
two different numbers share the name "size":

- `skill_manage` rejects on **characters** — `"<N> characters (limit: 100,000)"` — so the gate is
  `wc -m`, not `wc -c`. A file that is 100,417 **bytes** is frequently 99,828 **characters** and
  therefore **under** the cap.
- A byte-identical fold that lands under 100,000 *characters* needs **no slim** (#1135-class split):
  measure `wc -m <live>/SKILL.md` before deciding to split; report both `wc -c` and `wc -m`, and say
  which number the cap adjudicates. A dispatch that quotes only bytes has conflated the two.
- Corollary: you cannot grow `SKILL.md` with prose once it sits within a few hundred chars of the cap.
  Put new lessons in `references/` and add a one-line pointer, never another paragraph in the body.

## Post the PR body / bookend, then RE-READ the posted text

A shell heredoc with a **quoted** delimiter (`cat > body.md <<'EOF'`) does **not** expand `$VAR` — a
`#${PR}` placeholder survives literally into the published comment. Write the number explicitly or use
an unquoted heredoc, and either way **verify the posted body** rather than trusting the write:
`gh api repos/<owner>/<repo>/issues/comments/<id> --jq .body` (or `pulls/<n> --jq .body`) and grep the
id/sha/number you intended. A comment that reads `PR #${PR}` is a board record with no PR number — the
same silent-fact defect as a census with no sha. If it slipped through, post a one-line correction that
names the real number; do not edit history you cannot edit.

## Never unilaterally edit a live file another lane owns

While diagnosing a red you may find the live file itself carries a defect (e.g. a `make ci-lint`
"markdown heading not preceded by a blank line", or a missing trailing newline). Even when the fix is
one character and clearly correct, editing the live file while its owner is authoring it overlays
your change on their in-flight content. Instead: flag the defect on the thread with the file, the
line, the measurement, and the exact fix, and let the owning lane apply it. If you already touched
the live copy, say so explicitly in your status (what you changed, that you reverted your tree side,
that the live keeps/drops the line) — an unannounced write to someone else's artifact is the same
class of defect as a stale census.

## The gate reminders that bite during a fold

- `make ci-lint` (linefeed / editorconfig) fails on **markdown headings not preceded by a blank
  line** and on a missing trailing newline. A live source can carry either; if the gate reds on your
  fold, the defect is in the live source, so any fix must go to *both* copies — coordinated with the
  owner (see above), never silently to live.
- The change→note gate (#1123) fires on any branch that touches `agents/**`: it needs an
  `agent-wiki/` note **and** a `docs/changes.d/` row. The gate diffs `origin/main...HEAD`, so an
  uncommitted note on disk does not satisfy it — commit the note pair, then re-run `make check-docs`.
