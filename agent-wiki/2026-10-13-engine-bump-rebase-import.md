# engine-bump-rebase import

Issue #214. Run 38318141627 passed the guard and failed the rebase job:
`python3 scripts/engine_bump_rebase.py` puts `scripts/` on `sys.path`, so
`from scripts.engine_bump_sync import ...` raises `ModuleNotFoundError`.
The entrypoint inserts the repo root on `sys.path` before that import.
The workflow command is unchanged.
