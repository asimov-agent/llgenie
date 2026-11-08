# Fix: the verdict names a red it did not judge, and the roster that decides it is gated

## Why

`ci-verdict` judged exactly ONE workflow. `.github/workflows/ci-verdict.yml` declares

```yaml
on:
  workflow_run:
    workflows:
      - CI
```

and GitHub matches that list VERBATIM against a workflow's top-level `name:` (no wildcard, #349).
Meanwhile `scripts/auto_merge.py` refuses the merge on ANY blocking check-run at the head, "whatever
`mergeStateStatus` says" (#1386). The two rules composed into a state the board could not express:
**verdict green, auto-merge armed, merge impossible, and nothing on the head said why.**

Measured specimen — PR #1982, head `aeac049f` (2026-11-08): `ci-verdict` `success`,
`autoMergeRequest` armed, `engine-build-pr-trigger` `failure` (run `42440650801`, job `128608980091`,
`[will] FAIL engine=surogate: wait bound (60 min) expired`). A lane that trusted the verdict saw
"green and armed" on a PR that could never merge, and had to re-diagnose the failing job from scratch.

Three `pull_request` workflows post check-runs the verdict never read: `engine-build-pr-trigger`,
`holds` and `ci-scope` (`make verdict-roster` prints the set). Every future `pull_request` workflow
joined that population silently.

## What changes

1. **`scripts/ci_verdict.py` reads the head's check-runs** (`filter=latest`; a truncated listing is
   refused exactly like `jobs_of`), resolves each blocking row to the workflow that posted it through
   the Actions run in its `details_url`, and — when the judged run is green and one of those rows
   belongs to a workflow it did not judge — posts `failure`, naming the check, the workflow and its
   run id. `BLOCKING_CONCLUSIONS` is exactly `auto_merge.RED_CONCLUSIONS`, asserted equal by a test:
   the verdict can never call a head clean that the merger will refuse. The comparison is on the
   run's **`path`**, not its `name`, because GitHub stores a run's name TRUNCATED.
2. **`scripts/verdict_roster.py` + `data/verdict-roster.json` + `make verdict-roster`** hold the
   poster population and the judged set as a **SUBSET** check (`judged <= posters`, never equality —
   the workflow set grows by design), and every poster must carry a dated judgement decision
   (`judged: true`, or `judged: false` with reason/date/issue).
3. **`make check-workflows`** (in `ci-unit`) reds on an unrecorded poster, on a `judged: true` the
   verdict does not list, on an undated exemption, on a decision that names no poster (stale), and on
   a judged workflow that cannot post at a PR head.

## What it does NOT change

- `required_status_checks` on the main ruleset (#2024) — a platform gate, and it does not make the
  verdict legible.
- The `engine-build-pr-trigger` 404-poll defect itself (#2059 / PR #2069).

## Who

ci-pipelines-maintainer — a defect in a workflow, a gate or a make target this lane owns.
