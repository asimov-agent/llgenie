# Tasks

- [x] Reproduce: the profile script died with `FileNotFoundError: 'gh'` under `env -i PATH=/usr/bin:/bin`
- [x] Resolve `gh`/`git` via `shutil.which` plus an explicit fallback dir list, then the bare name
- [x] Version the script into the tree at `agents/llgenie-pr-merge-conflict/scripts/dirty-detector.py`
- [x] Prove from the TREE path at the pushed sha: prints `conflicting: none`, exits 0, two runs byte-identical
- [x] Change-note + `docs/changes.d/` row; `check-docs`, `check-pr-base`, `check-pr-authors` green
