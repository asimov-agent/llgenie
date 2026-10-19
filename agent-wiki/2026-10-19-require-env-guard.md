# 2026-10-19 — every bot leg refuses to start on a missing key (#363)

Implements [#363](https://github.com/asimov-agent/llgenie/issues/363) (PR [#370](https://github.com/asimov-agent/llgenie/pull/370)),
a child of the bot-fleet parent
[#357](https://github.com/asimov-agent/llgenie/issues/357). OpenSpec change:
`openspec/changes/require-env-guard`.

## What was wrong (measured)

One leg of eight guarded its key — `make hermes-smoke`, with an ad-hoc bash `test -n`. The rest
forwarded `-e NOUS_API_KEY` / `-e TYPESAFE_API_KEY` and failed only inside the container, after the
agent image had been pulled and started, on a job with a 120-180 minute timeout.

## What changed

- `scripts/require_env.py` (name-only, exit 2 on missing OR empty, bad names refused, no value ever
  printed) and `make require-env KEYS="…"` as the public entry point.
- The guard is the FIRST recipe line of every leg that starts the agent image — including
  `agent-shell-keys-check` and `fix-loop-image` — ahead of `scripts/ci_images.py ensure agent`.
- One code path: the bash guard inside `hermes-smoke` and `_hermes-smoke` is gone, replaced by the
  script, so the two cannot drift.
- `tests/test_require_env.py` derives the roster from the Makefile and asserts both the behaviour and
  the ordering (guard before the pull), so a leg added without one reds the suite (#349/#301 are the
  same defect this repo has filed twice).
- After #369 (the masked web reach) merged, the merged tree had two unguarded legs — `agent-fetch`
  and `search-smoke` both start the agent image. Both now run `scripts/require_env.py` before
  `scripts/ci_images.py ensure agent`; the file-derived roster is what caught it, which is the point.

## Verified

`pytest tests/test_require_env.py tests/test_agent_shell_keys.py -q` → 14 passed;
`make -n issue-refiner` renders the guard before `docker run`; an unset and an empty key both exit 2
with the variable's name and no value.

## Follow-ups

- #364 — the issue-bot implementer's job sets no `GH_TOKEN`, so that leg forwards an empty one (the
  guard now names it as missing rather than letting it look wired, which is the intended behaviour).
