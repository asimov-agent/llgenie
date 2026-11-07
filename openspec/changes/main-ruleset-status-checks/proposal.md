# Fix: make the `main` ruleset gate real — a guard over its required status checks

## Why

The repository's only branch protection is the `main` ruleset (id `24862727`, enforcement `active`,
target `~DEFAULT_BRANCH`), and its full rule list is exactly two: `deletion`, `non_fast_forward`
(measured `2026-11-07` via `gh api repos/asimov-agent/llgenie/rulesets/24862727`). There is **no**
`required_status_checks` rule and no merge queue (`merge_queue: null`). So a red-or-missing CI run is
**not** a platform block on a merge — GitHub only blocks when the ruleset *lists* a required check.
A commit can land on `main` with a red CI run, entirely authorised at the platform layer (e.g. #1392
merged at a head whose `linux/openspec` re-run was red). The fleet's "main stays green at merge tip"
(#1309) contract is a promise, not a guarantee, and the gap **rots silently** because nothing reads the
ruleset and alarms: a red run that files nothing, dispatches nothing and alarms nobody is a control
that does not exist.

## What changes

A guard make target `check-main-ruleset` (scripts/check_main_ruleset.py) that reads the live `main`
ruleset and **fails** when `required_status_checks` is missing, or is present but does not cover the
pinned context set this repository's own pipeline emits (subset check — a listed context the pipeline
no longer emits is reported as a named drift, never true. An extra listed context is not a finding:
the pin is an additive floor, not an exact match that reds on the next legitimate addition). It has a
consumer: a scheduled monitor workflow runs it, so the missing rule becomes a visible red run the lane
and the owner can see — a measure-and-alarm control, not a definition nobody runs.

The same script carries the **scripted ruleset update**: `main-ruleset-apply` (DRY by default) prints
the exact `required_status_checks` PUT body it would send; run with an admin token it performs the
change. The platform mutation is owner-admin-only — measured: this lane's token is `admin:false` and a
ruleset PUT returns 404/Not-Found — so the apply is a one-command, add-only, reviewed step for the
owner, never a self-mutating CI write. The guard turns green once the owner runs it; until then the
guard reports the measured gap loudly instead of silently passing.

## Who

ci-pipelines-maintainer (this lane owns gate coverage; the platform mutation is owner-admin-only, done by
the owner with the scripted apply this change ships).
