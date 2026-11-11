---
description: Bulk-edit Hermes config across all profiles safely.
name: hermes-profile-config
version: 1
license: MIT
author: hermes
metadata:
  hermes:
    tags: [hermes, config, profiles, model]
    related_skills: [hermes-agent, hermes-plugin-profile-alignment]
---

# Hermes profile config bulk edits

## When to Use
Editing settings that live in every profile's config.yaml — model switches, provider changes, auxiliary module models, delegation, fallback model, or a plugin's per-home settings — across the whole `~/.hermes` tree at once. For a plugin whose config also has a sidecar (Nerve's `nerve/profile.json`), see `references/nerve-engine-profile.md` — the config key and sidecar must BOTH be written per home.

## Layout
- Main config: `~/.hermes/config.yaml`
- Per-profile: `~/.hermes/profiles/<name>/config.yaml` (count the live dirs with `ls ~/.hermes/profiles` — enumerate, never assume, never hardcode a count)
- EXCLUDE from edits AND backups: `config-backups/*`, `profiles/*/state-snapshots/*`, `hermes-agent/**/templates/*`. Only live `config.yaml` + `profiles/*/config.yaml` get touched.

## Backup first (user mandate — do this before ANY edit)
Plain `cp config.yaml profiles/*/config.yaml <dir>/` is WRONG: every source has the same basename `config.yaml`, so all but the first get rejected/overwrite and the backup is silently incomplete. Loop with per-file dirname:
```bash
BK="$HOME/.hermes/config-backups/model-switch-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$BK"
for f in config.yaml profiles/*/config.yaml; do d="$BK/$(dirname "$f")"; mkdir -p "$d"; cp "$f" "$d/"; done
```
Verify `find "$BK" -type f | wc -l` equals the number of live configs before proceeding.

## What to replace — a model switch is TWO halves
A model id lives at many keys, all pointing at the same provider string: `model.default`, every `auxiliary.<mod>.model`, `delegation.model`, `fallback_model.model`. A global string replace across all live configs catches those:
```bash
cd ~/.hermes
for f in config.yaml profiles/*/config.yaml; do sed -i 's#OLD_MODEL#NEW_MODEL#g' "$f"; done
```
Use `#` not `/` as the sed delimiter — model ids contain slashes.

That replace does NOT move a profile's MAIN model. Profiles frequently default to a local server, so their top-level block reads `default: local-llm` / `provider: custom` / `base_url: http://127.0.0.1:11434/v1` / `context_length: 65536` while every auxiliary key already names the cloud id — a string replace then leaves the profile serving from a stopped local endpoint. Dump the blocks to see who is where before editing:
```bash
ruby -ryaml -rjson -e 'ARGV.each{|f| m=YAML.load_file(f)["model"]||{}; puts f+" "+m.reject{|k,_| k=="aliases"}.to_json}' config.yaml profiles/*/config.yaml
```
When the request is "set ALL configs to <model>", the top-level `model:` block is the half the user actually means: set `default` to the exact new id, `provider: nous` (or that id's provider), `base_url` to the provider endpoint, and DROP the local-only `context_length` — leaving 65536 on a 1M-context cloud model makes compression fire ~15x too early. Rewrite the block with `scripts/set_default_model.py` (idempotent, rewrites only the leading top-level `model:` block):
```bash
python3 <skill_dir>/scripts/set_default_model.py <model-id> [provider] [base_url]
```
It writes a `local-llm` alias alongside so the local server stays reachable via `-m local-llm` instead of being silently lost when `base_url` moves off 127.0.0.1.

**Pitfall — a longer id that STARTS with the old one double-suffixes.** Going `deepseek/deepseek-v4.1-flash` → `...-1017` with a plain `s#old#new#g` also rewrites the ids you just fixed, producing `-1017-1017`, and re-running the loop keeps appending. Anchor the bare id at end of line (`sed -i -E 's#(deepseek/deepseek-v4\.1-flash)[[:space:]]*$#\1-1017#'`) or, better, replace the longer/prefixed forms FIRST and verify with a grep that the new id occurs exactly once per key.

## Pointing scripts at a local LLM server
When the user wants cron/script jobs to hit a local server (llama.cpp, Ollama, vLLM) instead of the cloud model, do NOT edit every script's model string to a raw URL — define a `local` alias once, then scripts reference it by name:
```bash
hermes config set model.aliases.local '{"model":"llm-local","provider":"custom","base_url":"http://localhost:11434/v1"}'
```
Verify the alias resolves before touching scripts: `hermes config get model --json` shows it, and `hermes chat -q "reply ok" -m local` runs against the local endpoint. Then swap the script's `-m "cloud/model"` → `-m "local"`. The scripts stay LLM-agnostic; only the alias points at the server.

**Pitfall — grep the WHOLE repo, not one scripts dir.** Call sites live in `scripts/`, `Projects/*/scripts/`, `Projects/*/skills/*/run.sh`, and root `.py` files. A search scoped to `scripts/` misses most of them. Before declaring done, `grep -rl 'OLD_MODEL' --include='*.sh' --include='*.py' .` across the repo root and fix every hit.

**Pitfall — sed misses the Python list form.** Shell scripts use `-m "model"` (sed-able), but Python subprocess calls use `["hermes","chat","-q",prompt,"-m","model",...]` — a comma-separated list, so `sed 's/-m "model"/-m "local"/'` silently does nothing. Grep for BOTH `-m "model"` and `"-m", "model"`; fix the list form with a targeted patch, not sed.

**Verify:** zero old-model refs remain across all `.sh`/`.py` (`grep -rl OLD ... || echo NONE`), and the new `-m "local"` count matches the number of call sites you found.

## Per-profile `config set` loop (non-model keys)
For settings that are not model-string replacements, loop with the CLI instead of sed: `default` → `hermes config set K V`, others → `hermes -p <p> config set K V` (`ls ~/.hermes/profiles`). Booleans land as the quoted string `"true"`; that is fine for gate keys (`agent.tool_use_enforcement`, `agent.execution_guidance` parse true/false words). `agent.reasoning_effort` is read by CLI, TUI and gateway via `hermes_constants.resolve_reasoning_config`, even though `hermes config get` suggests it is unknown.

## Local single-slot servers (Strata/llama.cpp)
Set `model.context_length` explicitly to the server's n_ctx: the auto-probe sometimes falls back to 256K, so compression fires far too late. Keep auxiliary/delegation on a cloud model: extra local calls evict the main conversation's KV cache, and every following turn then re-reads the full prompt.

## Leave alone
Do NOT global-replace blindly — exclude non-hermes model values in the same files: `typesafe_model: jev-latest`, voice/STT models (`whisper-*`, `base`, `voxtral-mini-latest`), and empty-string models. If your old-string target only matches the hermes provider id, the sed is safe; otherwise tighten the pattern.

## Verify (do not skip)
1. No old string remains: `grep -rn "OLD" config.yaml profiles/*/config.yaml` must exit nonzero (no matches).
2. New string lands where expected: `grep -rc "NEW" config.yaml profiles/*/config.yaml` — counts vary by profile (minimal stubs have 1 hit, most have ~19). Confirm zero files show old, and check `model.default` and `fallback_model.model` explicitly.
3. Every file's top-level block agrees — id, provider AND base_url — not just that the id is present somewhere:
   ```bash
   ruby -ryaml -rjson -e 'ARGV.each{|f| m=YAML.load_file(f)["model"]||{}; print f+" "+[m["default"],m["provider"],m["base_url"],m["context_length"].inspect].join(" ")+"\n"}' config.yaml profiles/*/config.yaml
   ```
   A file that still shows `local-llm` / a 127.0.0.1 base_url is an unfinished profile.
4. YAML still parses: `ruby -ryaml -e 'ARGV.each{|f| YAML.load_file(f)}' config.yaml profiles/*/config.yaml` (python3 often lacks the `yaml` module on this host; ruby is the reliable validator).
5. The CLI agrees and the model actually answers — config text alone does not prove a route. One profile is enough as a smoke test:
   ```bash
   hermes -p <profile> config get model --json      # default/provider/base_url
   hermes -p <profile> chat -q "reply with exactly: ok"
   ```
   A real 2-5s reply means the provider route works; a multi-minute hang on a profile that was previously local means its block did not move.

## Preferences
- User's model requests are literal: use the EXACT id string they gave (e.g. session model `deepseek/deepseek-v4.1-flash-1017`), not a family/short name. When they say "the one we're using now", that's the active session model from runtime metadata.
- "All configs" / "including default" means the MAIN model too (`model.default` + provider + base_url in every profile), not only the auxiliary/delegation/fallback keys. Report which profiles were left on a local endpoint and ask before dragging a deliberately-local profile (`local-llm`, `hermes-llm`, `singularity`-style) onto the cloud; a one-line question beats silently breaking its purpose.
- Make the backup before any destructive bulk edit; confirm the backup count before changing anything.
- Report: backup path + count, files changed, 0-old-strings verified, YAML valid. Terse.
