## Why

`engine_runner.py serve` redirects the engine's real output to `$TMPDIR/engine-runner-serve.log`
**inside the container**, so `docker logs` carries only the launcher banner. When a served engine
never became ready, `engine_image.run()` printed one line —

```
[engine-image] FAIL llgenie-smoke-vllm-cpu not ready after 600s; see: docker logs llgenie-smoke-vllm-cpu
```

— and the caller removed the container in a `finally`. The only file holding the reason was destroyed
before anyone could read it, so "not ready" was indistinguishable from a silent hang.

Measured from the failing leg's own log (run `42428390792`, job `128571645259`, head `8cb8e6f7`):
`docker run -d` at `00:19:12.83`, the 600 s bound expired at `00:29:15.97`, and the job's only
container output was the `[entrypoint]` banner plus the `serve` command line — no traceback, no
progress, no reason. Filed as issue **#2080**, which this change fixes.

## What changes

`_dump_serve_log()` captures, on **both** failure paths (the readiness timeout and an early
container exit) and before the caller's `finally` removes the container:

- the in-container serve log — `docker exec <name> sh -c 'tail -c 4000 "${TMPDIR:-/tmp}/engine-runner-serve.log"'`
- the `docker logs --tail 60` tail

An engine that produced no output is named `EMPTY/absent (no engine output captured)` rather than
passing silently — a dead engine must print why.

## What does not change

- **No image tag moves.** `engine_image.py` is not one of the four tag inputs (variant params JSON,
  `Dockerfile.<variant>`, `containers/engines/entrypoint.sh`, `scripts/engine_runner.py`), so no
  engine is re-tagged and nothing is re-published.
- **No gate is weakened.** The readiness bound, the assertion and the exit code are unchanged; the
  change adds evidence, it does not relax a verdict.
- **Docker-less hosts are unaffected** — the dump is best-effort (empty output is reported as
  absent) and only runs after a failure that already returned 1.
