# Verifying content survived a squash / conflict resolution

A squash-merge or a manual conflict resolution can silently DROP clauses from a
non-code file (README, docs, a comment) while the code change merges intact. A
reviewer asking "is this drop intentional?" needs a measured verdict, not a guess.

## Rule: a dropped doc claim is a defect unless the merged code made it false

A clause missing from the merged tree is a *deliberate trim* only when the merged
code made the claim FALSE. If the code still does what the clause says, the drop is
an **under-description** — a doc-drift defect of the same weight as a red run. Never
default to "probably intentional"; measure.

## Procedure

1. **Identify the squash.** A squash-merge has a single parent, unlike a real merge
   commit which has two. `git show -s --format='%H %P' <merge_sha>` and count parents.
2. **Measure three versions of the exact clause**, grep-counting it at each:
   - the ORIGINAL commit (before the resolution),
   - the pre-merge PR head,
   - the merged squash sha and `upstream/main`.
   Loop: `for c in <orig> <prhead> <merge> upstream/main; do git show "$c":README.md | grep -c "<the clause>"; done`.
3. **Prove the claim is still true in the merged code**, against the mechanism the
   clause describes (not just the doc). Example: for a "job-level `env:` rather than
   workflow-wide" claim, count `^env:` blocks per workflow (workflow-level) and the
   job-level `env:` blocks in the reusable callee — if workflow-level is 0 and the
   callee sets the value at job level, the clause is true and its removal is a defect.
4. **Check formatting lost alongside text** — a bold `**word**`, a `[link]`, an em
   dash. Compare `grep -o` of the exact markdown span, not just word counts.
5. **Verdict + restore wording.** Pull the exact original sentence to hand off:
   `git show <orig>:README.md | sed -n '<line>p'`. Give the one-line replace
   (old fragment -> new fragment) rather than "restore the sentence".

## Routing a doc restore

A README/docs restore is the **documentation lane's** pull, not this lane's — this
lane's PR is for workflow/gate/make-target files. Message the documentation
maintainer with the measured evidence and the exact replace. Then **record the
disposition as a comment on the merged PR** (id, clause counts per sha, truth-check
result, who owns the restore) — a decision that exists only in a DM does not exist
for the next reader, and a DM may never be read.

## Proving an `--onto` replay preserved your content (a rebase, not a merge)

After rebasing YOUR OWN branch onto an advanced `main` (`git rebase --onto <fresh-main> <your-old-base> <branch>`),
the naive check misleads: **`git diff <old-head>..HEAD --stat` is NOT empty and is NOT your content changing** — it
lists every commit `main` gained since your old base (`CHANGES.md` rows, another lane's `agents/` files, new
openspec changes), because HEAD now carries them under the new base. Reading that delta as "the rebase altered my
files" is the false alarm; the honest proof is two checks:

1. **Per-file identity of YOUR files** — for each path your commit actually touched, compare the trees directly:
   `git diff --quiet <old-head> HEAD -- <file> && echo IDENTICAL <file>` (loop over your file list). Any `DIFFERS`
   on a file only YOU touched is a real defect (a lost hunk); the expected set is empty.
2. **Confirm the leftover delta is exactly main's advancement** — `git diff --stat <old-head> HEAD` should name only
   files your commit did NOT touch (main's new commits). If a file appears in BOTH lists, inspect it: a shared file
   like `CHANGES.md` differs only by the peer lane's added row appended above your intact row — verify with
   `git diff <old-head> HEAD -- CHANGES.md` and confirm your row is still present, not replaced.

That pair proves the replay was content-clean (base moved, your change untouched), which is the claim worth stating
when you hand the new head to the reviewer: **"my N files are byte-identical between <old-head> and <new-head>; the
only delta is <peer>'s landed change".** `git merge-base --is-ancestor <old-head> HEAD` returning NO is also
expected here (the old head is not an ancestor of the rebased head by construction) — do not read it as a lost commit.

On the CI side, the stale-base symptom this rebase clears shows up as `check-pr-base` moving from `failure` to
`skipped` (green-triggered after the rebase) in the fresh run's step map — read the step list to confirm, since a
skipped step is not itself a green.

## Resolving a CHANGES.md conflict in a rebase: regenerate, never hand-merge rows

`CHANGES.md` is a GENERATED index (`make changes-index` renders it from the `docs/changes.d/*.md`
fragments). When both lanes added a row, the conflict is in the rendered file, and hand-merging rows is
the wrong move — it can drop a sibling's row or mis-order them. Resolve it by regenerating: the
fragments are the source of truth, so `make changes-index` rebuilds the file with BOTH rows present and
correctly ordered. Verify the fragment count is what you expect (`ls docs/changes.d/*.md | wc -l`) and
that `git diff <old-head> HEAD -- CHANGES.md` shows the peer's added row plus your intact row — nothing
else.

**A regenerated file is NOT a resolved file — `git add` is the resolution step, and two checks will
fool you into skipping it.** `make changes-index` overwrites the working-tree content, so
`grep -cE '^(<<<<<<<|=======|>>>>>>>)' CHANGES.md` returns 0 and the diff reads correctly, while the
INDEX still holds the three merge stages and `git diff --name-only --diff-filter=U` still lists the
path; `git rebase --continue` then refuses with *"You must edit all merge conflicts and then mark them
as resolved using git add"*. The reliable sequence is regenerate → verify both rows are present →
`git add CHANGES.md` → confirm `--diff-filter=U` prints nothing → `GIT_EDITOR=true git rebase
--continue`. Treat the empty `--diff-filter=U` output as the gate, never the marker grep.

## A `git rebase --continue` that HANGS is the commit-message editor, not a lock

When the replay stopped on a conflict and `git rebase --continue` opens an editor for the commit
message, a non-interactive shell hangs on it forever (no output, no exit). Drive it explicitly:
`GIT_EDITOR=true git rebase --continue`. Check `git status --porcelain` first — no `UU`/`AU` lines means
all conflicts are resolved, so the only thing standing between you and the replay finishing is the
editor.

## When the rebase lane asks "is this your intentional resolution?"

Answer with the measurement, not agreement or deference. Confirm or refute with the
three-version grep and the code truth-check, then state the routing. Thank the lane
for holding the branch unpushed when it correctly declined to force-push a branch
whose head had already moved.
