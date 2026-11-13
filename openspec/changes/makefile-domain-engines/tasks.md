# tasks — makefile-domain-engines

## 1. The split

- [x] 1.1 `mk/engines.mk` carries ONLY the engine-domain targets (96 blocks, names + recipes byte-identical from the pre-split Makefile) — AC1
- [x] 1.2 the top `Makefile` keeps version/help/.PHONY/.DEFAULT_GOAL/environment and adds `include mk/engines.mk` beside `include mk/gates.mk` — AC2

## 2. The readers

- [x] 2.1 four readers already resolve `include mk/*.mk` (merged under #2457); the fifth,
      `scripts/unit_tests.py` (`_makefiles` + `_make_recipes`), gains the same resolver here so
      the unit-suite roster check stays sighted on moved recipes — AC2/AC3

## 3. Parity measurement

- [x] 3.1 `make -qp` target list diff EMPTY before/after (455 targets) — AC1
- [x] 3.2 `make help` byte-identical before/after — AC1
- [x] 3.3 `make check-wiring` output byte-identical pre/post split, rc=0 — AC3
- [x] 3.4 `make check-docs` output byte-identical pre/post split, rc=0 — AC3
- [x] 3.5 affected unit modules green in the test container on the split tree — AC3
- [x] 3.6 `make lint` / `make check-workflows` / `make check-dispatch-forms` green on the split tree — AC3

## 4. Documentation

- [x] 4.1 `agent-wiki/` entry referencing issue #2456 (family #800 → #2456/#2457; superseded #2454)
- [x] 4.2 `docs/changes.d/` fragment + `make changes-index` row

## 5. CI

- [x] 5.1 PR CI (ci.yml jobs that call these targets) green on the PR head; this PR closes only issue #2456 — AC4
