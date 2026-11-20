# Tasks: derive-leg-key-roster (issue #908)

## 1. Measure the baseline (before the rule exists)

- [x] 1.1 Record the measured counts at the branch base: agent legs in the Makefile
      (`$(AGENT_IMAGE)` recipes), workflow leg calls (direct + wrapper-mediated),
      workflows carrying them, and current roster coverage — into the PR report.

## 2. Derive the roster

- [x] 2.1 In `tests/test_agent_shell_keys.py`: derive target bodies from `makefiles_text()`,
      map every target to the legs it transitively runs (`make <leg>` / `$(MAKE) <leg>` edges),
      and scan every workflow step for `make <target>` calls.
- [x] 2.2 Assert each derived call against the leg's forwarded `-e` keys
      (minus `NON_CREDENTIAL_ENV` + forced twins) using the existing `_step_sets_key`
      job/step-env scope rule; findings name workflow, job, leg, key.
- [x] 2.3 Fail loudly when the walk finds zero leg calls (no vacuous pass), and assert the
      walk finds at least as many calls as the removed `entries` did.
- [x] 2.4 Remove the hand-kept `entries`; narrow `BOT_JOBS` to the `agent-shell-keys-check`
      assertion with a comment stating why that half stays hand-named.

## 3. Prove the rule catches the #364 shape end-to-end

- [x] 3.1 Planted-defect test: a synthetic workflow + Makefile where a job calls a leg that
      forwards `-e GH_TOKEN` and sets it only in a SIBLING step's `env:` — the derived walk
      reports the finding (fails red, then passes once the job env sets it).

## 4. Fix the gap the derived walk finds on main

- [x] 4.1 `publish-agent-image.yml`: set `TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}`
      on the `make agent-image-profiles-check` and `make hermes-smoke` steps (both legs forward
      `-e TYPESAFE_API_KEY`; no step set it).
- [x] 4.2 `make test-unit` rc=0 with the derived rule active (re-run green at the pushed head).
- [x] 4.3 `make lane-preflight` prints `preflight: OK` (rc=0) at the pushed head.
