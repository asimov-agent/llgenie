# Security lane: the engine install-string pins join the scan (issue #1282)

Implements [#1282](https://github.com/asimov-agent/llgenie/issues/1282) (one finding from this lane's
own continuous-improvement audit, scan-coverage dimension) — the engine runtime deps are no longer a
scan blind spot.

## The gap

A cell's pinned runtime deps (`torch==2.14.0`, `litert-lm==0.19.0`, `ziglang==0.17.0`) live as JSON
strings in `containers/engines/params/*.json` install lines, with the wheel index named by
`--index-url`. No scanner parses a JSON string as a dependency declaration, so a vulnerable or
silently-unsatisfiable engine pin never touched the SBOM/Trivy/Grype surface. Measured on
run 40693161435: the Syft SBOM catalogued 149 components (74 pypi) with 0 torch/vllm/sglang/litert/
ziglang/mlx/ollama, and Trivy reported only `containers/ci-variant/requirements.txt` +
`tools/requirements.txt`. `#1262` is exactly one such pin surfacing only when `engine-build` ran.

## The fix

- New `scripts/engine_pins.py`: `inventory` walks every committed `containers/engines/params/*.json`,
  extracts the Exact-version pins each cell actually installs (from its `variants[*].install` lines,
  including every `--index-url`), and writes `security-reports/engine-pins/requirements.txt` (a
  scan-consumable requirements shape) + `manifest.json` (the pins, their committed source + variant,
  and the head sha). `check` fails when no pins are inventoried, a pin is dropped, or an inventoried
  pin is absent from an existing `sbom.cdx.json`.
- Makefile: `make engine-pins`; `sbom` and `security-scan-all` depend on it (inventory before Syft so
  the SBOM covers the pins); `check-security-scan` runs the engine-pins gate (a tightening — the gate
  now fails while the engine runtime deps are out of the SBOM; no widening, no skip).

## Verification

- `make sbom` (the pinned Syft image): the generated `sbom.cdx.json` catalogues `pkg:pypi/torch@2.14.0`,
  `pkg:pypi/litert-lm@0.19.0`, `pkg:pypi/ziglang@0.17.0` (146 components total).
- `make security-scan TOOL=trivy` (the pinned Trivy image): `Results[].Target` now includes
  `security-reports/engine-pins/requirements.txt` alongside `tools/requirements.txt` — a known-bad
  engine pin reports down the same verdict/issue path as a `tools/` finding.
- `make check-security-scan`: `[engine-pins] OK: 5 engine pin(s) inventoried and (where scanned) in
  the SBOM` (exit 0).
- `tests/test_engine_pins.py` (new, behavior-based — asserts the pin *classes* torch/litert-lm/ziglang
  and the index-urls, never exact churning versions): 6 passed in the `llgenie/test:latest` venv.
- Tree measured at `main@e81ecad8`: 5 pins inventoried across freetoken/litert/tensorfold/vllm.

This lane reports scope; the fix PR for a gate this lane owns is in-scope per the dispatch
(issue #1010), never merged (#1088).
