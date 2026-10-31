# Tasks

- [x] `scripts/orchestrator_tick.py`: the producer — `measure()` (open PRs at `DIRTY`/`CONFLICTING`,
      open `agent:implement` issues with no live claim via `scripts/bot_claims.occupied()`), the fact
      key (`<KIND> #<subject> <detail>`, never the run time), the `[measured HH:MM:SSZ]` stamp taken
      from the measurement and persisted with the record, and the append-only outbox.
- [x] The ordering: outbox append + `fsync` BEFORE the state write; a record already in the outbox is
      never appended twice; a state write that fails still leaves the record durable.
- [x] The emit-time live-state filter (`gh pr view <n> --json state,mergedAt` / `gh issue view <n>
      --json state`): a merged PR or a closed issue is dropped and recorded as suppressed, never
      emitted by this or any later pass.
- [x] Delivery is acknowledged only after the lines print; a failed print raises `DeliveryError`,
      exits 3 and leaves them pending. `--no-ack` is the lost-delivery shape.
- [x] `pending` (print the undelivered lines, acknowledge nothing) and `report` (counts, exit 0)
      subcommands; a failed `gh` read exits 2 and leaves both files untouched.
- [x] `tests/test_orchestrator_tick.py`: the eleven cases the spec names — lost delivery re-emitted
      verbatim, outbox durable when the state write fails, loud read failure, the fact's own stamp on
      a re-emit, merged PR suppressed, closed issue suppressed, silent unchanged second pass with a
      byte-identical outbox, the clock is not the key, refused delivery stays pending, `pending` twice,
      `report`.
- [x] `Makefile`: `orchestrator-tick`, `orchestrator-tick-pending`, `orchestrator-tick-report` with
      `##` help lines and `.PHONY` entries (`STATE`/`OUTBOX`/`NOW`/`NO_ACK` overrides).
- [x] `docs/BOTS.md`: the producer, its three targets and the two properties (measurement stamp,
      outbox-before-state) beside the other hand-dispatch paths.
- [x] `agent-wiki/2026-10-31-orchestrator-tick-outbox.md` + its `docs/changes.d/` row rendered into
      `CHANGES.md`; `make check-docs` green.
- [x] `make openspec-validate NAME=orchestrator-tick-outbox` passes.
- [ ] Verification: `make test-unit` (the new module in the aggregator), `make check-wiring`,
      `make check-docs`, `make lint`, `make check-import-roots` — real output recorded in the wiki note.
