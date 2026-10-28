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
- **Prefer the candidate on the newest base.** A vehicle cut before a base-changing merge ships a tree that is already red
  for a reason main has since fixed; the one on current `main` carries the fix.
- **Prefer the candidate that carries the union of content.** Same files plus one more is not "bigger", it is a superset —
  check by file list, then by the specific additions (a profile, a rule, a test).
- **One PR per issue, decided once.** A third vehicle needs the planner's word, not a lane's initiative; a lane that finds
  two open PRs for its issue reports and stops rather than opening a third.

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

## Labels outrank a planned order

A `do-not-merge` hold is a stop, not a step. When a sweep list contains a held PR that is also the first step of a
dependency chain, the label wins: sweep what is free, report what was skipped and why, and ask the owner rather than
inventing an order that silently lifts their decision.
