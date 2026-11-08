# A served engine that never becomes ready must print its own log (issue #2080)

## The defect

`engine_runner.py serve` redirects the engine's real output to
`$TMPDIR/engine-runner-serve.log` **inside the container**, so `docker logs` carries only the
launcher banner. When a served engine never became ready, `engine_image.run()` printed one line —

```
[engine-image] FAIL llgenie-smoke-vllm-cpu not ready after 600s; see: docker logs llgenie-smoke-vllm-cpu
```

— and `engine_smoke.py` removed the container in a `finally`. The only file holding the reason was
destroyed before anyone could read it, so "not ready" was indistinguishable from a silent hang.

Measured from the failing leg's own log (run `42428390792`, job `128571645259`, head `8cb8e6f7`):
`docker run -d` at `00:19:12.83`, the 600 s bound expired at `00:29:15.97`, and the job's only
container output was the `[entrypoint]` banner plus the `serve` command line — no traceback, no
progress, no reason.

## What changed

`_dump_serve_log()` captures, on **both** failure paths (timeout and early exit) and before the
caller's `finally` removes the container:

- the in-container serve log — `docker exec <name> sh -c 'tail -c 4000 "${TMPDIR:-/tmp}/engine-runner-serve.log"'`
- the `docker logs --tail 60` tail

An engine that produced no output is named `EMPTY/absent (no engine output captured)` rather than
passing silently — a dead engine must print why.

## Why this is safe

- **No image tag moves.** `engine_image.py` is not one of the four tag inputs (variant params JSON,
  `Dockerfile.<variant>`, `containers/engines/entrypoint.sh`, `scripts/engine_runner.py`), so this
  re-tags no engine and re-publishes nothing.
- **No gate is weakened.** The readiness bound, the assertion and the exit code are unchanged; the
  change adds evidence, it does not relax a verdict.
- **Docker-less hosts are unaffected** — the dump is best-effort (`_sh` captures; empty output is
  reported as absent), and it only runs after a failure that already returned 1.

## What this does not do

It does not name the vllm/cpu root cause; that needs a re-run with this capture in place. Measured
context recorded on #1696 (head `8cb8e6f7`): `vllm-cpu` was **success** at branch head `0e840035`
(run `42391726947`, serve-leg 16:38:17→16:42:23 = 4 m 06 s) and **failure** at `cbe99416`,
`037abb73`, `8cb8e6f7` — green → red on the same branch, with the cpu variant differing only by
`env += UV_HTTP_TIMEOUT=180`, which forces a full rebuild of the cpu image. Two candidates remain,
distinguishable only by the captured log.

## Files

- `scripts/engine_image.py` — `_dump_serve_log()` and both failure paths calling it.
- `tests/test_engine_image_serve_log.py` — the regression tests (red on the parent).
- `openspec/changes/engine-image-serve-log-on-failure/` — this change.
