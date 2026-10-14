# cli-dry-run-grid — proposal

Issue: [#236](https://github.com/asimov-agent/llgenie/issues/236)

## Why

The regular PR pipeline exercises the `llgenie` CLI in pieces, but **not the INSTALLED
launcher's argument surface**. `ci-install-dry` runs `$HOME/bin/llgenie --dry` — bare, one
invocation, no arguments — and every (arch, vram, ram) dry run goes through
`scripts/llama_serve.py`, the source entry point
(`tests/test_pick_matrix_arch_perms.py`, `tests/test_pick_full_registry.py`). The installed
launcher is a generated wrapper (`~/bin/llgenie` → venv python → `scripts/llama_serve.py`),
so a wrapper that drops or mangles `"$@"` is invisible: its only test passes no arguments.

`tests/test_health.py` (installed launcher, real serve) and `tests/test_install_published.py`
(`--pick --auto --engine`, per backend) do run the wrapper, but both **serve on the runner's
real backend** — no `--dry`, no mocked arch/vram/ram. The grid coverage that exists is one
step away from the artifact.

## What Changes

- **`tests/test_cli_dry_run_matrix.py`** — the INSTALLED launcher, in dry run, over the
  mocked (arch × vram × ram) seams the permutation tests use:
  - `--matrix --vram V --ram R --arch A` for every architecture × 3 vram × 2 ram cases, and
    the positional `--matrix V R A` form, each asserted to echo the host it was given and to
    print a resolvable HF link;
  - the documented precedence (an explicit `--vram` beats a conflicting positional);
  - `--pick <model> --engine <engine> --dry` and bare `--dry` print the start command;
  - the read-only modes (`--engines`, `--trend`, `--help`) answer through the wrapper;
  - the invalid-value contract: a bad `--arch` / non-numeric `--vram` exits non-zero with a
    message naming the problem, never a silent fallback to the host's own architecture;
  - **`--dry` is dry**: the model root stays empty in every case;
  - the installed wrapper and the repo entry point agree on the same question — the test
    that makes a mangling wrapper fail.
  A missing launcher is a LOUD failure naming `make install` (AGENTS.md: no skips).
- **`make ci-install-dry-args`**, chained by `ci-install` right after `ci-install-dry`, so
  the regular pipeline runs it in the same `$HOME` `make install` wrote — in the test
  container on Linux, in the 3.11 venv on macOS. The job still runs ONE `make ci-<job>`
  target; the sub-targets are chained inside the recipe, as the other install steps are.

## Not covered

- The published path (`published.yml`'s `install-published-<backend>` → `make
  test-install-published`) already serves the installed launcher per backend; this change
  does not duplicate it.
- Wiring the *dead* target `make test-install-ci` — its own issue (#239).
