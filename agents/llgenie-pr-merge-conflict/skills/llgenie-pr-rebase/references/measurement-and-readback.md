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

## A post-merge gate re-read finding whose live mtime is strictly newer than the fold's mergedAt is NEXT-FOLD drift, never the landed fold's failure (issue #1464 guard #4)
After an acceptance-gate PR (*e.g. a `check_agent_profiles` fold*) merges, re-reading the gate at the
new head can still print "FAIL, N findings" — because live lanes keep editing **after** the merge. A
finding-count alone misfiles a landed fold as needing a re-fold. Correlate each finding's **live
mtime** against the fold's `mergedAt` (from `gh pr view <n> --json mergedAt`, read fresh): a finding
whose live mtime is **strictly newer** than `mergedAt` is drift that arose *after* the fold landed —
attribute it to the owning lane as the **next** fold's work, never report the current fold as failed
on it. Only a finding whose live mtime is **older than** `mergedAt` (present in the tree the fold
landed) is evidence the landed fold itself missed something. Both timestamps are facts; compare them
per finding before naming a fold.

## Cite a PR as green only from its live `check-runs` conclusions (fleet-witness rule, #1854)
When any dispatch, audit, or report cites \"PR X passed\" or \"PR X is green\" as a contrast witness, read that
PR's conclusions **from the API at the measured head** — `gh api repos/<r>/commits/<sha>/check-runs --jq
'[.check_runs[] | {name, status, conclusion}]'` — never a `mergeable` status and never a relayed claim.
A PR that is `MERGEABLE` and \"ready-for-review\" is not CI-green; a `cancelled` run (superseded by a newer
push / `cancel-in-progress`) is *not yet*, not a pass; a `failure` conclusion naming a fold is the wire fact.
The #1850 audit defect class: the audit cited its own vehicle as \"passed\" from a stale witness while the
live `guard`/`scope` runs at the head were red — `mergeable` said yes, `check-runs` said no. Prove a green
with `.conclusion == \"success\"` rows at the **current head sha** (a new push invalidates every earlier
conclusion, including your own).

## A per-lane vehicle that touches `agents/<lane>/` carries its `SYNC:` line in the same push (#1854, #1724)
Any profile-editing PR (anything that edits `agents/<profile>/SOUL.md` or a lane skill under
`agents/<profile>/`) must include `SYNC: <profile> make sync-agent-profile PROFILE=<profile>` in its body **in
the same commit/push that adds the skill edit** — the `check-pr-sync-line` (#1724) propagation rule is real and
reds a live-again vehicle whose body omits it. Never land the edit and defer the SYNC line to a re-push: the
gate reds on the wire in the gap, and a `MERGEABLE` PR red on `check-pr-sync-line` is exactly the
red-and-referenced-green failure the fleet witness rule exists to catch.
