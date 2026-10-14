# cli-dry-run-grid

## ADDED Requirements

### Requirement: the installed launcher's argument surface runs in dry run over the mocked grid

The INSTALLED launcher (`~/bin/llgenie`, the wrapper a user runs) MUST be exercised, in dry
run, with its documented argument surface over the mocked (arch, vram, ram) seams: the
`--matrix` flag form and the positional form for every architecture the pipeline serves,
`--pick <model> --engine <engine> --dry`, bare `--dry`, and the read-only modes. Each case
MUST assert the launcher answered for the host it was given, and MUST assert the run stayed
dry (nothing downloaded, no server started). A missing installed launcher MUST be a loud
failure naming `make install` — never a skip.

WHEN the regular PR pipeline reaches the install stage
THEN the installed launcher's own argument surface has been exercised over the mocked
arch x vram x ram grid, in dry run.

#### Scenario: the flag form echoes the mocked host it was given

- **Given** the installed launcher and a mocked host of each architecture, vram and ram
- **When** `llgenie --matrix --vram V --ram R --arch A` runs
- **Then** it exits 0, the header names exactly that (arch, vram, ram) as the flag form, and a resolvable HF link is printed
- **And** the model root stays empty, so nothing was downloaded
- **Test:** `tests/test_cli_dry_run_matrix.py::test_the_installed_launcher_matrix_flags_echo_the_mocked_host`

#### Scenario: the positional form and the flag precedence survive the wrapper

- **Given** the installed launcher
- **When** the positional `--matrix V R A` form runs, and when a positional GB conflicts with an explicit `--vram`
- **Then** the positional form prints the positional header (no flag marker) with the same host, and the explicit flag wins over the positional
- **Test:** `tests/test_cli_dry_run_matrix.py::test_the_installed_launcher_positional_matrix_form_agrees`
- **Test:** `tests/test_cli_dry_run_matrix.py::test_the_installed_launcher_flags_beat_a_conflicting_positional`

#### Scenario: the dry-run forms print a command and run nothing

- **Given** the installed launcher and a registry model from the smoke registry
- **When** `--pick <model> --engine <engine> --dry`, bare `--dry`, `--engines`, `--trend` and `--help` run
- **Then** each exits 0, the pick and the bare dry run print the command they would run, no mode reports a server as started, and the model root stays empty
- **Test:** `tests/test_cli_dry_run_matrix.py::test_the_installed_launcher_pick_engine_dry_run_prints_the_start_command`
- **Test:** `tests/test_cli_dry_run_matrix.py::test_the_installed_launcher_dry_run_is_the_serve_command`
- **Test:** `tests/test_cli_dry_run_matrix.py::test_the_installed_launcher_read_only_modes_answer`

#### Scenario: an invalid value fails loudly, never falls back to the host

- **Given** the installed launcher
- **When** an unknown `--arch` and a non-numeric `--vram` are asked for
- **Then** each exits non-zero with a message naming the problem
- **And** nothing is downloaded
- **Test:** `tests/test_cli_dry_run_matrix.py::test_an_invalid_arch_or_vram_fails_loudly_through_the_wrapper`

### Requirement: the installed wrapper and the repo entry point answer the same question

The installed launcher is a generated wrapper around the venv python and
`scripts/llama_serve.py`. A wrapper that drops or mangles `"$@"` MUST fail a named test: the
installed command and the repo entry point MUST be asserted to answer the same
`--matrix` question identically (header and offered links).

WHEN the wrapper loses an argument
THEN the agreement test fails, because the installed launcher no longer answers the question
the repo entry point does.

#### Scenario: wrapper and entry point agree

- **Given** the installed launcher and the same mocked host
- **When** both answer `--matrix --vram 24 --ram 64 --arch rocm`
- **Then** both exit 0, the installed one prints the flag-form header for that host, and their offered links are identical (and non-empty)
- **Test:** `tests/test_cli_dry_run_matrix.py::test_the_installed_wrapper_agrees_with_the_repo_script`

### Requirement: the stage is part of the regular pipeline's install job

`make ci-install-dry-args` MUST run the test in the same `$HOME` that `make install` wrote
(Linux: the test container; macOS: the 3.11 venv) and MUST be chained by the `ci-install`
recipe, so the install job of the regular PR pipeline runs it without adding a second
workflow step or a second `make ci-*` target.

WHEN `make ci-install` runs
THEN the installed launcher's dry-run argument surface has been exercised right after the
install and before the uninstall.

#### Scenario: the install job chains the dry-run argument stage

- **Given** the Makefile
- **When** the `ci-install` recipe is read
- **Then** it chains `test-env`, `ci-install-run`, `ci-install-dry`, `ci-install-dry-args` and `ci-install-uninstall`, and the new target runs the launcher test in the same container (Linux) / venv (macOS) and is phony
- **Test:** `tests/test_ci_images.py::test_every_pipeline_job_runs_one_ci_make_target`
