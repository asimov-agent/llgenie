# OpenSpec gate blindness — an implementing PR can be openspec-empty and still green

## Lesson (2026-11-05, issue-refiner #1806 + fleet #1803/#1801/#1799/#1797/#1795)

`make ci-openspec` (= `openspec-validate-all` + `openspec-tasks-check`) validates the STRUCTURE and task-completion of whatever ACTIVE changes already exist under `openspec/changes/*`. It iterates over existing changes — it CANNOT see "this implementing PR added no change of its own." So an openspec-empty implementing PR is CI-green (`linux / openspec` = SUCCESS) while AGENTS.md:27-53 declares OpenSpec MANDATORY and change-FIRST for every change.

## The trap
An openspec-empty implementing PR passes all gates. The discipline (create the change first, per 104 historical commits) can lapse silently PR after PR and no check reds.

## Fix shape that worked
- **On the vehicle** (planner does NOT implement): require the owning lane to add its own `openspec/changes/<name>/` (proposal.md + specs/<cap>/spec.md + tasks.md, all `- [x]`) to the EXISTING PR — same sole vehicle, no second PR.
- **File the gate gap** (#1807): `ci-openspec` must red an implementing PR whose diff adds no `openspec/` path, unless the body names an exact existing change it implements against. Red-on-old / green-on-fixed tests; reuse openspec scaffolding, never weaken validate/tasks-check.
- Owners may place `do-not-merge` during the dispute; a hold with no resolving issue reds the `holds` gate (issue #948). Write the exit condition as a comment with a resolve-verb + issue number (regex `resolves|fixed by|blocked by|until|exit condition|pending|awaiting` + `#N`) — `check_holds.py` REMEDY regex. Never remove an owner's label; write its remedy.

## Evidence-verify before claiming
Fetch the PR file list (`gh pr view N --json files`), filter `openspec`; read tasks.md tick state at the head sha; confirm `linux / openspec` at that head. A comment remedy must match `check_holds.py`'s own regex before calling the holds gate satisfiable.

No second vehicle, no gate weakening, no merge by planner; the fix rides the owning lane's existing PR.

(Auto-merge arming under single-token authorship and the `REVIEW_REQUIRED` owner-only gate live in
`incident-closure-and-board-mutation.md` — that is the merge-authority reference, not this openspec one.)
