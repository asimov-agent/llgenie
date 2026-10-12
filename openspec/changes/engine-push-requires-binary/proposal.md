# fix(ci): refuse to push an engine image whose binary does not report a version

Issue: [#204](https://github.com/asimov-agent/llgenie/issues/204)

## Why

An engine-bump pull request publishes each changed engine x backend image.
The CI matrix builds the image, runs `make test-engine-stage`, then
`make push-engine`. The push only checks that a local image tag exists, so a
row can be published to GHCR when the engine binary is not in that image.

## What Changes

- `make push-engine` runs the image version check (`entrypoint.sh detect` and
  `info`) and does not tag or push when that check fails.
- The matrix test step stays before the push step.
- Each engine skill documents the version/help flag its own binary answers
  (`binary_flags`), and `make generate-engine-params` writes them together with
  the file each image must contain into `containers/engines/binaries.json`.
- The push check probes THAT file with THOSE flags inside the image, so every
  published image is checked against its own documentation, and a unit test
  asserts the manifest covers every engine x variant CI builds and installs.
- A backend whose CLI initialises its device at startup (`binary_probe: device`,
  e.g. vllm cuda/rocm, CI #106) must still CONTAIN the binary file; there the
  version proof is the image's own `detect`.

## Impact

- `scripts/engine_image.py`, `scripts/engine_skills.py`
- `containers/engines/binaries.json` (generated, not hashed)
- `skills/engines/*/SKILL.md` (`binary_flags`, `binary_probe`)
- `Makefile` (`push-engine` comment)
- `tests/test_engine_skills.py`
- `README.md`
