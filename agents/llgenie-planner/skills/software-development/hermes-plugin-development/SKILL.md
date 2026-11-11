---
name: hermes-plugin-development
description: >-
  Build or test native Hermes Agent plugins.
---

# Hermes Plugin Development

Build native Hermes Agent plugins using the `plugin.yaml` + `register(ctx)` pattern.

## Plugin structure

```
my_plugin/
├── plugin.yaml          # Manifest: name, version, hooks, config
├── register.py          # Hook handlers + register(ctx) entrypoint
├── my_module.py         # Plugin logic
└── __init__.py
```

## Hook contracts

### pre_llm_call

- Receives: `task_context` (string), plus arbitrary kwargs
- Returns: `{"context": "..."}` to inject context, or `{}` for nothing
- **CANNOT**: skip LLM, change model, return tool results, or modify history
- Use sparingly — every injection adds tokens and latency

### pre_tool_call

- Receives: `tool_name`, `args` (dict), `task_id`, plus kwargs
- Returns: `{"action": "approve"|"block", "message": "..."}`
- **CANNOT**: execute the tool, return synthetic results, or modify args
- Fail-open on errors (return approve) — never block agent due to plugin issues

### post_tool_call

- Receives: `tool_name`, `args`, `result`, `task_id`, plus kwargs
- Returns: dict (passed back to caller, not automatically injected)
- **CANNOT**: modify conversation history or inject context
- Use for tracking, logging, and passing data to other hooks via module state

## Plugin registration

```python
def register(ctx):
    ctx.register_hook("pre_llm_call", pre_llm_call_handler)
    ctx.register_hook("pre_tool_call", pre_tool_call_handler)
    ctx.register_hook("post_tool_call", post_tool_call_handler)
```

Call `register(ctx)` once at module load. Use module-level singletons for state that persists across hook calls.

## Multi-profile deployment and verification

Install to all profiles so the plugin works everywhere, then verify runtime activation per profile.

```bash

# Root + profiles
for d in ~/.hermes ~/.hermes/profiles/*/; do
  mkdir -p "$d/plugins"
  cp -r my_plugin "$d/plugins/"
done
```

Enable + configure in each profile's `config.yaml` (not `entries.<id>.<key>` — settings one level up are silently ignored; use `plugins.entries.<id>.settings.<key>` or the top-level `plugins.enabled` + provider config fields).

### Activation verification (per-profile)

**Strip inherited Kanban/session env before every headless run** — `HERMES_KANBAN_TASK_ID`, `HERMES_CRON_SESSION`, `HERMES_GATEWAY_SESSION`, and similar session-identifying vars make the child load as a headless worker, skipping nervous/gate hooks and writing no ledger events:

```bash
env -u HERMES_KANBAN_TASK -u HERMES_KANBAN_TASK_ID -u HERMES_KANBAN_BOARD \
    -u HERMES_CRON_SESSION -u HERMES_GATEWAY_SESSION -u _HERMES_GATEWAY \
    -u HERMES_EXEC_ASK -u HERMES_SESSION_KEY \
    hermes -p <profile> -z "Use terminal to run: echo NERVE-PROBE. Reply OK." --yolo
```

Then inspect that profile's own plugin dir (not the root `~/.hermes/nerve`) for ledger writes:

```bash

# Real runtime evidence — live provider call + provenance
tail -2 ~/.hermes/profiles/<profile>/nerve/nervous-events.jsonl | jq .
tail -1 ~/.hermes/profiles/<profile>/nerve/receipts.jsonl | jq .
```

A receipt with `execution.live_provider_call: true` and `provenance.status: VERIFIED` proves the plugin loaded as a full controller session under that profile. See `references/hermes-plugin-patterns.md` for the full verification workflow and per-profile fan-out pattern.

### Context engine replacement (plugin as active compressor)

A plugin that subclasses `ContextEngine` can become the **sole compressor** for all sessions under that home via `context.engine: <name>` in config. When active, the built-in `ContextCompressor` is **never** called — the plugin's `should_compress()` and `compress()` own both the timing and the compaction strategy. Verify the active engine from the TUI/Desktop load line: `Loaded context engine: <name>` or, on failure, `Context engine '<name>' not found — falling back to built-in compressor`.

**The `name` contract.** Hermes looks up the engine by `context.engine` and matches it against `engine.name` (a property on the `ContextEngine` subclass). If they differ, you get the fallback warning and the built-in compressor silently takes over. Always confirm `name` matches the config value.

