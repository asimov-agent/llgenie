# Tasks

- [x] 1. `scripts/engine_pins.py`: walk every committed `containers/engines/params/*.json`, extract the
      Exact pins each cell actually installs (torch/litert-lm/ziglang + every `--index-url`) from its
      `variants[*].install` lines, and write `security-reports/engine-pins/requirements.txt` +
      `manifest.json` (sha-bound). Discovered by `make engine-pins`.
- [x] 2. Makefile: `make engine-pins`; `sbom` and `security-scan-all` depend on it (inventory before
      Syft so the SBOM covers the pins); `check-security-scan` runs the engine-pins gate.
- [x] 3. `tests/test_engine_pins.py`: the documented pin classes (a pinned torch + index, a pinned
      litert-lm, a pinned ziglang) are inventoried and sha-bound, and `check` fails when no pins are
      present or an inventoried pin is absent from the SBOM. `make ci-unit`/`test-unit` discovers it.
- [x] 4. Docs + record: `docs/SCANS.md` + `docs/SCANNERS.md` note the artifact; `agent-wiki/2026-11-06-security-engine-pins-in-scan-1282.md` +
      `CHANGES.md` index row.
- [x] 5. Verification: `make sbom` (Syft) catalogs the engine pins in `sbom.cdx.json`;
      `make security-scan TOOL=trivy` lists `security-reports/engine-pins/requirements.txt` as a target;
      `make check-security-scan` green with the artifact + SBOM present; `make check-docs`, `make lint`,
      `make test-unit` green; `make openspec-validate NAME=security-engine-pins-in-scan` valid.
