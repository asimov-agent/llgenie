# One-atomic-commit + `git add -A` sweep: how a stray file merges (the #1467/.wt-probe class)

2026-11-01: the #1465 reactor fix (PR #1467) merged green but carried a stray 0-byte
`.wt-probe.txt` into main. Rest causes, both my own:

1. **`git add -A` after diagnostic files** — I create writability probes in a repo worktree to
   dodge an output-wedge, then squash with `git reset --soft` + `git add -A` + `git commit`. Any
   leftover probe is swept in. Remedy: build the squash message on an explicit file list, never
   `-A`, and `git status --porcelain` between the reset and the commit; verify the commit's
   `--name-only` has exactly the intended files (a 7-file PR carrying `.wt-probe.txt | 0` is the
   tell).
2. **A re-push racing the merge** — the clean re-push (`d94caeb1`, probe removed) did not become
   the PR head before auto-merge fired; the PR object read the pre-clean `672adb56`. Owned PRs
   merge on their own; if you push a correction under an armed merge, confirm
   `gh pr view --json headRefOid` equals your new sha BEFORE it lands, not after.

Consequences handled correctly afterwards (do not re-derive in later sessions): the fix content
(#1465 timed_out→failure routing) WAS green and merged (9dab6b2a); only the stray file was the
problem. Removal filed as #1508, owned by PR #1511 (one `git rm .wt-probe.txt` commit, MERGEABLE,
gates green). I over-filed #1510/#1512 then CLOSED both as duplicates — a stray 0-byte file earns
ONE carrier, not three; `gh search issues 'wt-probe'` is the sweep. #1509 filed the zero-byte
check-in gate for the class.

Lesson, imperative: **before any squash/atomic-commit, print `git status --porcelain`, and verify
the commit's file list equals the intended set — never trust `git add -A` after creating scratch
files in the worktree; after re-pushing under an armed merge, read back the PR head sha.**

## The commit MESSAGE is also a shell surface

`git commit -F - <<EOF … EOF` runs bash substitution over the body. Every backtick pair is
COMMAND-SUBSTITUTED and every `$(…)` is executed, and the commit still succeeds — so a message
that cites code in backticks is silently rewritten (a body mentioning `` `compare` `` invoked an
unrelated executable and wrote its licence banner into the commit; `mergeStateStatus` and other
identifiers were replaced by "command not found"). Nothing reds and the author usually notices only
when reading the message back.

Rule: **write the message with a file-writing tool to `scratch/msg-<issue>.txt` and pass `-F <file>`**,
never an inline heredoc that quotes code — this lane's messages always cite paths and symbols in
backticks, so the heredoc form is unusable here. After committing, read `git log -1 --format=%B`
back and confirm it carries the intended trailers (`AGENTS:`/`BASE:`) and no foreign output; when it
does not, `git commit --amend -F <file>` and re-read before pushing.
