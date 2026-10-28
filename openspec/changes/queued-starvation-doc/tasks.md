# Tasks — queued-starvation-doc

- [x] 1. `docs/BOTS.md`: the **A queue is not a verdict** section, after the generated dispatch table, with the two measuring commands, the #801 distinction and the no-push rule.
- [x] 2. Measured before writing: `runner_name` is `null` for an `in_progress` job and `startedAt` is set at enqueue, so neither is a discriminator; the doc states the one that works.
- [x] 3. Real numbers quoted: `{completed: 36, in_progress: 1, queued: 3}` at 14:55Z against `queued: 18, in_progress: 0` at 14:42Z.
- [x] 4. `agent-wiki/2026-10-28-queue-is-not-a-verdict.md` + the `CHANGES.md` row.
- [x] 5. `check_docs`, `check_wiring`, `check_dispatch_forms`, `lint_linefeeds` and `make openspec-validate NAME=queued-starvation-doc` exit 0.
