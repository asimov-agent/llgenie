# rename-guard

## REMOVED Requirements

### Requirement: the old CLI module name stays a working alias

`scripts/llama_serve.py` existed so `import scripts.llama_serve` handed back the real module
and running the old path ran the CLI. The deprecation window is over: the shim is retired and
the old module name MUST NOT be importable.

## ADDED Requirements

### Requirement: the CLI has exactly one module path

The CLI entry point is `scripts/llgenie_serve.py`. `scripts/llama_serve.py` MUST NOT exist and
`scripts.llama_serve` MUST NOT be importable. The surviving entry point MUST still run — a
removal that leaves no working CLI is not a retirement.

WHEN a caller looks for the retired module
THEN it is absent, and the new module's `--help` path still works.

#### Scenario: the shim is gone and the real CLI still runs

- **Given** the checkout, where the shim has been deleted
- **When** `scripts.llama_serve` is resolved and `scripts/llgenie_serve.py --help` is run
- **Then** the module spec is `None`, the shim path does not exist, and `--help` exits 0 with usage text
- **Test:** `tests/test_rename_llgenie_serve.py::test_the_shim_is_gone_and_the_real_cli_still_runs`

### Requirement: the guard's allowlist carries only the guard and the dated record

`scripts/module_name_guard.py` refuses the retired CLI name in every live file. Its
`ALLOWED_PREFIXES` MUST name only the guard module itself and the dated history
(`agent-wiki/`, `openspec/changes/`) — never a `scripts/llama_serve.py` file path. A path that
comes back beside the guard MUST be an offender.

WHEN a live file at `scripts/llama_serve.py` exists again
THEN the guard refuses it like any other live file.

#### Scenario: a resurrected shim is an offender, the history is not

- **Given** a tree with a shim path under `scripts/`, a dated note under `agent-wiki/`, and a live doc naming the old module
- **When** the guard reads the tree
- **Then** the shim path and the live doc are hits, and the dated note is not
- **Test:** `tests/test_rename_llgenie_serve.py::test_the_guard_refuses_a_resurrected_shim_and_keeps_the_history`