**Two modes — `shadow` vs `apply` — change who performs compaction, not whether.**

| Mode | Timing decision | Compaction performer | Effect on context |
|------|----------------|---------------------|-------------------|
| `shadow` (default) | Engine's threshold | Built-in `ContextCompressor` via `_fallback` | Messages cut/summarized as the built-in would do |
| `apply` | Engine's threshold | Engine's own `compress()` with semantic anchoring | Tool results preserved as anchors, text summarized per engine policy |

Shadow is **not** passive observation — it still compresses, it just delegates the cut to the built-in. Switching to `apply` matters most on tool-heavy sessions where semantic anchoring of tool results (keep if needed again / superseded / conflicting) beats generic summarization.

**Config-path pitfall: live TUI edits to `compression.*` may silently fail.** Hermes' live config sync calls `_coerce_threshold_tokens_cap()` on the active engine. If the engine doesn't implement this method, the log shows `Could not apply live compression config for <session>: '<Engine>' object has no attribute '_coerce_threshold_tokens_cap'`. The engine then runs on its own `context_engine_threshold_percent` default (commonly 0.72) instead of the configured `compression.threshold`. Changing `compression.threshold_tokens` or `compression.threshold` in TUI settings does nothing — you must restart for edits to take effect.

**Verification for context-engine plugins:**
1. `context.engine` in config matches the engine's `name` property — load line confirms.
2. Search `logs/agent.log` for `_coerce_threshold_tokens_cap` warnings — if present, your `compression.*` config is not being applied; the engine's schema defaults win.
3. To change the effective threshold, edit config and restart the session — do not rely on live TUI sync.
4. Confirm actual compaction runs via `agent.conversation_compression` log lines showing `fallback_used: false` when the engine is in `apply` mode.

### Headless vs PTY: which proves what

Headless `-z "prompt" --yolo` (~7 s each, fan with `xargs -P`) proves the plugin's tools and hooks registered under that profile — fast and sufficient for most plugins.

Session-aware plugins (Nervous/Reflex) require a **real PTY turn** to prove their engine actually fires. Headless runs skip nervous hooks and write no ledger events, so a headless pass proves the plugin loaded but NOT that it engaged. For these:

```bash

# Boot a clean PTY (strip Kanban/session env first)
tmux new-session -d -s probe -x 200 -y 50 \
  "env -u HERMES_KANBAN_TASK -u HERMES_KANBAN_TASK_ID -u HERMES_KANBAN_BOARD \
   -u HERMES_CRON_SESSION -u HERMES_GATEWAY_SESSION \
   hermes -p <profile>"
sleep 30
tmux send-keys -t probe 'Reply exactly: OK' Enter
sleep 45
tmux capture-pane -t probe -p | tail -12
```

Then inspect that profile's plugin dir for engine-fired records — for Nervous, `nervous-events.jsonl` `turn_admission` entries with real `request_id` + `latency_ms` (not `null`). PTY cost: ~30 s boot + one provider turn per profile.

## Testing policy

### Integration tests (real API)

- No mocks. Tests fail if API key is missing.
- Check for key at module level with `pytest.fail(...)` — never silently skip.
- Hermes CLI tests use `hermes chat -q "..."` and parse session output.

### Unit tests (pure logic)

- Test plugin loading, YAML validity, handler signatures
- Test error handling paths that don't need API calls
- Use `MagicMock()` for `ctx` object in register tests

### Test file preservation

**NEVER overwrite existing test files when adding new ones.**

1. Read the existing file first
2. APPEND new tests or create NEW files
3. Keep existing fixtures (e.g., `FULL_TOOL_CATALOG`)
4. Update assertions to match real API behavior — don't force API to match old assertions

### Honest benchmarking for middleware plugins

**Don't claim:**
- "Jev makes decisions" → Jev classifies, LLM decides
- "Reduces token usage" → Suggests compaction, LLM may or may not comply
- "Hard compaction" → We do soft compaction via context injection

**Do claim:**
- "Classifies result relevance"
- "Provides compaction suggestions"
- "Blocks hallucinated tool calls"
- "LLM respects injected context (measured)"

### Soft vs Hard Compaction

| Type | Mechanism | Guaranteed? |
|------|-----------|-------------|
| Hard | Physically removes messages | Yes |
| Soft | Injects context suggesting LLM ignore/summarize | No |

## CI pipeline

