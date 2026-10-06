## 1. Vendored registry

- [x] 1.1 `data/models.json` = upstream copy; `load_registry()` defaults to it, `LLGENIE_REGISTRY_SRC` overrides, no run-time fetch.
- [x] 1.2 `scripts/sync_registry.py` + `make sync-registry` / `make check-registry`; `check-registry` in the CI `unit` job.
- [x] 1.3 `.github/workflows/registry-sync.yml` (daily + dispatch) opens/updates a PR from `chore/registry-sync`.

## 2. Trend pick (default `llgenie`)

- [x] 2.1 `recommend()`: top 10, fits card, GGUF-reading engine with an enabled image variant, t/s then engagement.
- [x] 2.2 `gguf_repo()`: registry repo with `.gguf`, else most-downloaded `<name>-GGUF` (same org first); `download()` uses it.
- [x] 2.3 `llgenie` with no model -> model prompt -> engine prompt -> download if missing -> serve; `--auto` / no tty takes the top; `--local` keeps the local picker.

## 3. Manual mode

- [x] 3.1 `llgenie --engines [model]` lists engines (all / compatible).
- [x] 3.2 `llgenie <local> --engine <e>` and `--pick <model> --engine <e>` check compatibility (variant + skill formats) and fail naming compatible engines.

## 4. Tests

- [x] 4.1 `tests/test_trend_pick.py` in `make test-unit`: every function and CLI path, real data, live Hub, a full real GGUF download (no byte cap), pty prompts incl. invalid input; no mocks.
- [x] 4.2 `tests/test_install_trend.py` in `make test-install-ci`: pty trend pick from `~/bin/llgenie`, real download, "hi".
- [x] 4.3 `tests/test_install_published.py`: pty trend pick per backend from the installed `~/bin/llgenie`, full GGUF download, this backend's engine image answers "hi".

- [x] 4.4 `hf_download.py`: a stall under hf-xet retries with `HF_HUB_DISABLE_XET=1` (found by 4.2: xet made 0 bytes of progress on unsloth repos); `tests/test_hf_download_stall.py::test_xet_stall_falls_back_to_plain_http`.

- [x] 4.5 `engine_image._digest` retries a failed GHCR manifest lookup (found on this PR's push run: `test-published-freetoken-rocm` got an empty digest for an existing `:rocm` tag); live test `tests/test_engine_skills.py::test_digest_reads_the_live_registry_and_retries_a_failed_lookup`.

## 4b. README-exact trend list (host test feedback)

- [x] 4b.1 The list is the upstream README "Most loved" list that fits the card's nominal VRAM, in README order; unservable rows stay with the reason.
- [x] 4b.2 `data/trending-README.md` vendored with the registry; sync/check reject an order mismatch.
- [x] 4b.3 Engine t/s from this host's hardware first (CUDA/ROCm/CPU classifier as upstream).
- [x] 4b.4 Download budget: 80% of the card - 1 GiB (+70% RAM for MoE); split shards summed; MTP heads / imatrix / mmproj never picked.
- [x] 4b.5 Tests against the README itself for 6 card sizes/backends, 16 GB concrete list, bands, live upstream README, pty.

- [x] 4b.6 Every README model that fits the card is selectable: engines map to the format llgenie can fetch (GGUF, LiteRT `.litertlm`, MLX / safetensors repo snapshot); MoE GGUF budget adds system RAM; `supported_engines` without figures count.
- [x] 4b.7 `llgenie --trend` / `--select N`: the list and a pick without a terminal; unit tests cover the whole mapping, every row of the 16 GB list, and a real download of a missing model.

## 5. Docs + verify

- [x] 5.1 README: trend flow, manual mode, `make sync-registry`.
- [x] 5.2 `make lint`, `make test-unit`, `make openspec-validate NAME=feat-trend-pick-default` green.
- [x] 5.3 Issue #105, this OpenSpec change and the code agree (goal, interface, requirements, acceptance checked against proposal/spec/tasks); PR #106 references #105.
