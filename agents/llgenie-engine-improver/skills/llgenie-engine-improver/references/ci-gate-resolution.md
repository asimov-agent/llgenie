# CI gate resolution — distinguishing a real defect from a gate red

Most engine-PR reds are NOT code failures. Before touching code or blaming a pin, read the
failing step's OWN log and classify the red. Three classes recur.

## 1. `check-pr-base` base-drift (branch, not code)

Symptom: a job concludes `FAILED` with `[check-pr-base] FAILED: HEAD is NOT cut from
origin/main — its merge-base with ... / foreign commits`.

Mechanism: the gate compares the branch's merge-base against the LIVE `origin/main`. If main
has moved since you branched (e.g. another PR merged), your own commits are reported as
"foreign" even though the code is correct. A `linux/unit` job can show `FAILED` while its
test body printed `3034 passed` — the red is this gate, not a test.

Fix:
- `git fetch origin main` (explicit refspec; never the ambiguous `origin/main` shadow), then
  rebase the branch onto the fetched live main commit, resolve, `--force-with-lease` push.
- Re-verify locally at the new head: `check-pr-base` rc=0 / no foreign commits, `check-docs`
  passes, the fix's own tests pass.
- Rebase ONLY when the gate actually reds or a real conflict appears — do not rebase on every
  main move (owner rule). Keep the current merged baseline otherwise.
- After force-push the PR head may lag the wire for a moment while GitHub recomputes the merge
  ref; re-read `headRefOid` before claiming.

## 2. `linux/unit` red that is not a test failure

A `FAILED` conclusion on the unit job does not mean tests failed. Open the unit job's log and
look for the actual failing line number — it may be the embedded `check-pr-base` gate (class 1),
a report-header assertion, or another inline gate, while the pytest body reports thousands of
passes. Quote the specific error line before classifying; a `conclusion` is a verdict, not a
cause.

## 3. change → note gate

Mechanism: changing a behavioural file (e.g. `scripts/engine_image.py`) owes a change-note trio:
- `agent-wiki/<stem>.md` — one note per changed behavioural file (stem == the changed file's stem),
- `docs/changes.d/<stem>.md` — a one-line fragment,
- the rendered `CHANGES.md` index row, produced by `make changes-index`.

Pitfall that costs a red: `check-docs` diffs `base...HEAD` (merge-base vs HEAD). Note files that
are only **untracked** in the worktree are invisible to that diff and the gate reds. The note
trio must be **committed** to HEAD before the gate sees them. Stage + commit the notes, then run
`make changes-index` (it re-renders deterministically from committed fragments; it may also pick
up an unrelated fragment that main landed without its index row — that is pre-existing merge
drift, not your change).

Local pre-push order that matches CI: commit notes → `make changes-index` → `check-docs`
(base...HEAD) → fix tests → push.

## Wire truth before any claim

Another lane's reconciliation premise can predate BOTH a rebase and a merge. Before replying to a
"#N is stuck / not merged / head is X" message, read the live state: `gh pr view <n> --json
headRefOid,state,mergedAt,mergedBy,mergeCommit` and `gh issue view <n> --json state,closedAt`.
A squashed merge lands on main as a single commit; confirm the fix is present on `origin/main`
(search the symbol in the merged file with the native search tool) rather than trusting the head
sha alone.