GitHub Actions should:
- Lint with `py_compile` + `shellcheck`
- Install + enable plugin
- Verify all hooks registered (assert `len(ctx.hooks) == N`)
- Run real API tests with secrets
- Multi-OS (ubuntu + macos)

### Docker-based CI (recommended)

Use `docker compose run --rm <service>` for each CI stage. The Dockerfile:

```dockerfile
FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y git curl bash make
WORKDIR /workspace
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
ENV PATH="/root/.hermes/bin:${PATH}"
RUN mkdir -p /root/.hermes/plugins/my_plugin && cp my_plugin/* /root/.hermes/plugins/my_plugin/
COPY configure_hermes.py /tmp/configure_hermes.py
RUN python3 /tmp/configure_hermes.py
CMD ["bash", "docker/scripts/test-runner.sh"]
```

**Pitfall: multiline Python in Dockerfiles breaks quoting.** Don't use `<<'PYEOF'` heredocs — use single-line commands or external scripts (`COPY` a Python script and `RUN python3` it).

**Pitfall: volumes on build steps wipe Docker config.** Never use `volumes: - hermes-data:/root/.hermes` on services that rely on the Docker build's `config.yaml` — the volume overlay wipes the build.

**Pitfall: Hermes needs full provider config in Docker.** Just installing Hermes isn't enough. `config.yaml` must have:
- `model.provider` and `model.default`
- `plugins.enabled: ["my-plugin"]`
- `mcp_servers.my_plugin` with `command` and `args`

Use a `configure_hermes.py` script to write this config at build time.

**Pitfall: `hermes plugins enable` doesn't persist to config.yaml in Docker build.** Run a Python script to configure `config.yaml` directly after installing Hermes.

### Hermes CLI commands in Docker

- List MCP servers: `hermes mcp list` (NOT `hermes tools list`)
- Enable plugin: `hermes plugins enable <name>`
- Disable plugin: `hermes plugins disable <name>`

### CRITICAL: Check CI after every push

After EVERY commit and push, you MUST check the CI pipeline:

```bash
sleep 30-60
gh run list --limit 1

# If failed:
gh run view <run-id> --log-failed
```

Fix, push, and repeat. **Do not move on to another task while CI is red.**

### GitHub Actions + Python pitfalls
- `ubuntu-latest` may have Python 3.14 — pin with `actions/setup-python@v5`
- `pip` may not be on PATH — use `python -m pip install` or `pip install` after setup-python
- Test jobs fail silently if TYPESAFE_API_KEY is not set — set it explicitly in env
- `gh secret set <name> --body "<value>"` — update secrets from CLI when keys rotate

## Makefile targets

```
all lint test unit integration profiles mcp benchmark install ci help clean
```

Each target that needs API key should fail explicitly if unset.

## Common pitfalls

- **pre_llm_call can't skip LLM** — don't architect around it. If you need to bypass the LLM, that requires modifying Hermes core (not possible via plugins).
- **pre_tool_call can't return results** — it's approve/block only.
- **post_tool_call return value is informational** — it doesn't inject into conversation.
- **Terminal kept for investigation** — don't deny-list `terminal` globally; the model needs it for search/debug. Use call_validator to block dangerous commands instead.
- **Test assertions must reflect real API behavior** — Jev may approve `rm -rf` in some contexts or return unexpected values. Don't hardcode expected values that depend on model behavior.
- **Write_file requires prior read** — when editing files, always call `read_file` first to get current content, then `patch` or `write_file`. Refused otherwise.
- **Hermes plugins are per-profile** — install to root AND all profiles, register MCP in each config.yaml.
- **CI secrets must be set explicitly** — use `gh secret set <name> --body "<value>"` for API tokens, reference via `${{ secrets.<NAME> }}`.
- **Forward the secret under the provider the SETUP runs, never the plugin's default.** A plugin with multiple providers reads the key name for the *configured* provider (`plugins.entries.<id>.settings.<provider_field>`), not its own default — so a self-consistent provider+key pair that doesn't match the setup is a silent failure (the plugin raises "the OTHER key is not configured"). Resolve the provider from the setup config, and make the guard reject any provider that isn't the setup's, even when the pair is internally consistent. Prove which env name the plugin actually reads by running the real installed plugin with the provider selected (`HERMES_NERVE_PROVIDER=<provider>`) and a placeholder key: no key → must raise naming THAT key; placeholder → must construct. A bare run tests the plugin's default, not the setup — select the provider explicitly before probing.
- **Squash commits before PR** — the user prefers single atomic commits, not multi-commit PRs.
