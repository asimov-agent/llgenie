# Rebase-lane decline trap: mergeable=true != based-on-latest-main

WHEN: a rebase directive is declined by the rebase lane citing mergeability.

TRAP: the GitHub API's `mergeable=true` means only "no merge-conflict" — it does NOT mean the PR head is based on latest main. A lane (or an agent) quoting `mergeable=true` as "needs no rebase; main is already ancestor" is answering the wrong question. The owner's rebase directive and any base-required artifacts (e.g. a change-note that only exists on main) are satisfied independently of mergeability.

RULE: test the REAL relation with git merge-base on the canonical repo, never the API flag:
- `git merge-base --is-ancestor <main_tip> <pr_head>` → NO means the head is BEHIND latest main → rebase owed.
- `git merge-base --is-ancestor <required_merge_commit> <pr_head>` → NO means a required main-only artifact is absent at head.

LESSON (llgenie 2026-11-06): PR #1696 head ea0b9033 had `mergeable=true` in the API, yet main tip 72fc612879 was NOT an ancestor (head 2 behind) and the #1694 AC4 change-note merge 1827be9669 was NOT in the head. The "no rebase needed" decline was a false premise; the rebase was owed independent of mergeability. Evidence posted on-issue (comment 6676826489).

Escalate clearly: quote the two `-is-ancestor` results (NOT-ancestor for tip, NOT-ancestor for the required artifact) to the lane alongside the owner directive, and record on-issue so the durable thread carries it.
