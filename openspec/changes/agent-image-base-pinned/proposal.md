# Change: the agent Dockerfile's TEST_IMAGE base build-arg loses its mutable `:latest` default

## Why

`containers/agent/Dockerfile` declares `ARG TEST_IMAGE=llgenie/test:latest` and
`FROM ${TEST_IMAGE}`. Trivy reports it as a dockerfile misconfig (`':latest' tag used`) — the LAST
misconfig row on `main` (`da2fc5adb`): the `containers/engines` and `containers/test` Dockerfiles
are all clean, so this one row is what keeps the daily security lane's verdict gate red after the
DS-0002 family cleared.

Every wired build path (`scripts/ci_images.py::build_args`) already passes the exact hash tag —
`--build-arg TEST_IMAGE=<ghcr hashed ref>` for every agent build (`ensure`, `_build_local`,
`_buildx_push`), locked by
`tests/test_ci_images.py::test_publish_agent_pins_the_test_image_it_builds_from`. But the default
makes a bare `docker build -f containers/agent/Dockerfile .` succeed against the mutable `:latest`
alias — the exact silent-base-drift mode the content-hash policy exists to prevent. An ad-hoc or
forgotten-path build can bake an arbitrary past test image into the bots, and their toolchain
silently drifts from the gates they enforce.

## What changes

- `containers/agent/Dockerfile`: `ARG TEST_IMAGE=llgenie/test:latest` becomes `ARG TEST_IMAGE`
  (no default). The `FROM ${TEST_IMAGE}` then fails loudly with an empty base name whenever the
  build-arg is missing, replacing a silent mutable base with a loud failure. The header comment is
  updated to state the arg is mandatory.
- `scripts/ci_images.py::build_args` is unchanged — it already always passes the hashed ref.
- `tests/test_ci_images.py`: a new text-lock test asserts the Dockerfile's `ARG TEST_IMAGE` line
  carries NO default, sitting next to the existing lock that the publish build passes the hashed
  `--build-arg`.
- `agent-wiki/` dated entry + `CHANGES.md` index row naming the issue and the PR.

## Who

llgenie-security-maintainer (the last trivy dockerfile misconfig on main).

_This OpenSpec change is the referee; the issue body (#2617) and the code conform to it._
