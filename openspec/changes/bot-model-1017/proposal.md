# The bots run DeepSeek V4.1 Flash 1017, and the pin cannot drift again

## Why

Every bot pins `deepseek/deepseek-v4.1-flash`, which the Nous endpoint serves as a **different,
older** model than the one the owner runs. Measured 2026-10-20 against
`https://inference-api.nousresearch.com/v1/models`:

```
deepseek/deepseek-v4.1-flash         canonical_slug deepseek/deepseek-v4.1-flash-20260910  (Impala)
deepseek/deepseek-v4.1-flash-1017    canonical_slug deepseek/deepseek-v4.1-flash-20261017  (DeepSeek)
```

Both answer `200`, so nothing inside a bot job can tell them apart: the issue-bot, fix-bot,
issue-refiner, rebase-bot and `agent-fetch` all ran the September snapshot while the host alias
(`~/.hermes/config.yaml`, `model.aliases.nous-deepseek`) already ran `-1017`. The only test on the pin
is a substring assert (`"deepseek/deepseek-v4.1-flash" in script`), which a *newer* id always
satisfies — so the drift was invisible by construction (issue #405).

The image's alias is also written with no `max_tokens` and no `context_window`, while the host pins
`max_tokens: 16000` and `context_window: 1048576` (the model's published `context_length`). With
neither set, Hermes derives the bot's budget from the models.dev catalogue, which does not carry this
snapshot id — a 120–180 minute bot job is budgeted from a default instead of the model's real window.

## What Changes

- **`scripts/agent_model_pin.py` (new)** — the pin, declared once: `MODEL_ID`, `MAX_TOKENS`,
  `CONTEXT_WINDOW`. `check` reads the Dockerfile's `ARG` defaults and the install script's defaults and
  fails, naming the file and the value, when either disagrees or names a different DeepSeek Flash
  snapshot. `report` prints what each place says. No network, no key.
- **`make check-agent-model` / `make model-pin-report`** — the gate and its report, `.PHONY`, run by
  `ci-unit` (so a drift reds the pipeline that builds the image).
- **`containers/agent/Dockerfile`** — `ARG HERMES_MODEL_ID` moves to
  `deepseek/deepseek-v4.1-flash-1017`, and the build asserts the alias landed with **that** id, the
  `max_tokens` and the `context_window` — a half-written alias fails the build, not a bot run.
- **`scripts/install_hermes_ci.sh`** — same pin, and it writes `model.aliases.<alias>.max_tokens` /
  `.context_window` as well; its loud post-write check covers all three keys.
- **`tests/test_agent_model_pin.py` (new)** — the checker detects drift in the Dockerfile, in the
  install script, and on a snapshot id of another release; the tree as committed is green; the gate is
  reached by `ci-unit`; the values match the model's published window.
- **`tests/test_issue_implementer.py`** — the alias test asserts the exact id (and that the unpinned
  `deepseek/deepseek-v4.1-flash` never appears), not the prefix that let the drift ship.

## Impact

- Affected specs: `bot-agent-model` (new capability).
- Affected code: `scripts/agent_model_pin.py` (new), `containers/agent/Dockerfile`,
  `scripts/install_hermes_ci.sh`, `Makefile`, `tests/test_agent_model_pin.py` (new),
  `tests/test_issue_implementer.py`, `README.md`, `agent-wiki/`.
- The agent image's hash tag moves (`install_hermes_ci.sh` and the Dockerfile are its inputs), so the
  first run pulls or builds a new image. Nothing else about a bot job changes: same alias name
  (`nous-deepseek`), same legs, same redaction.
- Cost: none per run. `check-agent-model` is stdlib only and makes no model call.

## Not covered (each its own issue)

- #406 — the agent image's hash covers the Dockerfile and scripts, but not the Hermes version
  `install.sh` fetches, so two builds of one tag can carry different CLIs.
- #407 — `make hermes-smoke` proves text generation, not the tool calling every bot leg depends on.
- #408 — nothing checks that the pinned snapshot is still the current one, which is how this drift went
  unnoticed for a release.
