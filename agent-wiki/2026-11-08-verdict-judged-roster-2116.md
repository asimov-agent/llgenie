# the verdict names a red it did not judge (issue #2116) — 2026-11-08

**Implements:** issue #2116 — `ci-verdict` judged exactly ONE workflow. `.github/workflows/ci-verdict.yml`
declares `on.workflow_run.workflows: [CI]`, and GitHub matches that list VERBATIM against a workflow's
top-level `name:` (no wildcard, #349), while `scripts/auto_merge.py` refuses the merge on ANY blocking
check-run at the head, "whatever `mergeStateStatus` says" (#1386). The two rules composed into a state
the board could not express: **verdict green, auto-merge armed, merge impossible, and nothing on the
head said why.**

Measured specimen this change reproduces through the shipped code — PR #1982, head `aeac049f`
(2026-11-08):

| surface | value |
|---|---|
| `ci-verdict` check-run | `success` |
| `autoMergeRequest` | armed |
| `engine-build-pr-trigger` | `failure` (run `42440650801`, job `128608980091`) |
| that job's own log line | `[will] FAIL engine=surogate: wait bound (60 min) expired — producer run 42440668074 never concluded, last status 404` |

Re-measured at the branch head with `make ci-verdict REPO=asimov-agent/llgenie RUN_ID=42440650781
HEAD_SHA=aeac049f…`: the judged run's own jobs are all green (`verdict=green success=10 failure=0`), and
the shipped code now exits **1** and posts `conclusion=failure` naming
`check 'trigger' conclusion=failure workflow='engine-build-pr-trigger…' run=42440650801`. The three
`pull_request` posters outside the judged set at this sha are `engine-build-pr-trigger.yml`,
`holds.yml` and `scope.yml` — `make verdict-roster` prints them beside the judged `ci.yml`.

## What changed

- **`scripts/verdict_roster.py`** (new) — the roster half. `poster_workflows()` (every workflow whose
  `on:` carries `pull_request`/`pull_request_target`, keyed by FILE), `judged_workflows()` (the verbatim
  `workflow_run.workflows` names), `judged_files()` (that roster resolved to files), and
  `coverage()`: a poster with no decision, a `judged: true` the verdict does not list, an undated
  exemption, a decision naming no poster (STALE), and `judged <= posters` as a **SUBSET** check — never
  equality, because the workflow set grows by design.
- **`data/verdict-roster.json`** (new) — one dated decision per poster: `judged: true` for `ci.yml`,
  `judged: false` + reason/date/issue for the three deliberately-unjudged posters.
- **`scripts/ci_verdict.py`** — reads the head's check-runs (`filter=latest`, truncation refused like
  `jobs_of`), resolves each blocking row to its workflow through the Actions run in its `details_url`,
  and returns the ones the verdict did not judge. `BLOCKING_CONCLUSIONS` is exactly
  `auto_merge.RED_CONCLUSIONS` (a test asserts the equality, so the verdict cannot call a head clean
  that the merger refuses). A green judged run with an unjudged blocking check-run posts `failure` and
  names each check with its workflow and run id; `--checks FILE` makes the read replayable.
- **`scripts/check_workflows.py`** — `check_verdict_roster()` added to `findings()`, so a new
  `pull_request` workflow with no judgement decision reds `make check-workflows` (`ci-unit`).
- **`Makefile`** — `make verdict-roster` (the report), `.PHONY`-declared.
- **`docs/BOTS.md`** — the target and the rule; **`.github/workflows/ci-verdict.yml`** header — the flow
  and the unjudged-red rule.
- **Tests** — `tests/test_verdict_roster.py` (the roster, every refusal proven on a temp tree built by
  the test) and 6 new cases in `tests/test_ci_verdict.py` (the specimen, the own-row/judged-row
  exemptions, the CLI red + named run id, the restored-green control, the foreign-app row, and the
  blocking-set equality).

## Decisions

- **`path` is the identity, never the run's `name`.** Measured: GitHub stores the run name TRUNCATED
  (`… waits on it (issue` — the file's `name:` ends `(issue #1633)`), so a roster matched on the name
  would silently fail for any long-named workflow. `workflow_of()` returns `{name, path}` and the
  comparison is `basename(path)` against the judged files.
- **The verdict reds rather than going `neutral`.** The issue offered "`failure` or a clearly-labelled
  `neutral`"; `neutral` is itself in `auto_merge.RED_CONCLUSIONS` and would read as the superseded-head
  answer, which it is not. A head whose merge is blocked is `failure`, and the body says exactly which
  check and which run.
- **Not `required_status_checks`** (that is #2024) and **not** the `engine-build-pr-trigger` 404-poll
  defect (#2059 / PR #2069): this change only makes the verdict NAME what it did not judge.

Refs: #2116 (this issue), #349 (verbatim `workflow_run` matching), #1386 (a red check-run blocks the
merge), #1111 (the verdict itself), #2024 (the platform gate, out of scope), #2059 (the 404 poll, out of
scope).
