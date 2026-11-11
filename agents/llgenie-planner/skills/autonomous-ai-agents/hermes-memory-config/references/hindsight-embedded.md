# Hindsight embedded daemon — internals worth knowing

## Where state lives

| Path | What it is |
|---|---|
| `$HERMES_HOME/hindsight/config.json` | plugin config (mode, provider, model, base url, banks); `0600` |
| `~/.hindsight/profiles/<profile>.env` | daemon env, rewritten by the plugin from the config; `0600` |
| `~/.hindsight/profiles/<profile>.log` | daemon log — the authoritative record of provider/model |
| `~/.hindsight/profiles/<profile>.lock` | pid of the owning daemon; clear it only when no daemon holds the port |
| `~/.pg0/instances/hindsight-embed-<profile>` | embedded Postgres; survives daemon restarts, so stops lose no data |

The daemon's profile name defaults to `hermes` — the `profile` key in `config.json` is what splits lanes.

## Plugin functions (import from `hindsight.embedded`)

`_build_embedded_profile_env(config)` builds the env dict from config; `_materialize_embedded_profile_env(config)`
writes it `0600`; `_profile_env_drifted(config)` is what triggers rewrite+restart; `_stop_daemon(profile)` /
`_start_daemon(env, profile)` control the process; `_embedded_profile_env_path(config)` returns the env path.

Run them with the Hermes venv interpreter, from the profile dir:

```bash
cd "$HERMES_HOME" && HERMES_HOME="$HERMES_HOME" ~/.hermes/hermes-agent/venv/bin/python - <<'EOF'
import sys
sys.path.insert(0, '$HOME/.hermes/hermes-agent')
sys.path.insert(0, '$HERMES_HOME/plugins')
import hindsight as H
from hindsight.embedded import _build_embedded_profile_env, _materialize_embedded_profile_env
cfg = H._load_config()
for k, v in _build_embedded_profile_env(cfg).items():
    print(k, '=', '<set>' if 'KEY' in k else v)
_materialize_embedded_profile_env(cfg)
EOF
```

`_load_config()` re-reads the JSON each call, so the script reflects an edit immediately — the live agent's
plugin object does not.

## Env keys written by the plugin

`HINDSIGHT_API_LLM_PROVIDER` (`openai` for any OpenAI-wire endpoint), `HINDSIGHT_API_LLM_API_KEY`,
`HINDSIGHT_API_LLM_MODEL`, `HINDSIGHT_API_LLM_BASE_URL`, `HINDSIGHT_API_LOG_LEVEL`,
`HINDSIGHT_EMBED_DAEMON_IDLE_TIMEOUT`. Keys the plugin does not own (`HINDSIGHT_API_PORT`, a hand-set
`*_DATABASE_URL`) are preserved across rewrites; comments in the file are not.

`idle_timeout: 0` means never self-stop; the default 300s shuts the daemon down when idle, which reads as
"not running" on a later check even though nothing is broken.

## Verification endpoints

```bash
curl -s 127.0.0.1:9177/health                      # status + database
curl -s "127.0.0.1:9177/v1/default/banks/hermes/stats"
curl -s "127.0.0.1:9177/v1/default/banks/hermes/memories/list?limit=5"
curl -s 127.0.0.1:9177/openapi.json                # full route list (recall/reflect/entities/directives)
```

`stats` exposes `pending_operations` / `failed_operations`; a `failed` op is usually a transient drain during
a restart, not a config error — check whether a batch retain completes afterwards before chasing it.

## Local-LLM variant

Same machinery with a llama.cpp server: `llm_provider: openai_compatible`,
`llm_base_url: http://127.0.0.1:<port>/v1`, `llm_model` = the server's `--alias`, key = whatever the server's
`--api-key` is (the plugin writes `not-needed` only when the config carries no key at all). Confirm the port
with `ss -tlnp` — a server started on 8081 while the config still says 8080 answers nothing and looks down.
