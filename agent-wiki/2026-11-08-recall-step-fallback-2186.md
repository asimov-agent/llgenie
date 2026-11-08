# The orchestrator's recall step gets a real fallback (issue #2186)

Step 2 of the orchestrator procedure — "recall the failure class before you interpret anything" —
named `hindsight_recall(query=…)`, an agent tool the cron tick's toolset does not carry. A step
that names an unavailable tool does not fail loudly; it degrades into whatever substitute the
running model reaches for, and that substitute defaulted the hindsight CLI to port `8888` while
nothing listened there. Measured 2026-11-08 at 07:52Z the pass reported *"the API is down —
no prior match, and no retain possible this pass"*, while the daemon was `active`, listening on
**9177**, and `/health` answered `{"status":"healthy","database":"connected"}`. A healthy
subsystem was reported as down and recall was skipped on every pass.

Two independent defects compounded:

1. **A step named a mechanism the runner lacks.** Step 2's agent tool is absent from a cron turn's
   toolset (the same pass notes `message_agent` is absent), so the step degraded without a loud
   failure.
2. **The substitute carried a default nobody chose.** `HINDSIGHT_API_PORT=9177` is the live value
   in `$HOME/.hindsight/profiles/hermes.env`; `8888` appears there only commented out
   (`# HINDSIGHT_CP_DATAPLANE_API_URL=http://localhost:8888`). The CLI defaulted to 8888 and the
   pass probed a dead port.

## The fix, versioned

`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/orchestrator-tick-contract.md`
— the versioned orchestrator procedure — now carries, byte-identical to the corrected live profile:

- **Step 2 (RECALL)** provides **both** paths: the agent tool when the turn has it, else a pinned
  shell fallback
  `curl -s -m 8 -X POST http://127.0.0.1:9177/v1/default/banks/llgenie-planner/memories/recall
  -d '{"query":"<failure class>","limit":3}'`
  with the lane's **own** bank id (`llgenie-planner`, never a placeholder that 404s) and the
  endpoint pinned at **9177** — never left to a CLI default.
- A **health probe** (`curl -s http://127.0.0.1:9177/health`) is part of the step, so "daemon
  down" and "wrong command" are distinguishable.
- The false negative is forbidden in the step text: `report "no prior match" only after the
  fallback has actually answered`; NEVER report the instrument as absent without running the
  fallback.
- The general rule applies to **every** tool-dependent step: a step that genuinely cannot be done
  from a shell (`message_agent` is an agent tool, not a binary) names its durable substitute — the
  **board task plus an on-issue comment** — instead of leaving a dead tool call in the procedure.

The endpoint is discovered, not guessed: `curl -s http://127.0.0.1:9177/openapi.json` lists
`/v1/default/banks/{bank_id}/memories/recall`.

## The tests prove it against the LIVE daemon

`tests/test_procedure_recall_step.py` drives the real fallback the way a tick turn would:

- **positive** — recall on 9177 returns a non-empty `results` array for a known class
  (`check-pr-acceptance write-back`);
- **negative control** — with the port set to 8888 the fallback FAILS **while** `9177/health`
  SUCCEEDS, proving the check distinguishes a wrong command from a dead daemon.

The live proof (quoted, this host): `curl … /memories/recall` with the class query returned
`results: 53`, the top hit the `check-pr-acceptance` → `llgenie-pr-reviever` write-back class; and
the 8888 probe failed (`000` / connection refused) while 9177 answered healthy. Both tests pass
via `make test-recall-step`. They need the daemon on 127.0.0.1:9177, so the file is a dated
decision in `tests/fixtures/unit-suite.json` (kept OUT of the hermetic gate, whose runners have no
daemon; this repo forbids skips, #1110).

## Acceptance coverage

- AC1 — step 2 in the versioned procedure provides both agent-tool path and the pinned 9177 shell
  fallback.
- AC2 — the step states 9177, that 8888 appears only commented-out in `hermes.env`, and that the
  tick must not conclude the instrument absent without running the fallback.
- AC3 — the health probe is part of the step; AC4 — the bank id is the lane's own
  (`llgenie-planner`).
- AC5 — every other agent-tool step (`message_agent`) states its durable channel: board task plus
  on-issue comment.
- AC6/AC7 — the two tests (positive live + 8888 wrong-port negative control) pass locally.
- AC8 — the failure mode is recorded: a step naming an unavailable tool must not be reported as
  "instrument absent".

No daemon, unit, or port changed — this is a caller-side fix only.
