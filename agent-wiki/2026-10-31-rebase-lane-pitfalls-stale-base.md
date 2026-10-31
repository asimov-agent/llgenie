# Rebase lane: version the import-roots stale-base lesson into `references/pitfalls.md`

Follow-up to `#1159` (which cleared the lane's last live→tree drift row). This carries one live-only
lesson the correction produced into the tree, per #1156's direction (lessons land via PR under
`agents/llgenie-pr-merge-conflict/`, not live-only).

## The lesson

The decisive `git archive origin/main | make check-import-roots` measurement — like a PR head — must be
taken at a **freshly re-fetched** `origin/main`. A base fetched "a few commands earlier" is stale in
this repo's churn and produced exactly that failure: the ~78-findings import-roots scan was measured at
`28b279f1` (the main fetched before `#1159` merged) and reported as "MAIN is red"; the merge advanced
main and the ratchet reconciled, and `make check-import-roots` at the merged `c3a0860d` returns rc=0.
The auto-merge then fired on the green base, contradicting the reported red — the stale base's only
effect was a false blocker claim, retracted same turn.

Treat it as the base-side twin of the "read `headRefOid` at report time" discipline: verify
`git rev-parse refs/remotes/origin/main` immediately before the archive, and prefer `git archive
origin/main` over a working-tree checkout (a `git fetch` moves refs only, never the working tree, so a
checkout can read a stale or wrong branch).

Verified live is a clean superset of the tree copy (comm: 0 main-only), so this is a pure union.
