# Reproducing a CI gate failure before dispatching a fix

A red check is a claim until you reproduce it. Reproducing it locally is 30 seconds of work and
prevents dispatching a lane at the wrong file, the wrong subcommand, or a head that has already moved.

## The tree CI runs is the merge, not the head

CI checks out `refs/pull/<n>/merge` — the head merged into its base. A tarball of the PR head therefore
cannot reproduce any failure that involves a base-side script, and a gate added to `main` after the
branch was cut simply will not exist in it.

```
git fetch <remote> '+refs/heads/<branch>:refs/remotes/<remote>/<tag>'
git rev-parse --short refs/remotes/<remote>/<tag>        # MUST equal the PR's headRefOid
T=$(git merge-tree --write-tree origin/main <that ref> | head -1)
git archive $T | tar x -C /tmp/merge && cd /tmp/merge
<run the gate>
```

- **Cross-repo PRs (`isCrossRepository=true`) live on the FORK remote.** `origin` can carry a
  same-named branch at a *different* sha; fetching the wrong remote silently measured the wrong
  branch and produced a false red. Confirm `rev-parse` against `headRefOid` before trusting anything.
- `git merge-tree --write-tree` also reports conflicts by exit status, so it doubles as the
  "is this actually dirty" check.

## Run the gate the way CI runs it

- **Read the Makefile target, not the script's docstring:** `grep -n '<target>' Makefile`. A checker
  often has an unfiltered *report* subcommand and a separate *gate* subcommand, and the documented
  one can red on a pristine tree by design (it lists every grandfathered finding and exits non-zero).
- **Establish the gate's exit code on clean `origin/main` first.** If it is non-zero there, your red
  says nothing about the branch.
- When the documented invocation and the CI invocation disagree on a clean main, that is a defect in
  its own right: a lane following the docstring either "fixes" findings the gate permits or learns
  to ignore the gate. File it and route it to whoever owns gate design.

## Classify before fixing: stale base or branch defect

- A gate that landed on `main` **after** the branch was cut exposes pre-existing branch content.
  That is *a rule arriving after the code*, not a lane ignoring a rule — say which one it is, because
  the two have different remedies and different write-ups.
