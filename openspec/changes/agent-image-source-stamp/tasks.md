# agent-image-source-stamp — Tasks

Checklist of record (issue #2968). The agent build stamps `llgenie.agent.source=<tree tag>`;
`source-check` compares the resolved image's label against the tree's tag; the agent-leg preflight
runs it before `hermes-smoke`. No publish-cadence change (#2935 stays a human dispatch).

## Stamp the source hash

- [x] 1.1 `scripts/ci_images.py`: stamp `--label llgenie.agent.source=<tag>` in `_buildx_push`
      and `_build_local` for the agent image only
- [x] 1.2 `scripts/ci_images.py`: `source-check` verb (CLI choice + function) with the three
      verdicts (match / missing label / differing label), the remedy naming #2935, rc 1 on stale

## Check seam + wiring

- [x] 2.1 `mk/agents.mk`: `agent-image-source-check` target wrapping the verb
- [x] 2.2 `.github/actions/agent-leg/action.yml`: preflight step before the routing-smoke step,
      same `routing_smoke` guard

## Tests (hermetic, no network)

- [x] 3.1 stamp pinned on both build paths (publish + local fallback) in `tests/test_ci_images.py`
- [x] 3.2 `source-check` verdicts pinned: match rc 0, missing label rc 1 names #2935,
      differing label rc 1 names both hashes
- [x] 3.3 composite-action ordering pinned: source-check appears before `make hermes-smoke`
      under the preflight+routing_smoke guard

## Verification provable at head (tick only with rc 0)

- [x] 4.1 `pytest tests/test_ci_images.py -q` rc=0 at head
- [x] 4.2 full unit battery `make test-unit` rc=0 at head
- [x] 4.3 `make openspec-validate NAME=agent-image-source-stamp` rc=0 and
      `make lane-preflight` rc=0 at head
