---
name: hindsight-local-llm
description: Use when Hindsight memory must run on a local model.
---

# Hindsight with a local LLM endpoint

Goal: Hindsight `local_embedded` mode (plugin-managed daemon, pg0 Postgres, local embeddings + reranker) with the extraction/reflect LLM served by llama.cpp instead of a cloud provider.

## Inference server choice
- Use llama.cpp `llama-server` (OpenAI-compatible `/v1`), not vLLM: single user, one GPU, GGUF quants, no KV headroom wasted. vLLM only pays off for many concurrent clients.
- Publish on loopback only. On this box `~/bin/llama-server` is a docker shim that maps `--host` to a `0.0.0.0` publish — bypass it and run `docker run -p 127.0.0.1:PORT:PORT --entrypoint .../llama-server IMAGE --host 0.0.0.0` so the container binds all interfaces but the host only exposes loopback.
- Disable thinking for extraction: `--chat-template-kwargs '{"enable_thinking":false}'`. Otherwise reasoning models spend the whole completion budget on reasoning and return empty `content`.
- Size the context as **total across slots, not per request**. `-c` is the whole KV budget that llama-server splits over `--parallel` slots (`n_ctx_slot = -c / parallel`), so `-c 16384` with the default 4 slots gives ~4k per request while Hindsight happily sends 3.5k-token extraction prompts *and* a consolidation call at the same time. Set `--parallel` explicitly and take `-c = per-slot × slots` (e.g. `-c 32768 --parallel 2` → 16k per slot).
- Hindsight's extraction prompts are ~3.5k tokens and expect strict JSON; a 27B IQ3_S dense model does it in ~12-20s/turn on a 16 GB laptop GPU with KV `-ctk q8_0 -ctv q8_0` (13.4 GB VRAM at 32k/2 slots).

## Config
- `$HERMES_HOME/hindsight/config.json`: `mode=local_embedded`, `llm_provider=openai_compatible`, `llm_model=<alias>`, `llm_base_url=http://127.0.0.1:PORT/v1`.
- `~/.hindsight/profiles/hermes.env` (rewritten by the plugin from config.json): `HINDSIGHT_API_LLM_PROVIDER=openai`, `_MODEL`, `_BASE_URL`, `_API_KEY`. The key must match llama-server's `--api-key`.

## Pitfalls
- **`uvx` must be on the agent process PATH.** The daemon falls back to `uvx hindsight-api@<ver>`; the Hermes python process PATH often lacks mise but includes `~/.local/bin`. Symlink `uv`/`uvx` there, else `Command not found: uvx` in `$HERMES_HOME/logs/hindsight-embed.log`.
- Prewarm with `uvx hindsight-api@1.2.0 --help` so the first daemon start is not a multi-minute download.
- **The plugin caches config.json per Hermes process.** A running TUI keeps its old LLM settings, rewrites the profile `.env` back, and restarts the daemon with them. Edit config.json, then verify from a fresh process (`hermes -p <profile> -z "reply OK"`) — it materializes env and restarts the daemon.
- Verify with the API, not the tool reply: `grep 'client initialized' ~/.hindsight/profiles/hermes.log` must show your model/base_url, then retain + recall must return extracted facts.
- **An under-sized server context surfaces as HTTP 500, not 400** — llama.cpp answers `{"code":500,"message":"Context size has been exceeded"}` and Hindsight logs it as `APIStatusError (... scope=retain_extract_facts, attempt 1/4)` then retries. `docker logs <container> | grep 'Context size has been exceeded'` names it definitively; raise `-c`/`--parallel` and restart rather than chasing it as an auth or JSON problem. Retried operations are retryable, so nothing is lost once the endpoint is resized.
- Isolated end-to-end test without touching the live profile: `uvx hindsight-embed profile create <tmp> --port <p> --env HINDSIGHT_API_LLM_*`, start, `memory retain|recall <bank> ...`, then `profile delete <tmp>`.
- The llama.cpp container's own Docker healthcheck reports `unhealthy` while the server is fine (it probes a path llama-server does not serve): judge the endpoint by `curl -s 127.0.0.1:<port>/health` → `{"status":"ok"}` and a real completion, not by `docker ps`'s status column.
- `--idle-timeout` is deprecated in hindsight-api 1.2 (daemon no longer exits when idle); budget VRAM accordingly.
