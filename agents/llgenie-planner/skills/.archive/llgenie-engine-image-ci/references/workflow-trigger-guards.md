# Auditing the trigger guards on a repo's dispatchable workflows

When asked "can only the owner/collaborator/bot start these?" or "do all the dispatchable
workflows have guard rails?", audit the ACTUAL guard shape in every workflow file — never
answer from memory or from a README's prose.

## Frame it correctly first

GitHub itself refuses `workflow_dispatch` from anyone without write access, so an outsider
cannot start any dispatchable workflow upstream regardless of guards. The guard is the SECOND
line — it is what covers the events that are NOT a dispatch (`issues: [labeled]`, a fork-side
run, a re-run by a different `triggering_actor`) and what keeps the rule visible in the file.
So a missing guard is a consistency/defence-in-depth finding, not an open door. Say that.

## The audit procedure

1. Enumerate every workflow and whether it is dispatchable:
   - `workflow_dispatch` in its `on:` → dispatchable, needs a guard.
   - `workflow_call` only (a reusable pipeline) → NOT dispatchable; it runs inside the caller's
     guarded run, so the question does not apply.
2. Detect a guard ANYWHERE, not just a `guard` job:
   `grep -c -iE "collaborator|not the owner|triggering_actor|/permission" .github/workflows/*.yml`
   A guard can be a separate `guard` job OR a step inside the work job (fix-bot's is a step).
   A naive scan that only looks for a `guard` job will report a guarded workflow as unguarded.
3. For each guard, characterise what it ACCEPTS (the whole point) by reading its run block:
   - `curl .../collaborators/$ACTOR` expecting `204` → accepts ANY collaborator level,
     read/triage included. `GET /repos/{o}/{r}/collaborators/{u}` returns 204 for a
     collaborator of any permission level, so this variant is the weak one.
   - `gh api .../collaborators/$u/permission` + `case admin|maintain|write` → the correct,
     strict shape.
   - Which actor(s) it checks: `github.actor` only, or actor AND `github.triggering_actor`.
     The strict shape checks both (a re-run/dispatch by a different actor must be re-checked).
4. Check the guard is actually WIRED: the work job must `needs: [guard]` (or be transitively
   gated). A guard that fails the run via non-zero `exit` skips its dependents — that is the
   refusal mechanism.
5. Check for a DEAD output: a guard job that declares `outputs.allowed:` and writes
   `allowed=true|false` to `$GITHUB_OUTPUT` but that NO job consumes (`needs.guard.outputs.allowed`
   appears nowhere) is dead — the refusal works only through the `exit 1`. A declared-never-
   consumed output is exactly how a reviewer comes to believe a value is consulted; either
   consume it in every dependent job or drop it and say the refusal is the non-zero exit.
6. Check the tests: guard tests are often per-workflow, so a NEW dispatchable workflow with no
   guard ships unnoticed. The fix shape is a table-driven test enumerating every dispatchable
   workflow and asserting: it has an actor check that reads `.permission`, accepts only
   `admin|maintain|write`, checks both actors, and its work job depends on the guard. A
   convention without such a guard drifts.

## Decision table (guard shapes found in the wild)

| shape | what it accepts | verdict |
|---|---|---|
| `gh api .../permission` → `admin\|maintain\|write`, actor + `triggering_actor` | strict | correct |
| `gh api .../permission` → `admin\|write`, actor only | misses `maintain`, misses re-run by other actor | tighten |
| `curl .../collaborators/$ACTOR` expecting `204` | ANY collaborator level (read/triage pass) | weak — tighten |
| no actor check at all | everything | gap — add |
| `workflow_call` only | n/a (runs inside caller's guarded run) | not dispatchable |

## Pitfalls

- **An automated guard scan must look for actor/collaborator checks ANYWHERE** (job-level OR
  step-level), not just a job literally named `guard`. Step-level guards are easy to miss.
- **`/collaborators/{user}` returning 204 is NOT a write-access check.** It is a "is this user a
  collaborator at all" check and passes read/triage members. Only reading `.permission` and
  accepting `admin|maintain|write` enforces the intended rule.
- **A guard that ignores `github.triggering_actor` does not re-check a run re-dispatched by a
  different user** — the actor who started it may be fine while the person who re-ran it is not.
- **A guard output nobody reads is a lie in the file.** `outputs.allowed` written but never
  consumed makes the workflow look value-driven when the refusal is purely the exit code.
- **Guard tests that are per-workflow let a new unguarded workflow ship.** Add a table-driven
  "every dispatchable workflow carries a guard" case.

## Reporting shape

The deliverable is a per-workflow table (triggers, guard present?, what it accepts) plus the
gaps ranked by severity, then — per the repo's analysis-ships-issues rule — ONE issue with the
full table and measured evidence, no implementation unless asked. Verify the issue landed with a
read-back (`gh api .../issues/<n> --jq .title`).
