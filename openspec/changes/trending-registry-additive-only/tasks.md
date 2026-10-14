# Tasks

- [x] 1. `scripts/registry_keys.py`: `compare(prev, cur)` reports every kind of loss (model, key, measurement group, t/s, counter, backends/supported_engines, formats, engine entry); CLI with `--prev` (file or git rev, default `HEAD:data/models.json`) and `--cur`; exit 1 on loss
- [x] 2. `Makefile`: `check-registry-keys` target, called from `check-registry`; `tests/test_registry_keys.py` added to the `make test-unit` list
- [x] 3. `tests/test_registry_keys.py`: the loss matrix, the additive green cases (incl. a key dropped from only ONE measurement row), the real vendored registry vs itself, CLI exit codes, rules/wiring presence
- [x] 4. `AGENTS.md`: durable sections "The vendored registry is additive only" and "Agent-implemented issues always end in a monitored, green PR"
- [x] 5. `agent-wiki/2026-10-14-trending-registry-additive-only.md` records the change, its verification and the upstream issues
- [x] 6. Verification: `make lint` green, `make openspec-validate NAME=trending-registry-additive-only` exits 0, `make test-unit` green (incl. the new guard test), `make check-registry-keys` green on the committed registry, and the guard's tests RED against the pre-change tree (no `registry_keys.py`)
- [x] 7. PR opened against upstream `main` with `closes #233`, and its CI checks monitored and driven green
