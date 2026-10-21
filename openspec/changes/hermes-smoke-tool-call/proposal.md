# `make hermes-smoke` proves the tool calling every bot leg depends on

## Why

`_hermes-smoke` (Makefile) is one line of prompt:

```
hermes -z "Reply with exactly: ok" $(nous-alias) --reasoning low --yolo
```

`issue-bot.yml` runs `make hermes-smoke` before it spends a run, and the smoke passes as long as the
endpoint returns the string `ok`. Every leg it protects is a **tool-using** agent: `implement-issue`
must run `make` gates through its terminal tool and edit files with its patch/write tools, the fix loop
hands the agent a failing check and expects it to run commands, the refiner must write `refine.md`. A
model whose tool calling is broken, disabled, or unsupported on the current snapshot still answers
`ok` — so the smoke stays green and the first real failure costs a 120-180 minute job
(`issue-bot.yml` `timeout-minutes: 120`, `fix-bot.yml` 180) before anyone sees it, which is exactly the
failure mode the smoke was added to prevent (issue #407).

Measured on 2026-10-20: `deepseek/deepseek-v4.1-flash-1017` does return `tool_calls` for a
`get_weather` function. The smoke cannot tell you that, and it could not tell you if it changed.

The smoke also cannot be strengthened by asking for a *word*: a model that answers "ok" is
indistinguishable from one that ran something and echoed it. The proof has to be a fact the model
cannot produce without a tool — so it must depend on a value the prompt does not contain.

## What Changes

- **`scripts/hermes_smoke.py` (new)** — the proof, declared once:
  - it writes a random nonce to a file under a temp dir; the prompt names the file but never the value;
  - the agent is told to run one exact command with its terminal tool —
    `printf 'smoke-ok:%s\n' "$(cat <file>)"` — and to reply with only that output;
  - after the run it reads the session transcript from `$HERMES_HOME/state.db` (`sessions` +
    `messages`, the same store `hermes sessions list` reads) and passes only when **all** hold:
    the run created exactly one new session, that session's transcript carries a `role='tool'` row
    whose `tool_name` is `terminal` and whose result contains `smoke-ok:<nonce>`, and the agent's final
    answer carries `smoke-ok:<nonce>` too.
  - every other outcome is a loud, named failure: no new session / no transcript, no tool call at all,
    a tool call to something other than `terminal`, a terminal call that did not produce the nonce, or
    an answer that does not carry it.
- **`make _hermes-smoke`** runs `python3 scripts/hermes_smoke.py run --alias nous-deepseek
  --reasoning low` inside the agent image: one code path, the same one `make hermes-smoke` drives from
  the host. A new `nous-model` Makefile variable carries the alias name so the script and the other
  legs read it from one place.
- **`tests/test_hermes_smoke.py` (new)** — locks the prompt (it names the terminal tool and the exact
  command, and it does **not** contain the nonce) and the assertion (a text-only transcript fails, a
  `terminal` result carrying the nonce passes, a `write_file` result carrying it fails, a session with
  `tool_call_count > 0` but no terminal result fails, a missing transcript fails rather than passes),
  plus the wiring: `_hermes-smoke` invokes the script, `issue-bot.yml` still runs `make hermes-smoke`,
  and the old `Reply with exactly: ok` prompt appears nowhere in the repository.
- **`README.md` + `agent-wiki/`** — the smoke's contract and how to read its failure.

## Impact

- Affected: `Makefile` (`_hermes-smoke`, `nous-model`), `scripts/hermes_smoke.py` (new),
  `tests/test_hermes_smoke.py` (new), `README.md`, `agent-wiki/`.
- No new dependency: `sqlite3`, `subprocess`, `secrets` and `tempfile` are stdlib.
- Cost: one extra terminal tool round-trip per smoke (a few hundred tokens).
- Not affected: `issue-bot.yml` keeps calling `make hermes-smoke`; the gate stays in the same place in
  the job, before the 120-minute step.
