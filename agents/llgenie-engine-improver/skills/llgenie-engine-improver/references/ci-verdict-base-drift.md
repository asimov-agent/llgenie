# Reading a CI verdict: base-drift reds and mergeable settling

## A `linux/unit` red can be the base-drift gate, not a test failure

The aggregate unit job also runs `check-pr-base`, which diffs `base...HEAD` against the worker's LIVE
`origin/main`. Once main advances past your cut point it flags YOUR OWN branch-head commits as foreign:

    [check-pr-base] FAILED: HEAD is NOT cut from origin/main — its merge-base with origin/main is <old sha>;
    the branch carries commits from another PR / another base

while the suite itself passed (thousands of tests green). A `conclusion=FAILURE` on a job whose name
says "unit" says nothing about the tests — only the log's failure line does.

That red means:

1. `git rebase origin/main` — clean when the commits that moved main touched files your diff does not.
2. Verify locally at the rebased head: merge-base == live main, docs gate clean, your own tests green.
3. `git push --force-with-lease`, then re-verify the fresh runs at the new head.

It is NOT a phantom regression to chase. This satisfies "rebase only on a real conflict" on its own
terms: the base gate IS the conflict. Before blaming a pin or a code change, classify drift as "the
pin/base moved" vs "another input moved".

## `mergeable` reads UNKNOWN after a force-push — poll it out

Right after a force-push `gh pr view --json mergeable` returns `UNKNOWN`/`null` and
`mergeable_state` is `unknown` while GitHub rebuilds the squash merge-ref (`refs/pull/<n>/merge` is
created lazily). The rebased head is authoritative as soon as `git ls-remote origin` /
`gh pr view --json headRefOid` show it, and every check-run at that head may already be SUCCESS with
`reviewDecision=APPROVED` while `mergeable` lingers UNKNOWN.

Treat `mergeable=null/unknown` within a couple of minutes of a push as compute-in-progress, not a
hold: re-poll until it settles to MERGEABLE, and never report a green PR as blocked on an UNKNOWN
that is still being computed. Authoritative green evidence is the check-runs at the named head sha.
