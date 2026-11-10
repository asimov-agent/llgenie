# Reactor run-id field — tasks

- [x] `scripts/run_failure_reactor.py`: thread `run_id` into `issue_body()`; `**run:**` carries the numeric id; `displayTitle` moved to its own `**commit title:**` field; reproduction command cites the same id
- [x] `tests/test_run_failure_reactor.py`: new test renders a body and asserts it contains the run id AND the id in the suggested command equals the id in `**run:**` (fails on the pre-change renderer, passes on the change)
- [x] change-note trio (agent-wiki + docs/changes.d + CHANGES.md) keyed to #2072
- [x] `make test-unit`, `make check-wiring`, `make lint` green at the fixing head
