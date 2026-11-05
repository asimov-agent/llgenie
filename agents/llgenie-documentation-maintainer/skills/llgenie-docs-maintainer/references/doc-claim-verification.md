# Verifying a doc claim before you write or land it

Every sentence in a doc is a claim about the tree. Three checks catch the claims that cost the most
time: roster/count claims, "the change is missing" conclusions, and dispatches that describe a state
that no longer exists.

## 1. A roster or count is sourced, never written

A doc sentence that names a set of host agents ("the two host agents", "all 13 of them") or any list
the tree is meant to extend must be **sourced from the registry**, not typed from memory:

    git show origin/main:agents/manifest.json        # authoritative profile list
    make agent-profiles-report                        # same, rendered
    git ls-tree --name-only origin/main agents/       # what the tree actually holds

Prove set-equality before landing, not eyeball agreement:

    prose_set == manifest_set == tree_set

A hand-written count is a stale census about to be true of nobody: the manifest gains a profile and
the prose keeps saying "two". When you show a *small example* tree under the roster (a partial
directory listing to illustrate layout), caption it as an illustrative **"two-of-N sample"** and never
as the whole set — the caption is what stops a reader treating an excerpt as the census.

## 2. A zero-hit grep is a bad pattern until proven otherwise

Before concluding "this change never landed on main", search without the doc's markdown markers.
`grep 'all 13 of them'` returns nothing against `**all 13 of them**`; the bold split the literal. Use a
distinctive substring (`grep '13 of them'`), or strip markers (`sed 's/[*_`]//g'`), or grep the
manifest/note/fragment rather than the prose sentence. A grep that returns 0 is evidence about your
pattern first, the tree second — and reporting "the fix is absent" from a bad pattern sends a false
finding to a lane that will re-do finished work.

## 3. A relayed dispatch is a snapshot; read the wire before acting

A dispatch (DM, relay, board row) naming an issue or PR describes the state when it was *composed*,
not now. Before branching or "picking up" the work, read the current state:

    gh pr view <n> --json state,mergedAt,headRefOid
    gh issue view <n> --json state,closedAt,stateReason

If the PR is MERGED or the issue CLOSED, the dispatch is stale-by-arrival: **do not re-implement**.
Correct the dispatcher with measured wire truth (main sha, merge time, PR number) and stand by — a
relay that keeps re-serving the pre-merge baseline is the other lane's cache defect, not new work.
Repeat the correction once, with ids; do not argue it down over multiple messages.

## Order of operations

1. Fetch the tip with an explicit refspec, cut a detachable worktree at that sha.
2. Measure the claim in the worktree (not in your branch checkout): manifest count, tree count, prose.
3. If the claim holds, cite the sha and the command that measured it in the PR body.
4. If it drifted, fix the doc — and name the resolving issue for any hold you place.
