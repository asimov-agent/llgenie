## 11. A per-PR "measured at" census pointer is a gate-defect symptom — do not chase it per PR

`scripts/check_architecture_census.py` reads a `measured at \`<sha>\`` pointer from
`docs/ARCHITECTURE.md` and asserts the doc counts match the tree. When a PR reds because that pointer
is a now-dangling sha (a rebase/squash gc'd it) or the counts are stale, the instinct to *re-point it*
on the PR is the wrong fix: the gate takes the checked-out HEAD as ground truth, so **every
file-adding PR must rewrite the pointer, and it dangles again after the squash** — an endless
per-PR chase, and a second vehicle on a branch the rebase lane may already have moved.

Diagnose the class before touching the pointer:

1. **Is the gate's ground truth the PR head or the `measured at` pointer?** Read the gate's OWN output
   line before theorising: it prints
   `[census-gate] OK — census measured at \`<sha>\` (tracked=N, …); referent \`<sha>\` is an ancestor of
   HEAD (<head>)`. When it counts at the POINTER and only requires that pointer to be an ancestor of
   HEAD, a file-adding PR does **not** owe a pointer rewrite — the counts are the pointer-tree's, and
   the tree at your head can differ from them (that is the design, post-#1053). Verify by reading the
   line: `counts at the pointer` + `referent … is an ancestor` = the gate is anchored, so leave
   `ARCHITECTURE.md` alone; a red naming a DANGLING pointer sha or mismatched counts at the pointer is
   the separate stale-pointer class below. (The pre-#1053 gate re-measured at HEAD, which is what made
   every file-adding PR rewrite the pointer — that history is why the defect exists, not a description
   of the current gate.)
2. **Does the red vanish on a plain rebase onto current main?** A branch behind `main` carries a stale
   copy of `ARCHITECTURE.md`; rebasing onto current main inherits the correct pointer + counts, with no
   per-PR edit. Check with `git merge-tree --write-tree <main> <head>` (clean) and diff the two
   `ARCHITECTURE.md` pointers — if the branch does not *modify* the file, main owns it.
3. **Many PRs redding the same way is ONE gate bug, not N branch bugs.** Hold the per-PR pointer edit,
   do **not** push a second fix onto a branch the rebase lane already rebased (that cancels their live
   run and duplicates the fix), and wait for the gate-source fix (#1053) to land. Then rebase +
   re-verify (unit green + the marks/pin) after it lands and main moves.

Rule: a `measured at <dangling sha>` or stale-count red is a **gate-ownership smell first, a branch
defect second**. Re-pointing it per PR is the symptom-chase #1053 exists to end. (Learned on #1016:
the pointer `348f7b4e` was a non-object; the real fix was #1053 at the gate source plus a rebase onto
current main — my independent rebase and the rebase lane's landed on the identical tree, and no push
was needed.)

**The mirror case is legitimate and needs the opposite treatment:** when the pointer is broken for the
WHOLE fleet (every PR reds `scope/check-docs` because `main`'s own pointer dangles), the single
re-point PR onto current `main` IS the correct unblocker — verify it instead of suppressing it. The
full recipe (local-ref fetch, clean `merge-tree`, real gate on the merged tree, gate-not-weakened
check, `REVIEW_REQUIRED` arm state) is `references/red-job-triage.md` §10.

- **A baseline/ratchet red is the SAME stale-measurement class, decided by scanning `main`'s tree with
  the branch's own counter.** A recorded baseline (a count, a pointer, a census) measures ONE tree
  state; a rebase onto a newer `main` carries newer debt in and the recorded number no longer matches
  the rebased tree, so the gate reds with NO change to the PR's own files. Decide whose fix it is by
  the same move as §9b: run the PR's checker over a `main` checkout. If main's count is far WORSE and
  the specific failing files are UNTOUCHED by the PR, it is a stale baseline — re-record it at the
  rebased base (grandfather main's pre-existing debt), and do NOT rewrite the PR's migrated files.
  "May only shrink" forbids hiding roots a PR ADDS; it does not forbid recording roots `main` already
  had, so re-recording to the current count is matching main, not weakening the ratchet.
- **The mirror case: a ratchet red whose offending sites are the PR's OWN brand-new files is the PR's
  defect — fix the SPELLING, never `--update` the baseline.** Same gate, opposite verdict: run the
  branch's checker over `main`'s tree and it comes back at-or-below baseline while the head is over
  (`sys-path 33 now/32 recorded`, `bare 54 now/52 recorded`) and the named files are files the PR
  ADDS ⇒ the new file is the offender, not the recorded number. Raise the baseline here and you have
  hidden the very roots the ratchet exists to stop. For `check_import_roots.py` the guard-clean form
  is `from scripts import <mod> as <alias>` (what `tests/test_import_roots.py` itself uses) with NO
  module-level `sys.path.insert`: `tests/conftest.py` is the one file allowed to insert, it already
  publishes the repo root and `scripts/`, and CI sets `PYTHONPATH=/repo/scripts`. The bare
  `import <mod>` after a hand-rolled `sys.path.insert(0, str(REPO/"scripts"))` costs TWO counts (one
  `sys-path`, one `bare`) from a single import block. Checker entry points: `python3
  scripts/check_import_roots.py report` (counts) and `... ratchet` (the gate; exit 0 prints `OK:
  counts at or below the recorded baseline`). Prove a remedy on a throwaway worktree (§9/§7 — never
  push it to the implementer's live branch) and hand the sed-able two-line diff to the lane that owns
  the branch. Depth: `references/path-selection-probes.md`.
