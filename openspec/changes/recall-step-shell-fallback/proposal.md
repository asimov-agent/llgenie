# recall-step-shell-fallback — proposal

Issue: [#2186](https://github.com/asimov-agent/llgenie/issues/2186)

## Why

Step 2 of the orchestrator procedure — "recall the failure class before you interpret anything" —
named `hindsight_recall(query=…)`, an agent tool the cron tick's toolset does not carry. A step
that names an unavailable tool degrades into a substitute with defaults nobody chose. Measured
2026-11-08 at 07:52Z: the tick probed the hindsight CLI's default port **8888**, nothing listened
there, and the run reported `✗ Cannot connect to Hindsight API — http://localhost:8888` as "the
API is down" while the daemon was `active` on **9177** and `/health` answered
`{"status":"healthy"}`. A healthy subsystem was reported down and recall was skipped on every pass.

## What Changes

- **The versioned procedure** (`agents/llgenie-planner/skills/llgenie-bot-orchestration/
  references/orchestrator-tick-contract.md`, live→tree fold byte-identical to the corrected live
  profile) — STEP 2 (RECALL) now carries **both** paths: the agent tool when the turn has it, and a
  shell fallback `curl -s -m 8 -X POST
  http://127.0.0.1:9177/v1/default/banks/llgenie-planner/memories/recall
  -H 'Content-Type: application/json' -d '{"query":"<failure class>","limit":3}'` with the lane's
  **own** bank id (never a placeholder that 404s) and the endpoint pinned at **9177** — never left
  to a CLI default. A **health probe** (`curl -s http://127.0.0.1:9177/health`) is part of the
  step, so "daemon down" and "wrong command" are distinguishable. The false negative is forbidden:
  report `no prior match` only after the fallback has actually answered. The endpoint is
  discovered (`curl … /openapi.json` lists `/v1/default/banks/{bank_id}/memories/recall`), not
  guessed.
- **Every tool-dependent step got a fallback or a durable channel.** `message_agent` steps (6 HOW
  TO DELEGATE, 11 DOCS + ARCHITECT) — an agent tool, not a binary — state explicitly that the
  durable channel is the **board task plus an on-issue comment**, so a runner without the agent
  toolset can still execute every step.
- **`tests/test_procedure_recall_step.py`** drives the REAL fallback against the live daemon: a
  positive (recall on 9177 returns a non-empty `results` array for `check-pr-acceptance
  write-back`) and a negative control (with the port at 8888 the fallback fails while 9177/health
  succeeds). The file is a dated decision in `tests/fixtures/unit-suite.json` (kept OUT of the
  hermetic gate, whose runners have no daemon; the repo forbids skips, #1110), and runs on the tick
  host via the new `make test-recall-step` target (documented in `docs/ARCHITECTURE.md`).
- **docs trio** — `agent-wiki/2026-11-08-recall-step-fallback-2186.md`,
  `docs/changes.d/2026-11-08-recall-step-fallback-2186.md`, and the `CHANGES.md` row rendered by
  `make changes-index`.
