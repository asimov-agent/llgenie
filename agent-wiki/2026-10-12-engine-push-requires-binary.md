# Engine push requires the binary

Issue #204. `make push-engine` used to publish any local image tag. It now
runs `test_image` and does not tag or push unless the engine binary file
exists in the image and answers the version/help flag that engine documents. A
Python import does not count.

Each servable skill documents its flags in `binary_flags` (llama.cpp, ollama,
vllm and freetoken answer `--version`; sglang, strata, tensorfold, litert, mlx,
exllamav3 and tensorrt-llm answer `--help`), and `make generate-engine-params`
writes them into `containers/engines/binaries.json` next to the file each image
must contain. The probe reads that manifest - generated files only, never a
skill - and tries the documented flags first, with `--version -h --help` as the
fallback. Neither the path nor the flags go into the hashed params, so published
tags do not move. `make check-engine-params` fails if the manifest is stale, and
`tests/test_engine_skills.py` asserts it covers every engine x variant.

Probe exit codes: 0 a flag answered, 1 the file is missing, 2 the file is there
but no flag answered. A backend whose CLI initialises its device at startup is
marked `binary_probe: device` (vllm cuda/rocm, mlx cuda, tensorrt-llm cuda,
exllamav3 rocm): it must still CONTAIN the file, and its version is proven by
`entrypoint.sh detect` (CI #106). The engine-image job still runs
`make test-engine-stage` before `make push-engine`, and `make test-published-engine`
re-runs the same probe against every image pulled back from GHCR.
