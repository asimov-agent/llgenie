# docs/ENGINES.md: a served engine that never becomes ready prints its own log (#2129)

**Implements:** issue #2129 — a docs-only update so `docs/ENGINES.md` describes how a failed engine
`serve` reports, which #2065 changed and the doc had not caught up with.

`ea8c239e` (#2065) changed `scripts/engine_image.py::run()` so a served engine that never becomes
ready prints the **in-container serve log** (last 4000 bytes) plus the `docker logs` tail on **both**
failure paths (readiness timeout and early exit), and names an engine that produced no output
`EMPTY/absent` instead of passing silently. The defect it fixes: `engine_runner.py serve` redirects
the engine's real output to `$TMPDIR/engine-runner-serve.log` **inside the container**, so `docker
logs` carried only the launcher banner, and `engine_smoke.py`'s `finally` destroyed the only file
holding the reason before anyone could read it. Measured on #1696 (`vllm/cpu`, run `42428390792`,
job `128571645259`, head `8cb8e6f7`): the container stayed Running for the full 600 s bound and the
job captured the banner as the ONLY line.

`docs/ENGINES.md` — the doc that owns build/serve behaviour — said nothing about this (measured
`grep -ci 'serve log|serve failure|last 4000 bytes' docs/ENGINES.md` → 0 at `2e04c9c2`). The #2065
note trio was complete, so `check-docs` stayed green while a reader of `docs/ENGINES.md` still
believed a failed serve prints only the launcher banner — the prose-one-rule-behind-the-code drift
class the docs lane exists to close.

## What changed

`docs/ENGINES.md`, the `### Engine container images` step-5 paragraph (the CI matrix cell that runs
`make test-engine-stage` and publishes), only: it now names the serve-failure dump (#2065, run
`42428390792`) beside the build/test/publish flow. No `scripts/`/`tests/`/workflow change.
