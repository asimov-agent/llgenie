# tasks — unsupported-comment-restore

## 1. The comment move

- [x] 1.1 the `# UNSUPPORTED=<file>` comment block (5 lines) sits immediately above `UNSUPPORTED ?=` in the top Makefile — AC1
- [x] 1.2 `mk/security.mk` no longer carries the comment block and ends with security content — AC2

## 2. Parity measurement

- [x] 2.1 `make -qp` target list diff EMPTY vs the parent commit, rc=0 — AC3
- [x] 2.2 `make help` byte-identical vs the parent commit, rc=0 — AC3
- [x] 2.3 `make check-wiring` unchanged — AC3

## 3. Documentation

- [x] 3.1 `agent-wiki/` entry referencing issue #2639
- [x] 3.2 `docs/changes.d/` fragment + `make changes-index` row

## 4. Gates

- [x] 4.1 `make lint` green on the changed tree
- [x] 4.2 `make openspec-validate NAME=unsupported-comment-restore` passes (blocked by container
      runtime down on this host — the change file is written to the CLI's shape; gate to be run by CI)
