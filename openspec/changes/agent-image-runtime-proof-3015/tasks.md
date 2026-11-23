# agent-image-runtime-proof — Tasks

Checklist of record (issue #3015). The publish lane must prove the pushed image is this tree and
that every declared bot lane resolves in it before the paid prompt smoke.

## Deterministic proofs

- [x] 1.1 `.github/workflows/publish-agent-image.yml`: add `make agent-image-pull` then
      `make agent-image-source-check` after `make publish-agent-image`, before
      `make agent-image-profiles-check` (buildx --push leaves no local image)
- [x] 1.2 `tests/fixtures/host-only-wiring.json`: delete the now-STALE `agent-image-pull` target
      exception (CI reaches it from the new step); the wiring guard proves it instead

## Check seam + wiring

- [x] 2.1 `scripts/agent_image_profiles_check.py`: add `--resolve` seam that runs
      `hermes -p <lane> skills list --source local` per manifest lane, with `RESOLVE OK/FAIL`
      verdicts and a loud missing-CLI failure
- [x] 2.2 `mk/agents.mk::_agent-image-profiles-check`: pass `--resolve` to the seam

## Tests (hermetic)

- [x] 3.1 tests pin the resolver: all lanes OK rc 0, one non-zero exit names the lane and rc 1,
      missing hermes CLI fails loudly, no model call is made
- [x] 3.2 tests pin workflow ordering (publish → pull → source-check → profiles → smoke) and the
      in-image `--resolve` flag
- [x] 3.3 sabotage proof: new tests fail against the pre-fix sources and pass against the fix

## Verification

- [x] 4.1 `pytest tests/test_agent_image_profiles_check.py -q` rc=0 (12 passed)
- [x] 4.2 `make test-unit`: final full battery 23 failed / 4352 passed; every failing test reproduces
      on detached `origin/main` `fde44d14` (baseline also had one extra flaky red) — zero new
      failures; the 3 wiring failures this change introduced were fixed (3/3 targeted tests pass)
- [x] 4.3 `make openspec-validate NAME=agent-image-runtime-proof-3015` rc=0
- [x] 4.4 `make lane-preflight` rc=0 at head after commit
- [x] 4.5 run 45134224656 outcome recorded on issue #3015
