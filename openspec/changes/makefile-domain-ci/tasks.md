# tasks — makefile-domain-ci

## 1. The split

- [x] 1.1 `mk/ci.mk` carries ONLY the ci-domain targets (20 blocks, names + recipes byte-identical from the pre-split Makefile, `ifeq`-guarded recipe bodies included; the ci-<job> section banner stays in the top Makefile at its original position, engines-split precedent) — AC1
- [x] 1.2 the top `Makefile` keeps version/help/.PHONY/.DEFAULT_GOAL/environment and adds `include mk/ci.mk` beside `include mk/gates.mk` — AC2

## 2. The readers

- [x] 2.1 every Makefile-text reader resolves `include mk/*.mk` (merged under #2457 + PR #2635); verify no reader goes blind on the ci split — AC2/AC3

## 3. Parity measurement

- [x] 3.1 `make -qp` target list diff EMPTY before/after — AC1
- [x] 3.2 `make help` byte-identical before/after — AC1
- [x] 3.3 `make check-wiring` output byte-identical pre/post split, rc=0 — AC3
- [x] 3.4 `make check-docs` output byte-identical pre/post split, rc=0 — AC3
- [x] 3.5 affected unit modules green in the test container on the split tree — AC3
- [x] 3.6 `make lint` / `make check-workflows` / `make check-dispatch-forms` green on the split tree — AC3

## 4. Documentation

- [x] 4.1 `agent-wiki/` entry referencing issue #2458 (family #800 → #2456/#2457/#2458; superseded #2454)
- [x] 4.2 `docs/changes.d/` fragment + `make changes-index` row

## 5. CI

- [x] 5.1 PR CI (ci.yml jobs that call these targets) green on the PR head; this PR closes only issue #2458 — AC3
