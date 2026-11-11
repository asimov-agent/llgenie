# Proving a headless agent actually calls tools

A smoke that asserts a SENTENCE ("reply with `ok`") is satisfied by every model, including one whose
tool calling is broken, disabled, or unsupported on the current snapshot. The bot then goes green and
fails 120-180 minutes into the real job. To prove the capability instead, the assertion must depend on
a fact the model cannot produce without a tool.

## The marker-file trick (make the answer unguessable)

1. Generate a random value per run and write it to a file. The prompt names the **file**, never the
   value.
2. Tell the agent to run one exact command with its terminal tool that prints that file, and to
   reply with only the output:
   `printf 'smoke-ok:%s\n' "$(cat <token_file>)"`.
3. Pass only when **both** hold: the run's transcript carries a tool result for the required tool
   containing the marker, AND the final answer carries it.

A text-only model cannot produce the value. Do not put the value in the prompt — a model that only
paraphrases would then pass by echoing it, and the smoke becomes a wording test again.

## Where the transcript lives (Hermes CLI)

The store is `$HERMES_HOME/state.db` (default `~/.hermes/state.db`), sqlite, the same one
`hermes sessions list` reads. Two tables matter:

- `sessions (id, started_at, tool_call_count, message_count, model, cwd, …)`
- `messages (id, session_id, role, content, tool_call_id, tool_calls, tool_name, timestamp, …)`

Procedure:

```python
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)   # read-only: never mutate the store
before = {row[0] for row in conn.execute("SELECT id FROM sessions")}
# … run the agent …
new = ids_after - before                                 # the session this run created
rows = conn.execute("SELECT role, tool_name, content FROM messages WHERE session_id=? ORDER BY id",
                    (session,)).fetchall()
```

- `role='tool'` rows carry `tool_name` and the tool's result in `content`, a JSON string such as
  `{"output": "smoke-ok:…\\n", "exit_code": 0, "error": null}` — substring-search the marker there.
- The last non-empty `role='assistant'` row is the answer.
- Rows finalize just after the process exits: poll for the new session id for ~30-60s instead of
  reading once.
- A missing `sessions` table raises `sqlite3.DatabaseError` on the first query — catch it and report a
  named failure instead of crashing or passing.

## What is NOT evidence

- **`tool_call_count` / `message_count`.** Summary counters. A session can claim tool calls with no
  tool row in the transcript; only the rows are evidence.
- **The process exit code.** `0` means the conversation ended, not that the work happened.
- **The agent's own report.** "committed at `<sha>`, nothing pushed" is a claim about a container's
  writable layer that may already be gone.
- **The answer text alone.** That is exactly what a tool-less model produces.

## Keep the failing side loud and named

Every non-passing outcome gets its own message: no new session, no readable/absent store, no tool call
at all, a tool other than the required one (list the tool names seen), a tool result without the
marker, an answer without the marker. A missing transcript is a failure, never a pass — absence of
evidence must never read as green.

## Testing the proof itself

- Build the sqlite fixtures for real (both tables, the real column names) — this is product logic, so
  no mock.
- Required cases: text-only transcript fails; required-tool result carrying the marker passes; another
  tool carrying it fails; `tool_call_count` > 0 without the tool row fails; nonexistent store and
  non-sqlite file both fail naming the transcript; the prompt lock (names the command and the token
  path, contains no occurrence of the marker value).
- Pin the wiring too: the recipe runs the script, the bot workflow's step calls the target, and the old
  sentence prompt appears nowhere a prompt can live.
- Prove the negative for real, not only in fixtures: run the old sentence prompt through the same code
  path and watch it report "answered without calling a tool at all".

## Reuse

The same shape proves write access: require a `write_file`/`patch` tool result whose content carries
the marker, when the bot's job is editing files rather than running commands.
