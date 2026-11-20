# Derive the leg→job key roster from the tree (issue #908)

## Why

The #364 rule "the job that calls a leg sets the keys that leg forwards" is driven by two
hand-kept rosters in `tests/test_agent_shell_keys.py`: `BOT_JOBS` (four workflows + key tuples)
and the `entries` tuple (four `(workflow, trigger, leg)` triples). Nothing derives either list
from the tree, so the rule covers exactly the four bots somebody remembered. Measured on
`main@4f3fc1ef25a0`: 16 agent legs in the Makefile, 23 leg calls across 9 workflow files —
`issue-dedup`, `registry-sync-review`, `architecture-bot`, `engine-bump`, `search-smoke`,
`publish-agent-image` and the wrapper-mediated `rebase-bot` call sit outside both rosters.
This is the third time this repo pays for a hand-kept workflow roster (#349, #301).

## What Changes

- The scope walk is DERIVED: for every workflow file, every job, every step whose text runs
  `make <target>`, when `<target>` is an agent leg (`$(AGENT_IMAGE)` in its recipe) or a wrapper
  that transitively runs one (`make <leg>` / `$(MAKE) <leg>` in the recipe), the required key set
  is what the leg's recipe forwards with `-e` (minus `NON_CREDENTIAL_ENV` knobs and the forced
  twins), asserted via the existing `_step_sets_key` scope rule (job `env:` or that step's own
  `env:`, never a sibling step's).
- The four hand-kept `entries` are REMOVED; every case they covered is asserted by the derived
  walk. A walk that finds zero leg calls fails loudly (no vacuous pass).
- `BOT_JOBS` keeps ONLY the `agent-shell-keys-check` assertion (which key set each bot job
  proves through the composite), with a comment saying why it stays hand-named.
- The derived walk finds a real gap on the base: `publish-agent-image.yml` runs
  `make agent-image-profiles-check` and `make hermes-smoke` — both forward `-e TYPESAFE_API_KEY`
  — but neither step sets it. This change adds `TYPESAFE_API_KEY: secrets.TYPESAFE_API_KEY` to
  those two steps so the battery is green with the derived rule active (the same shape #364 and
  #802 fixed; leaving it red is not an option).
- A planted-defect test proves the walk catches the #364 shape end-to-end: red before, green after.

## Impact

- Affected specs: `agent-shell-keys` (new requirement: derived coverage).
- Affected code: `tests/test_agent_shell_keys.py`, `.github/workflows/publish-agent-image.yml`.
- No credential is created; the secret already exists and is used by `issue-bot.yml`.
