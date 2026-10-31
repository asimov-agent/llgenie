# 2026-10-31 — the engine-build producer install-leg is product-agnostic (#1196)

The #1027 split made `engine-build` a **product-LESS producer**: the `llgenie` tool
(and its `--dry`) install only in `pipeline.yml`'s `ci-install` job, which already drives
`ci-install-dry`. But `make test-engine-install` (the producer's install-leg) still called
`make ci-install-dry`, so the `.ci-home` container always lacked `$HOME/bin/llgenie` →
`Error 127` / `Makefile:1771 ci-install-dry` — every engine cell's install-leg red even on the
`make engine-launchers` fixed recipe (confirm run `41231098296`: cpu+vulkan red on install-leg;
rocm+cuda building).

## Fix (in this note's PR)

- `Makefile` `test-engine-install:` is now `engine-launchers → test-built-engine →
  ci-install-uninstall` — the product-only `ci-install-dry` is removed (the product seam owns it).
- `Makefile` `ci-install-uninstall:` now `mkdir -p ~/bin` before the foreign-file witness
  `touch ~/bin/not-ours`. The producer leg never runs `make install` (which is what creates
  `~/bin` on the witness path), so reaching this step for the first time reds with
  "No such file or directory" (confirm run `41236321425`, ollama×4 + the full matrix) — the
  mkdir restores the guarantee the witness path gets from `make install`.
- `engine-build.yml` header comment + install-leg step name no longer claim `llgenie --dry`.
- The versioned lane reference `references/engine-install-leg.md` (both `agents/` and `.hermes/`
  copies) and both `SKILL.md` copies now state the chain is engine-launchers/test-built-engine/
  uninstall and explicitly NOT `ci-install-dry`.
- Tests pin the new shape: `ci-install-dry` must be **absent** from the producer recipe
  (`tests/test_published_gate.py`, `tests/test_engine_skills.py`), and `ci-install-uninstall:`
  must `mkdir -p ~/bin` on its Linux branch before the witness touch (`tests/test_ci_images.py`).

## Gating

AC6 (measured wall-clock + image size at the measured head) is written only from a **green
re-confirm at the fixed head**, never from the falsified run `41231098296`.
