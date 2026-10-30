# Tasks

- [x] 1. `scripts/llama_serve.py` is deleted; no live file imports or runs it
- [x] 2. `scripts/module_name_guard.py`: `ALLOWED_PREFIXES` drops the shim path (guard module + dated history only) and the docstring no longer describes a shim
- [x] 3. `tests/test_rename_llgenie_serve.py` drops the two shim-pinning tests and adds: the module spec is `None`, the shim path is absent, `scripts/llgenie_serve.py --help` reaches the CLI, and a resurrected shim is a guard offender
- [x] 4. Docstring/comment references to the shim in the touched files are consistent with the removal
- [x] 5. Dated `agent-wiki/` note + `docs/changes.d/` index fragment reference #816 and the PR
- [ ] 6. `make check-module-names`, `make test-unit` and `make check-docs` exit 0; `make openspec-validate NAME=retire-llama-serve-shim` exits 0 in this change
