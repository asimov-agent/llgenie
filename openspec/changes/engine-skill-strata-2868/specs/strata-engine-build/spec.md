## ADDED Requirements

### Requirement: The shipped strata cells build from the engine's own ggml at the pin

The strata cuda cell SHALL build at the skill pin using the ggml tree the engine itself vendors
(`third_party/strata-ggml`), and the install recipes SHALL NOT pass `-DSTRATA_GGML_DIR` or call
`setup.get_llama_cpp()` at pins where that call returns `None`.

#### Scenario: cuda cell at the v0.2.15 pin

- **WHEN** the engine-build cuda cell runs the skill install recipe at `v0.2.15`
- **THEN** cmake configure completes with ggml taken from the vendored tree (no
  `add_subdirectory` "is not an existing directory" error) and the cell builds green

#### Scenario: companions follow the skill in one pass

- **WHEN** `make generate-engine-params ENGINE=strata` runs after the skill is re-pinned
- **THEN** `params/strata.json` and the strata Dockerfiles carry `v0.2.15` and the same
  llama-free recipe the skill states, and `make check-engine-params` / `check-engine-source`
  / `check-engine-capabilities` pass

### Requirement: The vendored Hub model table carries the engine's per-size overrides

`scripts/strata_models.py` SHALL record, for every model the pinned `setup.py` declares, the Hub
`quant` name the files actually carry (which may differ from the MODELS key, as with
`UD-IQ4_XS-v31` shipping `UD-IQ4_XS` files) and the revision override the size lives at (as with
the v31 set's `UNSLOTH_V31_REVISION`), and `scripts/model_engine_pick.py` SHALL build its Hub
paths and plan from those per-model fields rather than family-level ones.

#### Scenario: the v31 shard set plans from its own revision

- **WHEN** a strata plan selects the `UD-IQ4_XS-v31` size
- **THEN** the plan names `UD-IQ4_XS/…-of-00004…` files at the v31 revision, and
  `make sync-strata-models` followed by `make check-strata-models` resolves every table entry
  against the pinned Hub tree with 0 problems

### Requirement: The launch line chooses key-free serving explicitly

The strata launch line SHALL pass `--api-key none` so the server takes the `explicit_no_key`
path regardless of a stray `$STRATA_API_KEY` or config `api_key`, matching how llgenie serves
every other engine inside the host's local network boundary.

#### Scenario: a polluted environment cannot re-arm the key

- **WHEN** `serve/server.py` starts from the launch line with `STRATA_API_KEY` set in the
  environment
- **THEN** `/v1/models` answers without an API key and the alias `llm-local` is listed