- For a shrink-only ratchet, conform the **new file** (import through the project's single seam) and
  never re-record the baseline: re-recording disables the gate for the next file and turns it into
  documentation. Re-recording is only correct for grandfathered content a rebase carried in.

## Hermeticity: trace the call, don't read the imports

- "No http import" is not "no network call" — a helper two levels down can import the fetcher.
  Follow the call chain from the test to the HTTP primitive before calling a test hermetic.
- **Read the cache TTL.** A disk cache measured in hours means a cold CI runner makes a live call, so
  a green run on a warm workstation proves nothing about durability. Report "current, not durable"
  and name the hermeticity issue that makes it hold tomorrow.
- A skip / marker is legitimate only when **the expectation is unchanged AND the branch behaves like
  main**. Prove it routes rather than silences: deselected mode collects nothing, selected mode
  collects everything, and a negative control (remove one mark) reds the membership census by name.
  A marker that hides a code-caused regression fails at every later head — say so in the write-up.

## Identifiers: anchored evidence, not substring proxies

- **Trailers are line-anchored.** `git log --format=%b | grep -i '^co-authored-by'`. A bare substring
  grep for an address or handle matches commit prose *about* the rule and reports a violation that
  does not exist.
- **A run id is keyed to a sha.** Amending a commit to cite a run id rewrites that sha and dangles the
  citation; post run evidence as a PR comment rather than rewriting history.
- **A status without `completed_at` is a snapshot; a job with `started_at=never` is queued, not hung.**
  Quote `status/conclusion` beside the timestamp. `cancelled` is never green, and a status that
  carries a completion time is a verdict that cannot revert.
- **A null subfield is not an absent field.** Querying `.autoMergeRequest.commitHeadOid` with a
  `// "none"` fallback prints `none` for a perfectly armed auto-merge, because that subfield is null
  whenever no head is pinned. Read the parent object before concluding; a fallback operator makes
  "null" and "missing" the same string, and one of them is a fact you would report wrongly.

## Before dispatching a fix

- **Quote `measured at <sha> <hh:mmZ>` inside the dispatch.** The relay delivers late, so a head can
  move before the message lands; a stale dispatch must identify itself so the lane can discard it.
- **Check the gate is in the preflight / fast set before telling a lane it will catch the problem.**
  A docstring claiming coverage the gate list does not have sends four PRs through a full matrix run
  each. If a pinned spec test blocks widening the list inside a lane's PR, file the follow-up issue
  rather than editing the acceptance test to fit the change.
- **Label owner-only actions explicitly (`OWNER: ...`).** A lane reads every line addressed to it as a
  task; an ambiguous board note produces a refusal, a round trip, or worse, work nobody asked for.
- **A lane's own versioned SOUL outranks a planner instruction.** When they conflict, do not override —
  file the instruction fix as an issue + PR under `agents/<profile>/`, because the fix belongs in the
  instruction and the lane's refusal was correct behaviour.
- **Never tick another lane's task checkboxes.** An unticked box is a claim that nobody measured the
  thing; ticking it fabricates verification nobody observed. Only the author ticks, citing the run.
- **"Tested good" and "mergeable" are different gates.** A behavioural PASS can still be CI-red on
  un-ticked task boxes, and a PR cannot merge while they are red. Report both or you will queue an
  unapprovable PR for approval.

## Pending and cancelled are holes, not passes

- **`failed=0, pending=2` is not "clean".** A check with no conclusion can still red, so never call a
  PR ready-for-approval while any job is pending — report `failed` and `pending` separately.
- **A re-run leaves no check-run on the commit until it starts.** During the re-run a board read shows
  *no* check at all rather than "pending"; quote the workflow run id and `run_attempt` instead of the
  check aggregate.
- **Before re-running a `cancelled` job, confirm nothing newer exists at that head.** A cancelled run
  that was superseded is history; one that was not superseded is a hole and needs `gh run rerun <id>`.
- **A cancelled run never satisfies an armed auto-merge.** The PR reads "armed and waiting" forever on
  a run that already died, which looks like a queue and behaves like an orphan.
- **A PR that has never run CI is not awaiting approval.** `gh api '…/actions/runs?head_sha=<sha>'`
  returning `total_count: 0` means no verdict exists for a signature to act on — that is a dispatch
  question, not an approval one. **`mergeable` describes the diff, never the verdict:** check
  `conclusion` per PR before listing anything as ready, or you hand the owner work that a signature
  cannot finish.
- **`mergeable=UNKNOWN` is ambiguous** — GitHub recomputes it on a just-merged PR and on a conflicted
  one alike. Resolve with `state` + `mergeStateStatus` before reporting either way.
- **A run can be hung rather than slow.** Before superseding one, prove it: `updated_at` frozen far
  past the normal band *and* the upstream service confirmed healthy, so it is not environmental. A
  substantive fix that supersedes a hung run is legitimate, because a hung run yields no verdict —
  that is different from pushing to clear a queue, and different again from a body-only edit, which
  never justifies cancelling a run. Say which of the three it was.

## Delegating a build change: scope execution, not review

When a change alters how an artifact is built, the author's own report is not evidence: a cached build
prints "no rebuild", which looks like a measurement and is not.

- Open the follow-up issue **with** the PR, delegated to the lane that owns the build, and scope it to
  execution: dispatch the pipeline and quote the run id *you* dispatched, build the changed artifact
  locally, exercise it (serve/detect/run), and record wall-clock plus per-artifact size beside the
  command that produced each number.
- A follow-up opened only after merge arrives too late to gate the PR — open it when the PR becomes
  reviewable, so verification never depends on the author.
- If the delegated lane's own rule forbids local builds, **amend that rule in the repository**; a rule
  standing against the owner's requirement gets versioned, not silently overridden.
- When a dispatch asks for a measurement the lane's rule forbids, the lane is right and the dispatch is
  wrong — accept it, then change the rule through an issue if the requirement still stands.

## Shared append files: a rebase moves the symptom, a rewrite removes the cause

A file that every change appends to — a rendered index, a changelog, a manifest — collides on nearly
every merge, and the `DIRTY` label tells you nothing about why.

```
git merge-tree --write-tree origin/main <head>                          # which paths conflict
git diff --name-only $(git merge-base origin/main <head>) <head> \
  | grep -c '^<shared file>$'                                           # does the branch really touch it
```

- **Rebasing clears the conflict without removing the change.** The hunk is re-applied onto the new
  base and lands because the base moved; the next edit to that file re-dirties the PR. A rebase is
  diagnostic of what to fix, not the fix — report it as *deferred*, never as *resolved*.
- **The fix is a rewrite** that drops the branch's hunk of the aggregate and keeps the per-change
  record the repo actually requires. Confirm the aggregate edit is unnecessary rather than assumed:
  the content/docs gates normally pass with the per-change fragment alone, so the aggregate rewrite
  is a habit, not a requirement.
- **A `grep -c` against `main` cannot tell "adds a row" from "is behind a row someone else added".**
  Both print 1. Test a real merge instead, then diff the staged result.
- **Four branches touching one append file is a process defect, not four careless lanes** — label the
  issue, and make the rule explicit where lanes read it, because nothing stops the edit by default.
- **Never regenerate a derived fixture while a known defect is still inside it.** Regenerating bakes
  the bug into the expectation, so the next lane's correct fix fails against a committed truth and its
  natural move is to regenerate again — that is how a golden stops describing the product and starts
  describing whatever the code did on the day. Regenerate once, after the defect is fixed, and if the
  suite must stay green meanwhile, mark it with the tracking issue rather than blessing the wrong row.
