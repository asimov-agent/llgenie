# Dispatch red-attributions are claims; the failing leg's own log is the fact

A dispatch ("these N reds are the tracked <issue> cascade, do not weight them") is triage
instruction, not evidence. Before accepting ANY red attribution from a dispatch — even one that
names a tracked no-decision/cascade issue — read the failing legs' own logs
(`gh api .../actions/jobs/<id>/logs`, curl fallback when the endpoint 404s or returns a BOM) and
confirm the failure class yourself.

## A "by-design self-red" dispatch is verified the same way — read the violations, re-run the gate

A planned self-red (the PR's own gate reds because it closes an umbrella with unticked ACs — the
#1644 reviewer-owned hold) is STILL a claim until the log says so. Read the violation detail lines
(`acceptance item N … is still - [ ] … yet the PR body closes the issue`) and match the count and
the issue number to the dispatch BEFORE writing back. Measured on #1816: dispatch said "4
violations all on #1815"; the guard log carried exactly 4 items naming #1815 AC-1..AC-4 — matched,
so the write-back was the honest remedy. Then, after both sides of the write-back, re-run the gate
on the LIVE PR body (`check_pr_acceptance.py check --body-file <live body>`) — an exit 0 after the
write-back is the authoritative "self-red cleared", independent of any CI run.

Why: a dispatcher composes the attribution from the check-run NAME and a checklist, while a leg's
log names the GATE that actually failed. The two agree only when verified. A measured instance: a
dispatch labelled three reds "the tracked cascade noise it fixes, do not weight", but the log for
the scope leg carried a genuine, unrelated `check-docs` failure — the diff changed a `scripts/*.py`
and added no `agent-wiki/<stem>.md` note. One of three reds was real and would have been laundered
under the cascade label had the logs not been read.

## Reading a leg's log reliably (exact shapes)

A `gh api .../jobs/<id>/logs` call made through bare `curl` returns **401 `Bad credentials`** — a
~112-byte JSON error body, not a log. It looks like a tiny legitimate fetch if you only check byte
count, so always assert on content (`grep -a` the gate name), never on size. The two working shapes:

```bash
# job ids for a run (--paginate + .[] errors with "expected an object but got: array")
gh api "repos/<org>/<repo>/actions/runs/<run>/jobs?per_page=100" \
  --jq '.jobs[]|select(.conclusion=="failure")|{name,failed:[.steps[]|select(.conclusion=="failure")|.name]}'

# the log itself — curl MUST carry the auth header
curl -sL -H "Authorization: token $(gh auth token)" \
  "https://api.github.com/repos/<org>/<repo>/actions/jobs/<job_id>/logs" -o /tmp/leg.log
# expect http=200 and tens of KB; ANSI escapes + BOM present, so grep with -a
```

A step whose name is `make ci-unit (...)` hides the sub-gates; the API reports the composite step
as failed and never names which target inside it reded — that granularity exists only in the log.

## Rules

- **Read the leg's log before you report or accept ANY red.** A tracked-cascade attribution is a
  hypothesis; a log line (e.g. `foreign commits (0)` measured against a stated sha) is a fact. If
  the log is unavailable for that leg, say so and do not weight the red either way.
- **Reproduce locally when the leg's log is ambiguous or heavy.** Run the failing make target in a
  worktree at head — the same ERROR line proves the red is deterministic against this diff, not a
  flake or a run-environment artifact.
- **A genuine unrelated red is a REVIEW finding.** Post it in the verdict with the file, the exact
  gate message, and the one-line fix plus which lane owns it, and correct the dispatch's premise in
  the same record. Never let a "tracked cascade" tag launder a real gate red into silence — the
  board must see it, and `mergeStateStatus` reads `BLOCKED` for a real red and a phantom alike.
- **Split the bucket explicitly**: name which reds are the tracked class (and that their logs were
  unavailable or empty), which the pre-write-back acceptance check (cleared by the tick), and which
  are real. A single "all reds are known noise" sentence is the failure shape.
- **A verdict survives its own new gate**: when the PR introduces the gate class (e.g.
  `tick-unprovable`), the write-back marker must pass THAT class — see
  `verdict-writeback-verification.md`.

## A `workflow_run` verdict leg inherits the TIP's head_sha — the log names the real subject

A `ci-verdict` job triggered by `workflow_run` runs in the context of the TIP (main's head at that
moment), so `gh api .../runs/<id>` reports `head_sha = <main tip>` for a red whose subject is an
unrelated open PR. Filtering merged-tip runs by `head_sha|startswith("<tip>")` and reading the red as
"the merged row fails" is therefore a misattribution: two consecutive `ci-verdict` failures at a
green merged tip were, by their logs, holding a *different* open PR (`[ci-verdict] run <parent-run-id>
CI head=<sha> event=pull_request pr=<n> branch=<ref> conclusion=failure`) to a missing
`ci-scope-decision` artifact — the no-decision class, not the merged issue's acceptance state.

Read the subject out of the log, never off the run's `head_sha`:

```bash
gh api "repos/<org>/<repo>/actions/runs?per_page=100" \
  --jq '.workflow_runs[]|select(.head_sha|startswith("<tip>"))|{id,name,conclusion,event}'
curl -sL -H "Authorization: token $(gh auth token)" \
  "https://api.github.com/repos/<org>/<repo>/actions/jobs/<job>/logs" -o /tmp/leg.log
grep -aE 'pr=|event=|branch=|no .ci-scope-decision. artifact|has no verdict' /tmp/leg.log
```

Classify by that line: `pr=<n>` different from the row under review ⇒ the red belongs to that PR's
row and its owning lane, and it is `no verdict` (its own bucket), never "N failures" and never a
regression of the merged row. Say the attribution out loud in the record (which PR, which run id,
which class) so a later reader does not re-litigate the merged row from a run list alone.

## Phantom-class re-citation: name the NEWEST tracked handle

When a newer tracked issue supersedes an older class label for the same phantom red (a base-moving
`check-pr-base` short-circuit that reports `foreign commits (0)`), a closure record citing only the
older handle is stale. Confirm the new tracker exists (`gh api repos/<org>/<repo>/issues/<n>`), cite
BOTH handles ("<old> class, now tracked as <new>"), and confirm the closure's green-head ancestry
chain covers the CURRENT main tip — a green at a head that is now an ancestor of live main is the
strongest closure basis: it is immune to the phantom without fabricating a new green.

## A claim measured at an old head is superseded by a merge

A gate-corrective record that says "this PR needs a further rebase" is true only while the PR is
open. If the PR merges afterwards, the old claim stands on the thread as a false instruction until
you retract it (measured 2026-11-06: #1840's 11:42Z "rebase owed" report became moot when #1840
merged 12:08:48Z at a LATER head than the comment cited). Retract ON THE SAME THREAD, quoting BOTH
shas — the one the stale claim was measured at and the merge commit that superseded it — and close
the row explicitly ("withdrawn", "superseded by merge", "no rebase owed"). A stale claim silently
standing is how a reader believes the branch is broken after it landed. Re-cite the red that
motivated the old claim as the tracked phantom class so the row reads phantom, not regression.

## The "not found" probe lines are not the red — read the line AFTER the probe

In a cache-tolerance workflow, the tolerance step probes the missing cache image
(`ERROR: <image>:buildcache-cuda: not found`) and then logs the skip
(`absent -> cold build (cache read skipped; #1842)`), and can die later from an unrelated
cause (infra/runner kill `exit 143`, a cache-PUSH auth 403). A job whose log contains a `not
found` line is NOT thereby red on the missing-cache class — the tolerance is LOGGED WORKING at that
head. Match the gate to the failing line(s): a red cell is only the class named by the step that
actually faulted (probe-skip followed by a later kill = infra-kill class; a `403 Forbidden` while
`exporting cache to registry` = cache-PUSH auth class). Read the whole cell log, never grep a
single `not found` token and call it the class. Measured #1440 (13:51Z): run 42208524862 @
dd57b47e92 had 3 red cells with distinct classes; a one-line-grep reading misattributed vllm-cuda
to the #1842 read-class (retracted 6686403156).

## Logged-working is a claim; an EXECUTED test at the live head is the proof

Reading a log line that says the tolerance fired (`absent -> cold build (cache read skipped)`) proves
only that the code branch ran on that runner. It does not prove the tree still behaves that way, and
it cannot be re-measured: the log is pinned to the run's head. When a record has to carry "this fix
works", promote the log reading to a test execution against the current PR head.

Locate the assertion, then run it — do not hand-write a probe:

```bash
# 1. where the behaviour lives (the marker the log printed)
git grep -n "absent -> cold build" refs/remotes/live/pr<n> -- scripts/
# 2. which test asserts it (search the tree for the same marker / the issue handle)
git grep -l "never-seeded registry cache\|<issue>" refs/remotes/live/pr<n> -- tests/
# 3. run it in a throwaway detached worktree at the live head
git worktree add --detach /tmp/wt<pr>live refs/remotes/live/pr<n>
cd /tmp/wt<pr>live && python3 -m pytest tests/<the_file>.py -q -k "<the marker>"
```

Quote the test file, the assertion's own docstring line, and the pass count — a docstring stating the
exact contract ("a never-seeded registry cache must not red the cell") is the strongest anchor, because
it names the behaviour rather than a symptom. A test pass certifies the *tree*; the log certifies the
*runner*. Report which one you hold.

## Check the cited head is still an ANCESTOR of the live head before measuring anything at it

A run record cites the head it ran at. That head is frequently **not** on the branch any more: the
branch advanced after the run started, and `git merge-base --is-ancestor <cited> <live head>` returns
non-zero — the pushed commit is superseded and its tree no longer exists at the tip. Never re-measure
"at the head the log came from" without this check:

```bash
git fetch origin refs/pull/<n>/head:refs/remotes/live/pr<n> --force
git rev-parse refs/remotes/live/pr<n>                      # the live head, from the wire
git merge-base --is-ancestor <cited-sha> refs/remotes/live/pr<n> || echo "superseded — measure the live head"
```

When it is superseded, say so plainly and measure the live head instead of the cited sha, then state
both shas beside the evidence ("cited `dd…`, live `14f…`, cited is not an ancestor"). A witness taken at
an orphaned head answers a question about a tree nobody can check out.

**Worktree cwd pitfall while doing this:** a shell session that `cd`s into a throwaway worktree keeps
that directory as its cwd after the worktree is removed, so every later call fails with
`cd: /tmp/wt<old>: No such file or directory` (exit 126) before running anything. Pass `workdir=`
explicitly on each command (or `git worktree add` into a fresh path and cd to it in the same call)
rather than relying on the persisted cwd.

## A described-but-never-posted corrective is a pre-merge reversal

When a planner warns that a described "update" would land as a reversal, verify what is ACTUALLY
on the wire (comment scan of the involved issues since the last known post) before posting or
retracting anything. If nothing from you exists post-that-time and no DM replay is queued, the
corrective is withdrawn BEFORE posting — never send it to "close the loop" on a stale draft
(measured 2026-11-06: #1849 "ITEM 1 NOT MET" 6684410613 was superseded by the CLOSE 6684433413
48 s later and is historical, not row state; the planner reconciliation 6685894665 is the ledger).
A pre-correction-standard record that a later post superseded is a timestamp artifact readers will
misread as the current position — acknowledge the reconciliation ON THE SAME THREAD so the newest
comment names the correct row state.
