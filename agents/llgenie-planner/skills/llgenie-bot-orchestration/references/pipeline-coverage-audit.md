# Auditing what the pipelines actually cover

Answering "do we have a pipeline that runs all the pipelines?" is a measurement, not a read of `ci.yml`.

## The four counts

```
ls .github/workflows/*.yml | wc -l                                  # how many exist
gh api repos/O/R/actions/workflows \
  --jq '[.workflows[]|select(.state=="disabled_manually")]|length'  # how many are OFF
for f in .github/workflows/*.yml; do grep -q workflow_dispatch $f && echo $f; done  # triggerable
grep -rn 'gh workflow run' .github/workflows/*.yml                 # anything that dispatches another
```

## Makefile coverage

```
grep -rhoE '^\s+make [a-zA-Z0-9._-]+' .github/workflows/*.yml | awk '{print $2}' | sort -u > /tmp/wf
grep -oE '^[a-zA-Z0-9._-]+:' Makefile | tr -d ':' | grep -v '^\.' | sort -u > /tmp/mk
comm -23 /tmp/mk /tmp/wf      # targets with no workflow caller
```

**State the caveat or the number lies:** "not invoked by any workflow" is **not** "never runs" — many
targets are internal (`_`-prefixed), report-only, or called by bot scripts rather than a workflow step.
The honest claim is *nobody knows which run*, and the value of the audit is turning that into a
measurement with a caller column (workflow step / script reference / none).

## The three constraints an umbrella sweep must honour

1. **A disabled workflow is reported `DISABLED`, never skipped.** Otherwise the sweep reports green
   while asserting that the off workflows work — `cancelled`-read-as-green at fleet scale.
2. **Await each dispatched run.** `gh workflow run` exiting 0 is not a verdict, exactly as
   `gh pr merge --auto` exits 0 while arming nothing (#964).
3. **`schedule` + `workflow_dispatch` only, never `pull_request`**, or the sweep doubles every PR's CI.

## Why it matters

A disabled producer is invisible from a green board: the broken thing is the *absence of a run*, and
nothing asserts on absence. Measured cases: `registry-sync` off ~56 h froze the engine registry
(#1092); `security-scan` off left #781 unprovable ~58 h.

## Reporting shape

`swept at <sha> · N ok · M failed · K disabled` plus a row per workflow: `name · run id ·
status/conclusion · completed_at`. A summary without the sha is a fact about the day, not the tree.

## Status in the repo

Filed as **#1102** (owner instruction) and delegated to `llgenie-ci-pipelines-maintainer`; the
measurement it rests on is in that issue. Two deliverables: `.github/workflows/all-pipelines.yml`
(weekly `schedule` + `workflow_dispatch`, awaits each run, reports the disabled list) and
`make targets-coverage` (caller column: workflow step / script reference / none).

**Until it lands, the standing query is:**
`gh api repos/O/R/actions/workflows --jq '.workflows[]|select(.state=="disabled_manually")|"\(.id) \(.name)"'`
— that should not have to be rediscovered by each lane that notices a producer is silent.


## Known blocker in this lane

`SKILL.md` in this profile is 101,292 b, over the 100,000-character authoring limit, so it can no
longer be patched to link a new reference. This file is therefore **unlinked** until the body is
split the way #1095 describes for the review skill. A reference nothing links is a reference nothing
loads — the same defect that issue exists to fix, confirmed here on the planner lane.
