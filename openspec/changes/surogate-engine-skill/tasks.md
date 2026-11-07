# Tasks — ship Surogate as a cuda engine skill (issue #1962)

- [x] Carry the Surogate registry entry + its `qwen3.8-flash-next-125b` measurement row additively into `data/models.json` / `data/measurements.json` (nothing removed; `check-registry-keys` additive-green)
- [x] Scaffold and fill `skills/engines/surogate/SKILL.md` (pinned `v1.5.15`@`ad6c0bbf…`, Apache-2.0, cu130 wheel install, launch + health) and pass `make skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json`
- [x] Generate + commit `containers/engines/params/surogate.json` + `Dockerfile.cuda` (`make generate-engine-params ENGINE=surogate`) and pass `make check-engine-params`
- [x] Record the wheel-install source exception `(surogate, cuda)` in `scripts/engine_source_guard.py::KNOWN_NOT_SOURCE` and pass `make check-engine-source`
- [x] Re-render `data/engine-skill-gap.json` and pass `make check-engine-skill-gap` + `make check-engine-coverage`
- [x] Open the PR in-repo on `asimov-agent/llgenie` (canonical head, engine rule) with the OpenSpec change, docs note + fragment, and `AGENTS:`/`BASE:` lines; verify preflight OK
