# Wiring a new script + make target, forbidden paths, and the full-suite budget

Read when you add a new `scripts/*.py` and/or a new make target, or place versioned
behaviour under `agents/<profile>/`.

## `check-wiring` — THREE surfaces, one of them BIDIRECTIONAL

`make check-wiring` prints `[check-wiring] OK … (NNN tests, MMM scripts): X run in CI, Y host-only`.

1. **`.PHONY:` declaration for the new make target.** A target with no `.PHONY` entry reds
   `check-wiring` naming `Makefile:<n>`. Add the name to the existing `.PHONY:` block — do not
   only place it adjacent to the target recipe.
2. **CI-reachable OR host-only fixture entry.** The script must be either CI-reachable (a
   `tests/` file imports/drives it) OR recorded in `tests/fixtures/host-only-wiring.json`.
3. **The host-only fixture is a ROUND-TRIP.** The moment you add a test that makes the script
   CI-reachable, its host-only entry becomes STALE and the gate reds until you DELETE it — add
   the entry only while the script stays host-only, and remove it in the SAME commit that adds
   its test.

## `scripts/package-layers.json` — every new script needs a group

`test_package_layers` reds `modules with no group: ['<name>']` for any `scripts/*.py` absent
from the file. Add it under the matching group (structural gates live beside
`check_agent_profiles`). Edit the JSON with `json` (load → mutate → dump with `ensure_ascii=True`,
`indent=1` matching the file), never a blind text rewrite — the file uses `\u2014` escapes and a
naive dump churns every unrelated line into the diff.

## `agents/<profile>/cron/` is FORBIDDEN

`test_agent_profiles` treats ANY file under `agents/<profile>/cron/` as committed chat logs /
credentials and reds `forbidden path`. A versioned prompt/script cannot live there — use
`agents/<profile>/prompts/<name>.md` (or `scripts/`). The gate's `--live` DEFAULT stays
`.hermes/profiles/<profile>/cron/jobs.json` — that is the real LIVE path, not a tree path; do
not "fix" it when relocating the versioned copy.

Relocation checklist after `git mv` (and `rmdir` the emptied `cron/`): gate `VERSIONED`
constant, Makefile help line, agent-wiki note + `docs/changes.d/` fragment + `CHANGES.md` row,
the test's `VERSIONED` constant, the openspec `spec.md` scenario. Then
`git grep -n 'cron/<name>'` must return only the live `--live` default.

## Full-suite budget and exclusion check

`make test-unit` = `python scripts/unit_tests.py run` routinely exceeds a 300 s `execute_code`
cell budget — run it as a tracked background process with `notify` and read the exit / `UNIT_RC`
on completion; do not poll in a loop or re-derive a number from a killed cell. Before trusting
"my test passed", confirm it is not silently deselected: check `tests/fixtures/unit-suite.json`
`excluded` for your test + script path (absent = good).
