# security-engine-pins-in-scan — proposal

Issue: [#1282](https://github.com/asimov-agent/llgenie/issues/1282)

## Why

The security scan set cannot see the dependency pins that become production engine images. Measured on
the daily-pipeline report of run 40693161435 (2026-10-28): the Syft SBOM catalogs 149 components (74
pypi) with **0 torch/vllm/sglang/litert/ziglang/mlx/ollama**; Trivy reported only
`containers/ci-variant/requirements.txt` + `tools/requirements.txt`. The engine cells pin versions in
their install strings inside `containers/engines/params/*.json`, which no scanner parses as a
dependency declaration — so a vulnerable or silently-unsatisfiable engine pin never touches the
SBOM/Trivy/Grype surface, and `#1262` documents exactly one such pin surfacing only when
`engine-build` ran.

## What Changes

At `make sbom` / `make security-scan-all` time, invent the Exact pins each cell actually installs
(from its committed `variants[*].install` lines, including every `--index-url`) into a
requirements-shaped artifact under `security-reports/engine-pins/`, run the SAME Syft/Trivy/Grype pass
over it, and make `make check-security-scan` fail while an inventoried pin is absent from the SBOM.

## Acceptance

See the four acceptance criteria on issue #1282: (1) a `make` target in `make sbom`'s dependency order
inventories the params install strings; (2) a Trivy/Syft run over that artifact reports a known-bad
engine pin with the same verdict/issue path as a `tools/` finding; (3) `make check-security-scan` fails
with the engine pins absent from the SBOM (a tightening, never a weakening); (4) the artifact is
sha-bound in the manifest like the CVE reports.
