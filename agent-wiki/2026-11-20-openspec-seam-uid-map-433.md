# The OpenSpec CLI seam writes as the invoking user (issue #433 closed)

Date: 2026-11-20. Lane: `feat/openspec-seam-uid-map-433`. Issue: #433.

## What was verified against the spec

- `Makefile` `OS_OPTS` moved from `-u root` to
  `-u "$(shell id -u):$(shell id -g)" ... -e HOME=/tmp` — the same invoking-uid
  mapping `TEST_OPTS` proved (issue #2563). Live proof at the fixed default
  seam: `make openspec-new NAME=uidmap-probe-433` rc=0 and
  `find openspec/changes/uidmap-probe-433 -user root` = 0 entries.
- `tests/test_openspec_gate.py` pins the seam two ways: `OS_OPTS`/`TEST_OPTS`
  must name `id -u`/`id -g` and carry no `-u root` (and OS_OPTS must carry
  `HOME=/tmp`); and the set of `:=` definitions running `-u root` must equal
  exactly `{ENGINE_TEST_ARGS, CI_HOME_CLEAN}` — the docker.sock stage and the
  root-tree cleaner — with no `mk/*.mk` recipe hardcoding a root run.

## Key decisions

- The openspec image's `USER 65532` (issue #1646) is untouched: the Makefile
  always overrides `-u` anyway, and a mapped uid needs the world-writable
  `HOME=/tmp` because the Node CLI would otherwise write to a non-writable
  `/root`.
- A command-line `OS_OPTS='-u $(id -u):...'` override is a trap: Make expands
  `$(id -u)` as an (empty) MAKE variable, silently reverting to root. The seam
  must use `$(shell id -u)` inside the Makefile — the probe that exposed this
  is what re-measured #433's live state today.
- The 491 pre-existing root-owned residue dirs stay the #2477 CONFIRM-gated
  prune's job (out of scope here).

## Current status

OpenSpec change `openspec-seam-uid-map` validates; targeted gate tests 4/4
green; full unit battery + lane-preflight run at the lane head before push.
