# Fix: check-pr-base attributes a stale-but-clean PR to the #845 foreign-branch defect

## Why

`check-pr-base` renders a PR cut from an OLDER `main` — merge-base IS a `main` ancestor, the
head carries only its OWN work — with the same #845 defect message that names a genuine
foreign-branch leak. The gate passes only when `git merge-base <origin/main> <rev> ==
<origin/main>` — i.e. the CURRENT main tip is an ancestor of the head. A branch cut from any
earlier `main` fails this even though the merge-base is on `main` and every commit it carries
is its own. Measured at `main@b7d3edcf` (2026-11-07 ~13:37Z): three open PRs (#1976, #1969,
#1933) all red with the identical "foreign commits from another PR" message; #1976's red
(merge-base `c07d2b40`, 2 own commits) sat in the `guard` leg and CANCELLED its walking legs —
`ci-images`/`linux`/`scanner-images` all `skipped`, and `ci-verdict` reported
`NO VERDICT: 4 job(s) unaccounted for`. The branches are merely stale — the previous reds caused
rebase/fix-bot churn, and the same PR re-dirties after every subsequent main move.

The gate cannot discriminate "cut from an older main (clean, stale)" from "cut from another PR
(#845 leak)". Compounding: the `guard`-leg failure cancels the unit matrix, so a stale-but-clean
PR has no unit verdict, and the dispatch protocol + review skill read an own-gate red at the PR
head as "premise refuted — not a review target", so the reviewer stands down without posting a
verdict. A correct set of changes sits in a permanent red + no-verdict loop that reads as
"something is wrong with this branch" to every lane and the owner.

## What changes

`scripts/check_pr_base.py::check` distinguishes three verdicts instead of two:

1. **stale-but-clean** — merge-base IS a `main` ancestor (the branch was cut from a real main
   tip) AND every commit in `base..rev` is the branch's own (no commit is reachable from any
   other ref than the base and the head's own branch; verified by the reachability probe). This
   is `#1969/#1976/#1933`: the branch is cut from an older main and carries only its own commits.
2. **genuine #845 leak** — a commit in `base..rev` is reachable from ANOTHER ref (it belongs to
   a different branch/PR) OR the merge-base is NOT on `main` at all. This is the real #845 shape.
3. **clean / exempt** — unchanged: merge-base == base, or `base..rev` empty.

A stale-but-clean verdict:
- renders a distinct, non-#845 message — "rebase onto a fresh origin/main" — never the "carries
  commits from another PR (issue #845)" accusation;
- **passes** (exit 0), so the `guard` job succeeds and the walking legs
  (`linux`/`ci-images`/`scanner-images`, all `needs: [guard]`) still run — a unit verdict exists
  at the head even when the base is stale.

A genuine #845 leak still FAILS with the original message (regression guard: the discriminator
must not weaken the real detection), and a branch cut from the CURRENT main tip still passes.

The review-pass classification (this lane's own-domain audit b7d3edcf, and the dispatch
protocol's "own-gate red = not a review target") is brought in line: a `check-pr-base`-only red
with merge-base-on-main and own-commits-only facts is "code green, stale base, rebase owed" — a
routing fact, not a refusal to grade the tree.

## Who

llgenie-ci-pipelines-maintainer (this gate-family defect is this lane's PR, issue #2016); the
review-pass verdict text is owned by the reviewer lane's `references/board-sweep.md`.
