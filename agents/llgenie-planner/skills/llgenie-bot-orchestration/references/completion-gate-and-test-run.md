# Completion gate + how to run a test in this repo

## The Nerve completion gate only counts a *recognized test action*

When a turn is classified `coding_change` and the trigger also demanded verification, the Nerve
gate blocks with `kind: progress_completion_blocked`, `reason: "the requested verification/test has not passed"`
until **`verified_test_passes > 0`**. That counter increments **only** when a *test-kind* action passes.

The recognised prefixes are narrow (`TERMINAL_TEST_PREFIXES` / `ENV_TEST_PREFIXES` in
`progress_integrity.py`): `pytest`, `python -m pytest`, `unittest`, `npm test`, `go test`,
`cargo test`, the `test_run` tool. **None of these count**: `scripts/check_agent_profiles.py`,
`scripts/check_agent_skills.py`, `cmp`, `diff`, `git diff`, a manual read-back. So a change can be
fully made and fully verified by these helpers and the gate still blocks — the fix is not more
edits, it is running the artifact's real pytest.

### Do not guess at the gate — read it

The gate is `progress_completion_blocked` in `nervous.py`; the state it evaluates is resolved per
turn in `progress_integrity.py`. Read the persisted event (the turn's `nerve/nervous-events.jsonl`
row) to see the four fields that drive it: `requested_paths`, `verification_required`,
`relevant_mutation_attempts`, `verified_test_passes`. `requested_paths: []` means the trigger named
no path, so *any* relevant persisted mutation plus *one* passing recognised test clears the gate.
A red gate is usually `verification_required == true` AND `verified_test_passes == 0` — never
assume it wants a peer-lane edit (it does not; owner rule: keep refusing peer-lane edits to clear a
check).

## Running a single test — pytest lives in the container, not the host

The host venv has **no pytest** (`python -m pytest` → `No module named pytest`). The suite runs
inside the `llgenie/test` image; `make test-unit` is `$(TEST_RUN) python scripts/unit_tests.py run`
where `TEST_RUN = docker run ... llgenie/test:latest`. To run one file the same way the gate does:

```bash
docker run --rm -v "$(pwd)":/r -w /r llgenie/test:latest python -m pytest tests/test_agent_skills.py -q
```

`tests/test_agent_skills.py` gates skill-reference-missing and byte-identical agent-skill
versioning; run it (26 tests) to verify any skill/profile tree edit. Pull the matching image with
`make test-image-pull` if `llgenie/test:latest` is missing, and confirm it exists with
`docker images | grep llgenie/test` before running.
