# The orchestrator tick's producer: the outbox is written before the state (issue #1125)

Issue: [#1125](https://github.com/asimov-agent/llgenie/issues/1125) · OpenSpec change:
`openspec/changes/orchestrator-tick-outbox` · Branch: `fix/1125-tick-outbox-before-state`

## What was measured

The tick dispatched work that had already merged, and each receiving lane spent a turn disproving
it: `#919` as "rebase it, head e21e7b22" 2.5 h after its merge (`d3d9dd28`, 20:51:19Z), `#1049` and
`#1050` after theirs, `#885` after `21:50:58Z`. A stale dispatch is indistinguishable from a fresh
one, so the cost is the re-measure, not the message.

## The mechanism, and the fix

The producer advanced its durable state before the side effect that consumes its output. When the
delivery failed (`queue_full` is measured on that job) the delta existed nowhere, so the next pass
diffed against the already-advanced state and re-sent a task list from memory that still looked
current.

`scripts/orchestrator_tick.py` (new) is the producer. It mirrors the shape the rebase lane proved in
its own `tally-delta.py` reporter — append-only outbox, `[measured HH:MM:SSZ]` on every line, delta
keyed on the fact — with the ordering corrected:

1. the delta is appended to `~/.llgenie/tick/outbox.log` and `fsync`ed **before** the state write;
2. each line carries the **measurement time of the fact**, read back from the record on a re-emit;
3. at emit time the subject's live state is asked (`gh pr view <n> --json state,mergedAt`,
   `gh issue view <n> --json state`) — a merged PR or a closed issue is suppressed and never emitted;
4. the delta key is the fact set, never the run time.

Facts: an open PR at `mergeStateStatus` `DIRTY`/`CONFLICTING` (`REBASE-NEEDED`), and an open
`agent:implement` issue with no live claim through `scripts/bot_claims.py` (`IMPLEMENT-READY`).

## Decisions

- **The ack is separate from the measurement, and it is the last step.** `--no-ack` prints the same
  lines and acknowledges nothing — that is exactly a delivery that was lost, which is what the
  acceptance test drives. A print that raises (`queue_full`) raises `DeliveryError`, exits 3, and
  leaves the records pending.
- **`gh` is reached only through PATH** (`--gh` selects another), so the tests run a stub — the
  repository's allowance for an external CLI, with the real request-building code still running.
- **A failed read exits 2 and writes nothing.** "We could not read" must never render as "no change",
  which is the defect class the issue was filed for.
- **Suppression is recorded, not silently dropped**: a merged subject goes into the state's
  `suppressed` list, so `make orchestrator-tick-report` can say why a line never appeared.
- The tick's own cron prompt was not edited: the planner lane owns that profile and its live skill
  directory is not in the tree (issue #791). This change ships the producer and its gates.

## Analysis: the gap this change surfaced

Two consecutive `make test-unit` runs today stalled at 67% and never finished:
`tests/test_mac_trend_pick.py::test_trend_on_a_48gb_mac_is_the_readme_list_with_metal_engines`
reaches the live Hub (`hf_auth.hub_open` via `model_engine_pick.mlx_repos`) with **no
`@pytest.mark.network`**, so the hermetic gate blocks on a socket read and pytest-timeout's 5-minute
dump does not abort it. Filed as its own issue — [#1142](https://github.com/asimov-agent/llgenie/issues/1142) —
because it is a separate objective (the routing class of #1000), not part of this change.

## Verification

- `11 passed` — `tests/test_orchestrator_tick.py` (lost delivery re-emitted verbatim, outbox durable
  when the state write fails, loud read failure, the fact's own stamp on a re-emit, merged PR
  suppressed, closed issue suppressed, silent unchanged second pass with a byte-identical outbox, the
  clock is not the key, refused delivery stays pending, `pending` twice, `report`).
- `make check-wiring` — OK, 293 documents (178 tests, 115 scripts, 287 run in CI), 301 make targets.
- `make check-docs` — OK, every one of the 272 user-facing targets documented in 8 docs.
- `make lint` — `LINT OK — all tracked text files end with a newline; markdown sections are
  blank-line separated.`
- `make openspec-validate NAME=orchestrator-tick-outbox` — `Change … is valid`.
- The proof, executed live against `asimov-agent/llgenie` at 23:31Z:

  ```
  run1  make orchestrator-tick NO_ACK=1      46 lines, stdout discarded (a lost delivery)
  run2  make orchestrator-tick NO_ACK=1      measured=46 appended=0 emitted=46
        diff outbox-lines run2-stdout        IDENTICAL (46 lines, the 23:31:04Z stamps)
  run3  make orchestrator-tick               measured=46 appended=0 emitted=46  (acknowledged)
  run5  make orchestrator-tick               exit 0, 0 stdout lines, outbox md5 unchanged
        ([orchestrator-tick] measured=48 appended=0 emitted=0 suppressed=0)
  ```

  The step from 46 to 48 facts between passes is the producer working: two issues were labelled
  `agent:implement` in the interval and were dispatched as new facts, which is why the idempotent
  pass is `run5` (over an unchanged set) rather than `run4`.

## Status

The producer, its three make targets and its docs are on the branch; the PR carries the issue
reference. The planner lane wires its cron leg to `make orchestrator-tick` on its next profile sync.
