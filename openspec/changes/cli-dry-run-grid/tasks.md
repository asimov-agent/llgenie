# Tasks

- [x] 1. `tests/test_cli_dry_run_matrix.py` drives the INSTALLED launcher (`LLGENIE_LAUNCHER` or `$HOME/bin/llgenie`) in dry run, failing loudly when it is missing
- [x] 2. It covers the `--matrix` flag form for every architecture × vram × ram of the mocked grid, the positional form, and the flag-beats-positional precedence
- [x] 3. It covers `--pick --engine --dry`, bare `--dry`, the read-only modes, and the invalid-arch / non-numeric-vram contract
- [x] 4. Every case proves the run stayed dry (the model root stays empty) and the wrapper agrees with the repo entry point on the same question
- [x] 5. `make ci-install-dry-args` runs it (container on Linux, venv on macOS) and is chained by `ci-install`, so the regular PR pipeline runs it in the same `$HOME` `make install` wrote
- [x] 6. README documents the stage; the new target is in `.PHONY`
- [x] 7. In `llgenie/test:latest` after `make ci-install-run`: `make ci-install-dry-args` passes, and breaking the installed wrapper's `"$@"` makes it fail (the demonstration the issue asks for)
- [x] 8. Issue #236 reflects the wiring as implemented
