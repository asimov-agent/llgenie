# Tasks — vllm-rocm-device-extras-index

- [ ] 1. `skills/engines/vllm/SKILL.md` `install.rocm` step 4: add
       `--extra-index-url https://repo.amd.com/rocm/whl-multi-arch/ --index-strategy unsafe-best-match`
       to the `-e .` editable install, with a comment naming why (vllm `get_rocm_device_requirements`
       emits `rocm[device-gfx*]`/`torch[device-gfx*]`/`torchvision[device-gfx*]` extras only served
       by the AMD index; without it uv falls back to the PyPI `rocm==0.1.0` placeholder whose poetry
       build fails under `--no-build-isolation`).
- [ ] 2. `make generate-engine-params ENGINE=vllm` regenerates `containers/engines/params/vllm.json`
       (rocm `install[3]` gains the index args); diff confirms only the rocm step changed.
- [ ] 3. Local uv resolve/dry-run proves the fix: `uv pip install --dry-run rocm[device-gfx1100]`
       with the AMD index resolves `rocm==7.14.x` (+ `rocm-sdk-device-gfx1100` etc) and does NOT
       select `rocm==0.1.0`; without the index it selects `rocm==0.1.0` (the failing class).
- [ ] 4. `make check-engine-params`, `make check-engine-source`, `make check-engine-coverage`,
       `make test-unit` green.
- [ ] 5. Engine-build vllm arch=rocm `push=false` green (run id + head sha recorded).
- [ ] 6. Engine-build vllm arch=rocm `push=true` publishes the `:rocm` image; the published digest
       answers its probe (run id + head sha recorded).
- [ ] 7. `docs/ENGINES.md` rocm row, `agent-wiki/2026-11-02-vllm-rocm-device-extras-index.md`,
       `CHANGES.md` row (+ `docs/changes.d/`), OpenSpec `tasks.md` all ticked.
- [ ] 8. `make openspec-validate NAME=vllm-rocm-device-extras-index` exits 0.
- [ ] 9. `make lane-preflight` green; PR opened against `asimov-agent/llgenie:main` referencing
       issue #1558, auto-merge armed; author gate (`check_pr_authors`) passes.
