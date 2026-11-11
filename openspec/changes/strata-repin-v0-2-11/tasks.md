# Tasks — strata-repin-v0-2-11 (issue tracked upstream: Niko1221/Strata#5473)

- [x] 1. OpenSpec change: `proposal.md`, `specs/strata-repin/spec.md`, this checklist
- [x] 2. `skills/engines/strata/SKILL.md`: re-pin ref/version/pinned to v0.2.11@4a4160162e4a402e082f41aa0a88e6eed629d913 (via `python3 scripts/engine_bump.py pin strata v0.2.11 <sha>`)
- [x] 3. `make sync-strata-models`: re-sync `data/strata_models.json` to setup.py at the new pin
- [x] 4. `make generate-engine-params ENGINE=strata`: regenerate `containers/engines/params/strata.json` and `Dockerfile.cuda`/`Dockerfile.rocm`
- [x] 5. `make check-engine-params` exit 0 (committed output == what the skill generates)
- [x] 6. `make check-strata-models` exit 0
- [x] 7. `make lint` exit 0 (trailing newlines on every touched file)
- [x] 8. `make openspec-validate NAME=strata-repin-v0-2-11` valid
- [x] 9. `agent-wiki/` note + `docs/changes.d/` fragment + `CHANGES.md` index row naming the issue and the PR
- [x] 10. `pr-body.md` written with Issue:/Fix:/Benefit:/Technical:/AGENTS: sections

The engine-build green runs at the new pin and `check-engine-pins-published` manifest resolution are the CI-side acceptance (the build lane runs after the change lands); the hermetic generators above are the parts verifiable from the implement tree.
