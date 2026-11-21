# Tasks: verdict-head-neutral-2993

## 1. Change and issue

- [x] 1.1 Open the OpenSpec change (proposal, spec delta, tasks) before any code, referencing issue #2993 and the side issues #2991 / #2992.

## 2. Implementation

- [x] 2.1 `scripts/ci_verdict.py`: add the `--run-event` / `CI_VERDICT_RUN_EVENT` argument; compute `run_event` and `default_branch_head` (event neither empty nor `pull_request`).
- [x] 2.2 Extend the conclusion block: `GREEN` judged verdict + unjudged reds + `default_branch_head` -> `neutral`, exit 0; keep `success` for a clean head, `failure` for a non-green judged verdict, and the unchanged `neutral` arms for superseded/merged-straggler.
- [x] 2.3 Print the `DEFAULT-BRANCH HEAD` line naming the event, the rule, and the fact that the unjudged reds remain named.

## 3. Tests (`tests/test_ci_verdict.py`)

- [x] 3.1 Replay: green judged jobs + the measured main-head row set (`implement` failures from runs `44822618375`/`44822619990`) with event `push` -> exit 0, conclusion `neutral`, UNJUDGED RED named, `DEFAULT-BRANCH HEAD` line present.
- [x] 3.2 Replay: the same row set with no event -> exit 1, conclusion `failure` (#2116 forcing pinned).
- [x] 3.3 Replay: event `push` with a judged job failed -> exit 1, conclusion `failure`, no neutral line.
- [x] 3.4 Replay: event `pull_request` beside the specimen unjudged red -> exit 1, conclusion `failure` (the arm never touches PR heads).

## 4. Gates

- [x] 4.1 `make test-unit` exits 0 with the new tests.
- [x] 4.2 `make check-workflows` and `make openspec-validate NAME=verdict-head-neutral-2993` exit 0.
- [x] 4.3 `make lane-preflight` prints `preflight: OK` on the committed tree.
