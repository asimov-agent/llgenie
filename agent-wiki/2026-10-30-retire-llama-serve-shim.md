# Retire the `scripts/llama_serve.py` shim (#816)

**Issue:** #816 · **PR:** opened from `fix/816-retire-llama-serve-shim` · **Task:** `t_7af211a6`

## Decision taken

The shim's docstring promised "removed in a follow-up" since the CLI rename (#251, 2026-10-14).
No follow-up was filed and nothing imported or ran the shim, so the deprecation window was over.

- `scripts/llama_serve.py` is deleted.
- `scripts/module_name_guard.py` loses the `scripts/llama_serve.py` entry from
  `ALLOWED_PREFIXES`: only the guard module itself and the dated history (`agent-wiki/`,
  `openspec/changes/`) are exempt. A file that comes back at the old path is now an ordinary
  offender, so the hole the shim kept in the allowlist is closed rather than guarded around.
- `tests/test_rename_llgenie_serve.py` traded its two shim-pinning tests for the rule behind
  them: `importlib.util.find_spec("scripts.llama_serve") is None`, the shim path is absent, and
  `scripts/llgenie_serve.py --help` reaches the CLI. The allowlist test now asserts a
  resurrected shim is a hit while the dated history is not.

## What was measured, not assumed

- `make check-module-names` → exit 0 (guard CLI green with the shim entry removed).
- The containerised `tests/test_rename_llgenie_serve.py` → 16 passed (test image
  `llgenie/test:latest`, `python -m pytest … -q`).
- `make check-architecture-census` is green at `main@369e191` (tracked=2002); the new commit
  changes the tree count, so the census gate is red on this branch for the reason tracked in
  #1053 (the gate measures `HEAD`, so every file-adding/removing PR must edit one shared doc).
  `docs/ARCHITECTURE.md` is deliberately untouched, per #1053's required direction.
