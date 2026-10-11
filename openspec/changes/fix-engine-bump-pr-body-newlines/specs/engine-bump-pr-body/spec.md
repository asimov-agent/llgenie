# fix-engine-bump-pr-body-newlines — spec of record

## ADDED Requirements

### Requirement: the bump PR body renders with real newlines

`make engine-bump` (and the `engine-bump` workflow's **Open / update the bump
PR** step) MUST produce a PR body whose lines are separated by real newline
characters — not the two characters backslash + n — and that interpolates the
matrix values (`ID`, `OLD`, `NEW`, `REF`) and the `${{ github.repository }}`
compare URL. The body is assembled with `printf`, whose format string
interprets `\n`; it is never built from a double-quoted bash string containing
`\n` (bash does not turn `\n` into a newline inside double quotes).

#### Scenario: base body has real line breaks

- **Given** the bump step assembles the PR body for engine `ollama`
- **When** the shell runs the body-assembly `printf`
- **Then** each bullet is separated by an actual newline character and `\n` is
  nowhere in the rendered body
- **Test:** `tests/test_engine_bump_pr_body.py::test_pr_body_has_real_newlines`

### Requirement: hard-fail warning appends as a separate paragraph

WHEN a derive hard-fail was recorded (`HARD_FAIL` non-empty), the warning
paragraph MUST be appended after the base body separated by a blank line, and
MUST NOT appear when `HARD_FAIL` is empty. The append uses `printf '%b'`.

#### Scenario: hard-fail warning is appended on its own block

- **Given** a skill's derive step recorded a hard-fail
- **When** the bump step appends the manual-review warning
- **Then** the final body is `base + "\n\n> ⚠️ **Manual review required:** … hand."`
- **Test:** `tests/test_engine_bump_pr_body.py::test_hard_fail_appended`

#### Scenario: no warning when hard-fail is empty

- **Given** no hard-fail (`HARD_FAIL=""`)
- **When** the guarded append runs
- **Then** the body is exactly the base body with no warning
- **Test:** `tests/test_engine_bump_pr_body.py::test_hard_fail_absent_does_not_append`

### Requirement: a bump rewrites the unit suite's hardcoded pin asserts

`engine_bump.bump` MUST rewrite every hardcoded occurrence of the engine's old
pin in `tests/` and `README.md` so `make test-unit` stays green on the bump PR.
The shapes rewritten are the full sha, its 8-character prefix (image tags) and,
when the ref moved, the tag string and the tag with its leading `v` stripped
(`v0.35.1` and `0.35.1-rocm`). Historical records (`openspec/`, `agent-wiki/`)
and another engine's pin MUST NOT be touched. A Strata bump MUST also regenerate
`data/strata_models.json` (`make sync-strata-models`), because
`make check-strata-models` (part of `make ci-unit`) fails when that file was
built from a different pin.

#### Scenario: the bump rewrites the same pin literals the unit suite asserts

- **Given** a skill pinned at `v0.35.1` / sha `a…a` whose unit tests assert
  `releases/download/v0.35.1/…`, `FROM ollama/ollama:0.35.1-rocm`, the 8-char
  image-tag prefix and the full sha, and a newer upstream tag `v0.40.3`
- **When** `engine_bump.bump` runs
- **Then** each of those literals is the new pin, another engine's `v0.31.0`
  is unchanged, and a historical spec still says `v0.35.1`
- **Test:** `tests/test_engine_bump.py::test_bump_rewrites_hardcoded_pin_asserts`

### Requirement: an unreadable same-size GGUF is removed and fetched again

`download_top_tier_candidate` MUST treat a same-size local file whose GGUF
metadata cannot be read as damaged, not as done. `hf download` leaves such a
file in place, so the candidate MUST delete it and fetch once more before it
fails. A second unreadable result MUST still fail.

#### Scenario: a damaged same-size file is re-fetched

- **Given** the first fetch leaves a same-size file that is not a readable GGUF
- **When** `download_top_tier_candidate` verifies it
- **Then** the file is removed, fetched again, and the restored GGUF is accepted
- **Test:** `tests/test_llama_ai.py::test_unreadable_gguf_is_removed_and_refetched`

### Requirement: the generated shell validates

The `Open / update the bump PR` step's `run` block MUST remain a valid bash
script (`bash -n` passes) and the workflow YAML MUST parse without error.

#### Scenario: workflow parses and shell stays valid

- **Given** the edited `engine-bump.yml`
- **When** we run the repo's validation gates
- **Then** the YAML parses cleanly and the extracted `run` block passes `bash -n`
- **Test:** `make lint` and `make openspec-validate` plus
  `tests/test_engine_bump_pr_body.py::test_run_block_is_valid_bash`
