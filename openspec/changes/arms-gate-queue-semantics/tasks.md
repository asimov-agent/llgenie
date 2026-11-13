# Tasks: arms-gate-queue-semantics

- [x] 1. `scripts/check_arms.py`: `checks_verdict` (terminal-green / in-CI / red), `queue_state`
      (armed / CLEAN-queued / review-chain in flight), `finished`, `finished_unarmed`, `state_of` per-PR
      report line; one unfiltered `gh pr list --json` call carrying `mergeStateStatus`, `reviewDecision`,
      `statusCheckRollup`.
- [x] 2. `tests/test_arms.py`: negative controls that FAIL on the pre-fix tree — mid-CI PR (IN_PROGRESS row
      and empty rollup) not a finding; CLEAN queue row not a finding; REVIEW_REQUIRED/CHANGES_REQUESTED not a
      finding; red rollup not a finding — plus the stuck class (green+APPROVED+BLOCKED, and green+BEHIND)
      stays a finding, and the single-call `--json` field lock (#1021).
- [x] 3. `.github/workflows/arms.yml`: header comments + `arms` step name carry the queue semantics (no
      trigger/permission change).
- [x] 4. Issue #2378 body synced to the measured cause and the queue-semantics fix; its AC3 reworded to a
      replayable pre-merge proof (the local `make check-arms` run at the fix head) with the post-merge arms
      dispatch recorded after landing; AC items ticked with `proven:` evidence; PR body mirrors them.
- [x] 5. Live proof at the fix tree: `make check-arms` rc=0 against the live board (0 findings; every open
      lane named in-CI/queued/in-flight — negative control against the old script's 4/4 flag at
      `2f6574ea8`); `tests/test_arms.py` battery rc=0; `make check-workflows`, `make check-wiring`,
      `make lint`, `make openspec-validate NAME=arms-gate-queue-semantics`, `make lane-preflight` rc=0.
- [x] 6. Docs pair (`agent-wiki/2026-11-13-arms-gate-queue-semantics-2378.md` +
      `docs/changes.d/2026-11-13-arms-gate-queue-semantics-2378.md` via `make changes-index`), commit with
      `closes #2378` and the ticked checklist, push, PR against main with the mirrored ticked acceptance.
      Post-merge follow-up (not a checklist item): dispatch `arms.yml` on main and record the green job id
      + 0-finding verdict in issue #2378 and the agent-wiki note.
