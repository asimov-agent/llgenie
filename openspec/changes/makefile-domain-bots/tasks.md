# Tasks: makefile-domain-bots

## 1. Baseline
- [x] 1.1 Record the pre-split baseline: target set, `make help`, `make check-wiring`, `make check-docs` from `origin/main`
- [x] 1.2 Confirm the 72-target bot roster has zero overlap with the ci (#2458) and security (#2459) rosters

## 2. Split
- [x] 2.1 Extract the 72 bot-domain blocks (span: target header → blank line, next target header or variable assignment, tracking `ifeq/else/endif` depth) into `mk/bots.mk`
- [x] 2.2 Add `include mk/bots.mk` beside the existing includes; leave banners, variables, `version`/`help`/.PHONY/DEFAULT_GOAL in the top Makefile

## 3. Parity
- [x] 3.1 `make -qp` filtered target lists identical to baseline
- [x] 3.2 `make help`, `make check-wiring`, `make check-docs` byte-identical to baseline
- [x] 3.3 Re-point every blind Makefile-text reader (test or guard slicing a moved bot target from the top file) through the include-resolving reader

## 4. Docs
- [x] 4.1 agent-wiki note + docs/changes.d row + CHANGES.md row

## 5. Verification
- [x] 5.1 `make lane-preflight` OK
- [x] 5.2 Full `make test-unit` battery green on the final squashed head
- [x] 5.3 `make openspec-validate NAME=makefile-domain-bots` passes
- [x] 5.4 PR CI (main CI + ci-scope + ci-verdict) green at the PR head
