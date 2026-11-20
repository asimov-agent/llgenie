# Tasks: rebase-sweep-record-2950

- [x] 1. `scripts/rebase_bot_sweep.py`: print `deferred=#<n>` per entry of the sweep's deferred
      list (stdout readout only; decision semantics and exit codes unchanged). Prove with a test
      on the existing fake-gh sweep fixture.
- [x] 2. NEW `scripts/rebase_sweep_record.py` + `make rebase-sweep-record` (mk/bots.mk, .PHONY,
      package-layers.json group entry): fixed first line, per-PR lines from `LINES=<file>`,
      `--dry` prints, no `--record` posts nothing. Register the target with check-wiring's
      expectations (it is a CI-step target, so NOT host-only).
- [x] 3. `.github/workflows/rebase-bot.yml`: drain step counts dispatched (= rebased + failed)
      and accumulates `- PR #<n>: <reason>` deferral/failure lines into
      `$RUNNER_TEMP/rebase-sweep-lines.txt` (from the sweep's `deferred=#` PR numbers plus
      failed picks); a `Record the sweep summary on the tracker` step (guarded by
      `steps.drain.outputs.rebased != ''` — a crashed decision is never recorded as zeros,
      `RECORD=2652`) posts via the make target.
- [x] 4. Tests `tests/test_rebase_sweep_record.py` (summary shape, deferred count arithmetic,
      dry silence, quiet pass records, lane wiring pins `RECORD=2652` + the new step) and the
      sweep stdout deferral-line test from task 1.
- [x] 5. Gates green: `make check-wiring`, `make check-workflows`, `make check-ci-discipline`,
      `make check-docs` (docs/BOTS.md documents `rebase-sweep-record`),
      `make openspec-validate NAME=rebase-sweep-record-2950`, `make test-unit`,
      `make lane-preflight`. Issue #2950's AC items ticked with replayable proven clauses; PR
      body carries the same ACs (three-mirror rule) with `Issue: #2950` + `closes #2950` —
      #2950 is a normal issue (closes on merge) while #2652 stays open and is referenced without
      a closing keyword.
- [x] 6. Live proof: ran `make rebase-sweep-record REPO=asimov-agent/llgenie RECORD=2652
      DISPATCHED=0 REBASED=0 FAILED=0` with zero deferral lines against the live tracker;
      comment 7026720439 read back via `gh api repos/asimov-agent/llgenie/issues/2652/comments`
      (`[rebase-sweep 2026-11-20T00:45:59Z] dispatched=0 rebased=0 deferred=0`), re-run at the
      pushed head (comment id recorded in #2950's `## Technical`).
