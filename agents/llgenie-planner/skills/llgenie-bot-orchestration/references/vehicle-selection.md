# Choosing the surviving PR when two lanes build the same issue

Two lanes routinely produce two PRs for one issue within an hour, and a third appears when a reactor re-dispatches.
The decision is mechanical, and it is almost never "which is better".

## Decide by stack, not by merit

Measure first:

```bash
gh pr list --repo <o>/<r> --state open --limit 100 --json number,title,baseRefName,headRefOid,files
gh pr view <n> --json files --jq '[.files[].path]|join(", ")'      # per candidate
```

- **Count dependents before choosing.** If three other PRs build on one candidate's `agents/`, `Makefile` or shared
tests, that candidate survives — closing it orphans them and forces a rebase of each onto a differently shaped base.
  Keeping the stacked base costs one PR; closing it costs N.
- **Check whether they are a stack or copies before counting anything else.** A stack has each PR based on the previous
  branch; copies share one file skeleton — same `Makefile`, same manifest, same tests, same docs — with one unique file
  each. Compare `gh pr view <n> --json files` across the candidates: identical skeleton plus one distinct path per PR
  means **copies of one change**, and the first to land turns the rest into conflicts in every shared file. Selecting a
  "survivor" then merges an arbitrary subset, and resolving the others by taking one side silently drops a lane's entry.
- **Prefer the candidate on the newest base.** A vehicle cut before a base-changing merge ships a tree that is already red
  for a reason main has since fixed; the one on current `main` carries the fix.
- **Prefer the candidate that carries the union of content.** Same files plus one more is not "bigger", it is a superset —
  check by file list, then by the specific additions (a profile, a rule, a test).
- **One PR per issue, decided once.** A third vehicle needs the planner's word, not a lane's initiative; a lane that finds
  two open PRs for its issue reports and stops rather than opening a third.

## When N PRs are parallel copies, widen one and close the rest

Land **one** PR widened to carry every per-lane file, close the others with the comparison, and keep any unique *code*
(not content) as a small delta on the post-merge base. A copy of a copy is also where a file shrinks: re-seed each
lane's file from its authoritative source (the live copy) rather than transcribing it out of another PR, and check the
count after widening — the manifest gate should report one entry per directory that exists, and a missing sixth lane is
the normal way this goes wrong.

## When widening stalls, land the base alone

Widening one PR to carry every per-lane file means all of them must arrive through one branch, so it inherits that lane's
blockers — and while it waits, the shared tree is still absent from the base and every copy stays conflicted. The cheaper
fallback, once widening has missed a round: **merge the base PR as it stands**, close the copies with comparisons, and
let each remaining lane open a small PR touching exactly its own file plus one index line. Landing the base unblocks
everything; a widening that never lands unblocks nothing.

## Close with a comparison, never with a verdict

The close comment must show the reader why the work is not lost:

- a file-level or commit-level comparison table (which PR has what);
- the reason for the surviving vehicle expressed as **structure** ("four PRs stack on its manifest") rather than quality;
- the explicit sentence that the diagnosis is not rejected, and where the dependents are re-pointed;
- any improvement the closed PR had that the survivor lacks, as a follow-up item — a superseded PR usually found a real
  defect, and that finding survives the close even when the code does not.

## A "closed as duplicate" PR can still be the right base for a fix

A closed vehicle is history, not a licence to stop thinking: its branch, its tests and its close comment remain the
cheapest place to lift a fix into a reopened issue. Keep a local branch for a reopen only when a reopen bar exists;
otherwise delete it, because a stale local branch is itself a misleading artefact.

## A branch named for the issue is not a vehicle for the issue

`refs/heads/fix/<issue>-<slug>` existing on origin proves someone once pushed *something* under a plausible name —
not that the issue's work is on it. Measured: `fix/1000-hf-network-tests` sat on origin, 26 commits ahead, head
commit unrelated to the issue, base stale (did not contain current `main`), and **zero** of the markers the issue
required. A name-matching branch with the wrong content flips "the half is unlanded" to "the half looks landed".

Verify content before naming a branch as the vehicle:

```bash
git fetch -q origin refs/heads/<b>:refs/remotes/origin/<b>
git log --oneline -5 origin/<b>                     # does the head describe the issue at all?
git merge-base --is-ancestor origin/main origin/<b> # stale base => red for reasons main already fixed
git show origin/<b>:<file> | grep -c '<exact token the issue wants>'   # the work, not the name
gh pr list --json number,body --jq '.[]|select(.body|test("#<n>"))'   # a branch never implies a PR
```

When the branch's content is empty of the issue's work, report the literal count (`marker count: 0`) rather than
"the branch exists", and keep the halves assigned to lanes.

## Labels outrank a planned order

A `do-not-merge` hold is a stop, not a step. When a sweep list contains a held PR that is also the first step of a
dependency chain, the label wins: sweep what is free, report what was skipped and why, and ask the owner rather than
inventing an order that silently lifts their decision.
