# 2026-11-11 — security: engine images serve as a non-root user (DS-0002)

Issue: the DS-0002 umbrella consolidating #2397–#2428 and #2463–#2467 (trivy
"Specify at least 1 USER command… non-root user as argument"); implementing PR opened by
the issue-bot from this change.

## What was verified

The repo's ONE renderer (`scripts/engine_skills.py`) is the single source of the non-root
guarantee, so `make check-engine-params` stays green and a future engine inherits the fix
for free:

- `render_base_dockerfile` ends every shared base with `USER 65532:65532`.
- `render_dockerfile` resets `USER root` for the build stage of any cell that compiles on the
  shared base (so `engine_runner.py install` keeps root), and ends the **final runtime stage**
  with `RUN chown -R 65532:65532 /opt/llgenie/app`, `ENV HOME=/opt/llgenie/app` and
  `USER 65532:65532` immediately before `HEALTHCHECK`/`ENTRYPOINT`.
- `scripts/engine_runner.py` makes the HF-cache `mkdir` best-effort so a read-only
  host-mounted `/models` can't crash non-root serving.
- `containers/test/Dockerfile` declares the non-root default; the harness already runs
  `-u root` (`TEST_OPTS`, `ENGINE_TEST_ARGS`) and `CI_HOME_CLEAN` now does too.
- `make generate-engine-params` regenerated the 4 base + 32 engine Dockerfiles — all 37 of
  the listed files (36 regenerated + `containers/test/Dockerfile`) now declare the non-root
  user, closing the family.

## Decisions

- Numeric `USER 65532:65532` (nobody) matches the repo's existing hardening precedent
  (`containers/ci-variant`, the scanners) and needs no `useradd` in the many base images.
- The build/install stage runs as root (reset after the base `FROM`); only the served
  process drops to non-root — compile-and-install behaviour is unchanged.
- The test image keeps a non-root default but every verification stage overrides to root,
  because the harness mounts the rw repo, the host docker socket and writes build artifacts.

## Gates

`make lint`, `make test-unit` (incl. the new engine_skills tests), `make check-wiring`,
`make check-docs`, `make check-engine-params` and `make openspec-tasks-check` are green.
The Dockerized `openspec-validate` and the engine build/serve jobs run in CI (no docker
available in this environment). The security re-scan (`make security-verdict` on `main`)
should report zero `DS-0002` after merge.
