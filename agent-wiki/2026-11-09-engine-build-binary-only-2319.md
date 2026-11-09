# engine-build: binary-only gate, serving host-only (#2319)

The engine-build CI pipeline verifies ONLY that the published engine binary answers `-h` and `--version`.
No inference-serving test runs in CI (a vllm/cpu serve-readiness wait timed out at 600s on the old serve-leg).
The serving conformance test is a host-only action: `make test-engine-host ENGINE=<id> ARCH=<arch> [MODEL=...]`
(or the `--serve` tier `make test-engine-serve`), run manually by the llgenie engine improver with the smallest
model that fits. Owner directive 2026-11-09; tracked as https://github.com/asimov-agent/llgenie/issues/2319.
