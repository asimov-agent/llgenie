# Spec Delta: engine-sweep-note-2529

## ADDED Requirements

### Requirement: The engine non-root sweep proof shall be repository state

The completed engine × arch non-root sweep measured on `main` SHALL be recorded in
`agent-wiki/` with its sweep table (engine, arch, published tag, image-config User) and in
`docs/changes.d/` as an index row, so the acceptance evidence for #2529 lives in the repo
and not only in run history. The recorded numbers SHALL be re-measured at a named `main`
commit with the repo's own referee (`check_engine_pins_published`) and `imagetools` reads.

#### Scenario: the note carries the full population

- **Given** the sweep completed on `main` `da2fc5adb`
- **When** the note is read at its committed state
- **Then** it names 28 committed cells, all published at fresh post-#2517 context hashes,
  the 4 disabled variants absent by design, and User `1000:1000` for every published tag

#### Scenario: the remediated cell names its verify run

- **Given** the vllm/rocm cell that failed the cutover (exit 126 on `3a4d82f5-db98981b-rocm`)
- **When** the note is read
- **Then** it names the re-verify dispatch run id (43361645161) and its `completed success`
  verdict
