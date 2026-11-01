# The CHANGES.md index — one row per file, and the freshness duties that follow

`CHANGES.md` was one table every PR prepended a row to; at `main@97a24063` 10 of 12 open `DIRTY`
PRs conflicted on it alone (issue #934). The durable shape is **one index row per file**:
`docs/changes.d/<note-stem>.md` holds exactly one row, and `CHANGES.md` is rendered from the
fragments by `make changes-index` (`scripts/changes_index.py`).

## Rules that follow

- A change PR adds `agent-wiki/<stem>.md` and `docs/changes.d/<stem>.md` and **never** edits
  `CHANGES.md`. Do not gate `CHANGES.md` currency — requiring it per PR re-creates the append point.
  `make changes-index-report` prints how far behind it is.
- **The docs lane's OWN versioning/doc PR is the exception that renders it — and the render is the
  currency job, done IN that PR, not deferred.** After the note+fragment are written and the
  functional commit is in, run `make changes-index` (it writes from every fragment in
  `docs/changes.d/`), then amend the commit and re-push. Expect the diff to include **other lanes'**
  unrendered rows alongside yours (the render is global, not per-PR) — that is correct and minimal
  (your row + whatever note landed without a render), not scope creep; quote the added rows in the
  PR body. `check-changes` is **not** a `make` target — it is a check function run *inside*
  `check-docs`, so never `make check-changes` (it 404s); the proof the render is consistent with the
  fragments is `make -s check-docs` staying green ("CHANGES.md links no missing note").
- **A committed row that no longer matches its fragment is a main-red this lane owns — regenerate,
  do not hand-edit.** When a fragment is edited AFTER it merged (a strengthened md5, a corrected byte
  count, a re-worded summary) but `make changes-index` was never re-run, `CHANGES.md` keeps the OLD
  row while the renderer would emit the new one. `tests/test_changes_index.py` asserts
  `committed_rows <= rendered_rows` ("CHANGES.md carries a row make changes-index would never
  write"), so the default-branch `unit` leg reds at the CI head even though the fragment is correct
  and every doc gate (`check-docs`, lint) is green. It is NOT a merge conflict and NOT a stale
  census pointer: the fix is the currency job — `make changes-index` rewrites the whole table from
  the fragments, the diff is `CHANGES.md`-only (1 file), and the subset assertion goes FAIL→PASS.
  This is a **docs-only PR**, never a `do-not-merge`. Verify at head with `committed == rendered` and
  `non-rendered rows == 0`, then `make -s check-docs` + `make -s ci-lint`.

## Reproducing a reported index red (or any test that reads the working tree)

- **Reproduce at the EXACT CI head in a CLEAN worktree — a dirty local `main` checkout can PASS the
  failing assertion and mask it.** The main checkout usually sits on an older commit and/or carries
  uncommitted changes, so a test that reads the working tree (the `CHANGES.md` subset check, a
  census, a render) can pass there for the wrong reason while CI reds at the pushed head. Do not
  conclude "it passes here, the reporter is wrong": `git fetch origin
  +refs/heads/main:refs/remotes/origin/main`, `git worktree add /tmp/repro <the-CI-head-sha>`, run
  the exact failing test/gate there, and quote BOTH outcomes (dirty checkout sha vs clean-head sha).
  The clean-head FAIL and the dirty-checkout PASS together ARE the proof your checkout was masking
  it. Fix on a branch cut from that clean head, never by editing the dirty checkout.
- Reproduce the assertion the test itself makes, not a hand guess of it. For the index: parse committed
  rows (`line.startswith('| 20')`) and rendered rows (`ci.render(root)`), and confirm `committed ==
  rendered` and `non-rendered == 0` — that is the same predicate `test_the_real_index_accepts_a_committed_changes_md_that_lags_the_fragments`
  evaluates, so a green there matches what CI runs.
- **A reporter's cited FILENAME or md5 literal may not match the tree — reconcile by measuring the real
  thing, never by declaring the finding false.** A run/log citation can carry a fragment stem, a byte
  count or an md5 that differs from what is actually committed (a renamed stem, a re-strengthened md5,
  a truncated hash). Grep for the literal, and when it misses, find the real file (`ls docs/changes.d/ |
  grep <note-topic>`), recompute the md5 (`md5sum`), and re-run the predicate: a stale literal with a
  live divergence is still a real defect, and "the literal isn't in the tree → reporter is wrong" is
  the false-negative that ships a red main. Quote the real stem and both md5s in the fix PR.
- **`pytest` is not installed in this lane's host — run the predicate, not the test file.** `python -m
  pytest ...` exits non-zero for lack of the package, which reads like a red. Import the module
  directly instead (`python3 -c 'import scripts.changes_index as ci; ...'` from the repo root) and
  evaluate the same predicate the test evaluates; that is the measurement, and it costs no install.

## Gate falsifiability and the change→note direction

- Keep the gate falsifiable in both directions: note with no row → red, row whose note is gone →
  red, malformed row → red. Deriving rows purely from note frontmatter loses the dangling case.
- **A rule is only enforced where a gate checks BOTH directions — a one-directional gate is the
  blind spot.** The change-record rule was gated note→fragment (a note must have a row) but never
  change→note, so a behavioural change with no `agent-wiki/` note merged green (measured: roughly a
  third of recent merged PRs touching `scripts/`, `agents/` or `docs/` carried no note). When you
  add or review a gate, name the direction it is silent on and close it: a change owes a note when
  it touches a behavioural surface (`scripts/**`, `agents/*/SOUL.md`, `agents/*/skills/**`,
  `agents/manifest.json`, `docs/**/*.md`, `.github/workflows/**`, `Makefile`, `data/**`,
  `containers/**`, `openspec/**`), while `tests/**`, `agent-wiki/**`, `docs/changes.d/**` and
  `CHANGES.md` are exempt. A live→tree skill sync is such a change even though it only copies
  bytes the live profile already ran — it *edits* `agents/*/skills/**`, so it owes its own note;
  ship the note in the same PR as the sync, not as a follow-up, or the gate reds the sync the
  moment the gate PR merges. **The gate reads the COMMITTED diff, not the working tree** — its
  change→note check diffs `origin/main...HEAD`, so a note + `docs/changes.d/` fragment written to
  disk but not yet committed leaves `make check-docs` red with the change→note error and reads as
  "the note was ignored"; commit the pair, then re-run the gate. **The note STEM need not match the
  changed filename** — the check passes once the diff ADDS any `agent-wiki/<stem>.md` paired with
  its `docs/changes.d/<stem>.md` row, so a folded reference file is satisfied by one note named for
  the change, not for the file it folds. Assert the surface set **additively** — a behaviour/subset
  check, never a pinned file list — or the gate reds on the next legitimate surface and gets edited
  to match the code. Prove both lines: a no-note behavioural change fails, an exempt change passes.

## Structural and migration proofs

- Prove the property structurally, not by assertion: two scratch branches each adding a note +
  fragment, then `git merge-tree --write-tree a b` must print a single tree sha and no conflicted
  path.
- Migrating existing rows: split them **verbatim** into fragments, then `make changes-index`; diff
  the data rows against `git show HEAD:CHANGES.md` so the refactor provably rewrites nothing.
- Resolve a rendered `CHANGES.md` conflict by regenerating, never by hand: `git checkout --ours
  CHANGES.md`, then `make -s changes-index`, `git add`, `rebase --continue`. Never hand-merge a
  generated file — a manual edit that stops matching the fragments reds `check-changes` inside the
  next `check-docs`.
