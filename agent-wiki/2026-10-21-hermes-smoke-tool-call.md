# `make hermes-smoke` proves the tool calling every bot leg depends on

- Issue: #407 (`ci(bots): hermes-smoke proves text generation, not the tool calling every bot depends on`)
- OpenSpec change: `hermes-smoke-tool-call`
- Branch: `feat/hermes-smoke-tool-call`
- PR: [#439](https://github.com/asimov-agent/llgenie/pull/439) — `asimov-agent/llgenie:main` from
  `andyholst:feat/hermes-smoke-tool-call`

## What was wrong

`_hermes-smoke` was `hermes -z "Reply with exactly: ok" … --yolo` and passed on any endpoint that
returns the string `ok`. Every leg the smoke guards is a tool-using agent — `implement-issue` runs
`make` gates through its terminal tool, the fix loop hands the agent a failing check, the refiner writes
`refine.md`. A model whose `tools` were dropped, disabled or broken by a snapshot change answered `ok`
and went green, then failed a 120-180 minute job.

## What changed

- `scripts/hermes_smoke.py` (new) — the proof, one code path: a per-run nonce is written to a token
  file (the prompt names the path, never the value); the agent is told to run
  `printf 'smoke-ok:%s\n' "$(cat <file>)"` with its terminal tool and answer with only that output; the
  verdict is read from the session the run created in `$HERMES_HOME/state.db` — a `role='tool'`,
  `tool_name='terminal'` result carrying `smoke-ok:<nonce>` **and** a final answer carrying it.
- `Makefile` — `nous-model` is the one place the alias name lives (`nous-alias := -m $(nous-model)`);
  `_hermes-smoke` runs `python3 scripts/hermes_smoke.py run --alias $(nous-model) --reasoning low`; the
  public `hermes-smoke` help line states the tool-call contract.
- `tests/test_hermes_smoke.py` (new) — locks the prompt (names the command and the token path, never the
  nonce), the four verdicts (text-only fails, `terminal` with the nonce passes, another tool does not
  count, a `tool_call_count` above zero is not evidence), the two missing-transcript failures, and the
  wiring (recipe runs the script, `issue-bot.yml` still runs `make hermes-smoke`, the old sentence
  assertion is gone from every file that can carry a prompt).
- `README.md` — the smoke's contract and how to read its failure.

## Verified

- **Live, against the real alias** (`nous-deepseek`, the host's `hermes`, same code path as the recipe):
  `python3 scripts/hermes_smoke.py run --alias nous-deepseek --reasoning low` →
  `[hermes-smoke] OK: session local-6067a5… called the terminal tool and its output
  (\`smoke-ok:db0cf8aa…\`) reached the answer`, exit 0.
- **Live negative, same code path:** a run of the old sentence prompt created a session with two rows
  (`user`, `assistant`) and the verdict reported *"the model answered without calling a tool at all"* —
  the exact failure the smoke exists to catch. So the assertion discriminates on a real transcript, not
  on a fixture.
- **Container:** the agent image (`d70aa12310b4`) runs the script (`prompt_for` + `sqlite3` import
  through `/repo/scripts`), so the recipe's interpreter and module set are proven; the full
  `make hermes-smoke` inside the image runs in the bot job, which supplies `NOUS_API_KEY`.
- `make test-unit` — `4911 passed, 3 deselected in 1187.27s` (exit 0). The two suite cases that pinned
the old alias literal and the `hermes -z` smoke line were updated to the new single source and the
script leg, not weakened.
- `make check-docs`, `make check-wiring`, `make check-workflows`, `make check-pr-hygiene`,
  `make lint`, `make openspec-validate NAME=hermes-smoke-tool-call` — green.

## Notes

- `tool_call_count` is a summary counter; the smoke deliberately does not trust it. Only the transcript
  is evidence.
- The nonce never enters the prompt, so a text-only model cannot pass by echoing — that is the property
  that makes the smoke a capability test rather than a wording test.
- Filed from this work, not fixed here (separate issues): #426 (the agent's worktree escapes the
  `/repo` mount), #427 (the triage scratch file is committed as the implementation), #428 (`rc=0` is
  treated as "implemented"), #429 (the bot's placeholder PR body), #430 (`BUMP_TOKEN` cannot post the
  claim comment). PR #424 was a stub built on those defects and was closed unmerged.
