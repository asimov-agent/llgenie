# engine-smoke

## ADDED Requirements

### Requirement: the engine smoke fetches its tiny model through the one downloader

`scripts/engine_smoke.py` SHALL fetch its per-format tiny test model by running
`scripts/hf_download.py` — the repository's single download path (the official `hf` CLI plus the
stall-watch and the auto-resume/retry loop) — and SHALL NOT call the `hf` CLI itself.

#### Scenario: a named model file is fetched through the downloader

- **Given** the smoke's tiny test model for a model format that names one file (`gguf`)
- **When** the smoke needs that model
- **Then** it SHALL run `scripts/hf_download.py` with the model's repo, that filename, the smoke
  models directory and a label
- **Test:** `tests/test_engine_smoke_fetch.py::test_fetch_model_runs_the_one_downloader`

#### Scenario: a whole-repo model is fetched through the same downloader

- **Given** the smoke's tiny test model for a format that is a whole repo (`safetensors`)
- **When** the smoke needs that model
- **Then** it SHALL ask the same downloader for the whole repo (`-` in place of the filename)
- **Test:** `tests/test_engine_smoke_fetch.py::test_fetch_model_asks_for_a_snapshot_when_the_format_has_no_filename`

#### Scenario: no bare hf download is left in the smoke

- **Given** `scripts/engine_smoke.py`
- **When** every string literal in it is read
- **Then** none SHALL build a `download` command or name the `hf` CLI
- **And** the one downloader SHALL be named
- **Test:** `tests/test_engine_smoke_fetch.py::test_no_bare_hf_download_is_left_in_engine_smoke`

#### Scenario: a failed fetch is loud

- **Given** a downloader that exits non-zero
- **When** the smoke fetches its model
- **Then** the smoke SHALL stop non-zero, naming the format and the exit code
- **Test:** `tests/test_engine_smoke_fetch.py::test_a_failed_fetch_is_loud`

### Requirement: the downloader waits the seconds the Hub's throttle names

When an `hf` CLI attempt fails and its output names a Hub throttle, `scripts/hf_download.py` SHALL
sleep the seconds the Hub states for the retry (capped, so a bogus value cannot park the job),
then retry on the existing bounded attempt budget. An attempt that names no throttle SHALL keep the
existing short pause.

#### Scenario: a throttled attempt waits the Hub's number, then succeeds

- **Given** a download whose first attempt fails with `429 Too Many Requests` and
  `Retry after 2 seconds`
- **When** the downloader decides how long to wait before its next attempt
- **Then** it SHALL wait the stated seconds
- **And** the download SHALL succeed on the next attempt
- **And** the progress log SHALL record the throttle wait
- **Test:** `tests/test_hf_download_throttle.py::test_downloader_waits_the_seconds_the_hub_names`

#### Scenario: an eternal throttle fails loudly on the bounded budget

- **Given** a download that keeps failing with a throttle
- **When** the attempts are exhausted
- **Then** the downloader SHALL exit non-zero after exactly the budget's attempts
- **And** it SHALL print the loud failure naming the log
- **Test:** `tests/test_hf_download_throttle.py::test_an_eternal_throttle_fails_loudly_on_the_bounded_budget`

#### Scenario: the wait policy matches the header form

- **Given** throttle text with the Hub's number, text with no number, an absurd number, and text
  naming no throttle
- **When** each is turned into a wait
- **Then** they SHALL be the stated seconds, the 5-minute window, the 10-minute cap, and 0
- **Test:** `tests/test_hf_auth.py::test_throttle_wait_reads_the_seconds_the_hub_names_in_text`,
  `tests/test_hf_auth.py::test_throttle_wait_defaults_and_caps_like_the_header_form` and
  `tests/test_hf_auth.py::test_throttle_wait_ignores_text_that_names_no_throttle`

### Requirement: the downloader can fetch a whole-repo snapshot

`scripts/hf_download.py` SHALL accept `-` in place of a filename and then download the whole repo
into the destination directory, by the same CLI, fast path, resume and retry rules the single-file
path uses. A destination that holds no real file yet SHALL NOT be treated as a finished download.

#### Scenario: a snapshot is fetched into the destination

- **Given** a repo whose model is a whole-repo snapshot (config.json + safetensors)
- **When** the downloader is run with `-` as the filename
- **Then** it SHALL download the repo into the destination directory in one attempt
- **Test:** `tests/test_hf_download_throttle.py::test_snapshot_download_fetches_the_whole_repo`

#### Scenario: an existing snapshot is not refetched

- **Given** a destination that already holds a snapshot
- **When** the downloader runs again with a CLI that would throttle forever
- **Then** it SHALL exit 0 without a single attempt
- **Test:** `tests/test_hf_download_throttle.py::test_an_existing_snapshot_is_not_refetched`
