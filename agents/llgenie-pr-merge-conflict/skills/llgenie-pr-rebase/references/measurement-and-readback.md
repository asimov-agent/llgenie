# Measurement and read-back discipline

Pitfalls where a command "succeeds" but the fact it reports is wrong, or where a tool reads a different
copy of the tree than the one you measured. Read the mechanism, not the exit code.

## Exit codes behind a pipe
`cmd | tail -1; echo "rc=$?"` reports **tail's** exit status, not `cmd`'s. A failing gate shows `rc=0` and
you report a green that does not exist. Capture the command's rc before formatting its output, or enable
`set -o pipefail`. Same trap with `cmd | grep`, `cmd | head`, `cmd | awk`.

## "The command exited 0" is not "the effect happened"
`gh pr merge --auto` exits 0 while arming nothing. The fact is whatever the merged-state field reads back
as — never the command's exit code. Verify every external-write by reading the exact target back.

## Auto-merge read-back: GraphQL, and beware jq-on-null
- Read the arm back with explicit fields, not a bare truthiness test. `if .autoMergeRequest then ...`
  prints its "armed" branch on a JSON **null** just as on a real object — a false ARMED. Ask for the
  fields directly: `gh pr view <n> --json autoMergeRequest --jq '.autoMergeRequest | {method: .mergeMethod, by: .enabledBy.login, at: .enabledAt}'`.
  A non-null `mergeMethod` is the proof; `null` method = not armed.
- REST `pulls/<n>.autoMergeRequest` reads empty/null even when armed (REST names it `auto_merge`, and it
  lags a just-issued arm). Treat GraphQL as authoritative — a REST null is not "not armed", and re-arming
  on that false negative is wasted.
- The arm only fires when the base is the default branch with required status checks. On a non-default /
  stacked base, arm nothing and say `auto=none (stacked base: no required checks)`.

## Tools that read the checked-out tree, not the fetched remote
A drift / diff checker that walks the working directory sees **what is checked out**, not what you just
fetched. `git fetch` moves `origin/main` but leaves the working tree behind; the tool then double-counts or
reports phantom drift that is really the stale checkout. `git checkout <fetched-main>` (or read via
`git show <sha>:path`) before trusting such a tool. Same class: read the **committed blob**
(`git cat-file -s <sha>:<path>`) for a size, never the un-`git add`ed working file — that is the pre-edit size.

## Attribute a red before claiming it
When a gate reds, count the findings that touch your changed files before blaming the branch:
`grep -c '<your path>'` on the tool output. **Zero findings on your files + the same red reproduced on a
clean `main`** = a shared-base defect: disclose it as pre-existing and do not try to fix it inside a
rebase/docs PR. A branch that adds nothing to the failing tool's findings did not cause that red.
