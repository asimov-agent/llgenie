# 2026-10-09 macOS pipeline parity (#120)

## What was verified
- `make test-unit`: 781 passed (hermetic, containerized).
- `make lint`: green (trailing newlines + markdown blank-line separation).
- `make openspec-validate NAME=macos-parity-install`: valid.
- `make bash-check` on this macOS host: resolves SHELL to brew's bash 5.3.15, gate passes; passing system bash 3.2 fails closed (exit 1).
- New tests in `tests/test_macos_install.py` (bash5 present / installed-when-missing / fails-closed-on-3.2 / pure-make-surface): 4 passed; full file 35 passed.

## Key decisions
- macOS pipeline is literally the same as Linux: same `make ci-<job>` targets, same order, same asserts; diverges only on the engine matrix (Linux container images, macOS native-Metal). Each OS runs `make install` per supported engine in its own environment.
- bash-5 gate: Makefile resolves SHELL to brew bash on macOS / /bin/bash on Linux; `make bash-check` (prereq of install, ci-*, loop, chained) installs via brew when missing, fails closed on 3.2. Logic lives in `scripts/check_bash.py` (single source of truth — every make command runs its Python script).
- Per-engine install proof already exists: `test-install-published` (Linux, per backend) + `test-native-engine`/`test-interactive-tensorfold-ci` (macOS native Metal). Documented + locked, not re-implemented.

## Status
- PR #121 open against upstream main (from feat/macos-parity-install), references issue #120. Issue body, OpenSpec change, and code aligned.
- Remaining tracked task (not in PR): bump `llgenie/test` image base 3.10 -> 3.11 + recompile lockfiles (large, separate change).
- Note: in this repo `origin` = upstream (asimov-agent), `andyholst` = fork; gh token is for asimov-agent so the fork push is denied — PR created as same-repo branch.
