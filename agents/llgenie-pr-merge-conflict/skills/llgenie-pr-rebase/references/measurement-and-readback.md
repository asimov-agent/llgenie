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

**A `MERGEABLE` PR is not automatically exempt from rebasing: `check-pr-base` can red on a mergeable head.**
`gh pr view --json mergeable` answers "does this merge cleanly", not "is the head cut from current
`main`". Every merge that lands on `main` re-stales every open head, and the resulting `check-pr-base` red
cascades into `linux/unit` and then `ci-verdict` while `mergeable` still reads `true`. Decide a rebase
from the gate itself — `make check-pr-base PR_BASE=origin/main` in a worktree at the pushed head — and
never from `mergeable` alone. Corollary: batch rounds repeat. Pushing a whole board onto `main@X` is
followed by `X` merging and re-staling all of it minutes later, so expect a second pass and do not treat
the re-stale as a mistake in the first.

Also: **re-measure run aliveness yourself immediately before a push; a coordinator's "0 in-progress runs"
can be stale.** Before force-pushing, list `gh run list --branch <b> --status in_progress` per PR. If runs
are present, decide by the workflow's own concurrency block: `cancel-in-progress: true` (e.g. `ci.yml` on
`pull_request`) means a push kills it and you wait; `cancel-in-progress: false` (e.g. `engine-build.yml`,
`engine-build-pr-trigger.yml`, whose groups are keyed on inputs/PR-number+sha and are not `push`-triggered)
means the push cannot cancel it and is safe. Confirm after the push that those runs are still `in_progress`
— that read-back is the proof you did not destroy anyone's matrix.

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

## A dispatcher's "N passed" may be the test COUNT, not the pass count
A dispatch premise like `pytest <file> -q` → "99 passed" can mean the module *holds* 99 tests of which
two fail (`2 failed, 97 passed`): total and passing coincide only when the suite is green, which is the
very thing the premise assumes. Never relay a count as evidence — run it and read the summary line, then
report `X failed, Y passed` **with the failing node ids**. When the red is neither a pre-existing one on
`main` nor caused by the rebase, the third cause is that the branch's own commit changed a file its
tests still read the old way (a workflow block moved from the workflow onto jobs, a renamed key). Prove
it on a clean extraction — `git archive <head> | tar -x -C <scratch>/v` and run there — so the shared
worktree's uncommitted state cannot be the explanation, and file the test-shape defect instead of
editing content you do not own. Beware the "assert text, not behaviour" direction too: if the cheapest
way to green is to restore what the commit deliberately removed, the test is the defect.

## Re-read the remote ref AND the local branch ref immediately before the push; `Everything up-to-date` is the tell
A lane that spends minutes in a slow gate is a lane whose branch can be repaired underneath it. Another
actor (a fix bot, the content lane) can push a new head and `reset --hard origin/<branch>` inside the
worktree you are rebasing in: your rebased commit survives only as an orphaned object while the local
branch ref points at their head, so `git push --force-with-lease` prints `Everything up-to-date` — a
success that sent nothing, with no conflict to warn you. Measure `git rev-parse <branch>`, `git
ls-remote origin refs/heads/<branch>` and `git log --oneline <main>..HEAD` as the LAST step before the
push. A lease value that no longer matches the remote, or a base older than the one the branch already
sits on, means your rebase is superseded: report it and push nothing. Never push a rebase cut on an
older `main` than the branch has — that regresses the base and re-creates the conflict you were sent to
fix. When the tree is dirty with another lane's work, preserve it twice (`git diff > <scratch>/wip.patch`
and `git stash push -m "<lane> WIP preserved by rebase lane <task>"`) before rebasing, and never
`stash drop` it — it is not yours to discard.

## Listing runs at a head: `gh run list` has `-c/--commit`, NOT `--head`

`gh run list --head <sha>` fails with `unknown flag: --head` and dumps the whole help text, which reads like
a broken environment rather than a wrong flag. The commit filter is `-c`/`--commit`:

```bash
gh run list -c <full-or-short-sha> --limit 8 --json databaseId,workflowName,status,conclusion \
  --jq '.[] | "\(.databaseId)\t\(.workflowName)\t\(.status)/\(.conclusion // "-")"'
gh run list -b <branch> --status in_progress          # branch filter + status filter are separate flags
```

Two more shapes that cost a call each: `--jq` expressions containing `\n` inside a double-quoted shell
string fail to parse (`unexpected token "\\"` — the shell hands jq a literal backslash-n outside a string),
so build multi-field output with `"\(.a)\t\(.b)"` or separate `--jq` runs instead of embedding newlines; and
`--jq` that concatenates a **string with a number** (`"  " + .databaseId`) dies with `cannot add: string and
number` — wrap the number: `(.databaseId | tostring)`. Prefer a `--json` dump piped to `jq`/`sed` when the
expression stops being one line.

Because a run's own `conclusion` is a verdict and not a cause, a `failure` row here only tells you which run
to open — the gate that actually failed comes from `gh run view <run-id> --log` filtered to
`\[check-` / `make check-` / `##\[error\]` lines.
