# tasks — restore-unsupported-comment

## 1. The move

- [x] 1.1 `mk/security.mk` loses the 5-line `# UNSUPPORTED=<file>` comment block at its tail (file ends after the `renovate-report` recipe) — AC2
- [x] 1.2 the top `Makefile` carries that block immediately above `UNSUPPORTED ?=` — AC1

## 2. Parity proof (comment-only)

- [x] 2.1 `make -qp` target-name diff against the parent tree EMPTY, rc=0 — AC3
- [x] 2.2 `make help` byte-identical against the parent tree (`cmp`) — AC3
- [x] 2.3 `make check-wiring` rc=0 — AC3

## 3. Gates

- [x] 3.1 `make lint`, `make check-workflows`, `make check-docs`, `make openspec-validate NAME=restore-unsupported-comment`, `make lane-preflight` rc=0
- [x] 3.2 hermetic unit battery `make test-unit` rc=0 on the PR head

## 4. Landing

- [x] 4.1 PR CI (CI, ci-scope, ci-verdict lanes) green on the PR head; this PR closes only issue #2639
