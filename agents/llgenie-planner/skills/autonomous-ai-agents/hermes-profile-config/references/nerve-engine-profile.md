# Nerve / JEV engine profile change (all homes)

Recipe for switching every home to "JEV as engine, no Kanban" — the config the
user wants when they say "use jev as an engine, not kanban supervision."

## What the change is
Two independent levers, both per home:

- `plugins.entries.nerve.settings.nerve_profile: operator` — the profile that
  turns ON `action_gate`, `context_governor`, `local_learning`, `reflex`,
  `nervous`, `receipts` and leaves `work_supervision`/`token_trajectory` OFF
  (that pair is the Kanban layer — leave it off).
- `plugins.entries.nerve.settings.gate_mode: advisory` — `action_gate` returns
  `None` when `gate_mode() == "off"`, so enabling the module alone does nothing;
  the mode must be non-`off`. `advisory` = JEV decides + logs but does not block;
  `enforce` = its verdicts actually gate execution.

## The dual write: config.yaml AND the sidecar
Nerve >= 0.3 reads `<home>/nerve/profile.json` (lean/marie_kondo/operator/...).
The config key and the sidecar must agree; the sidecar wins the module set. So
per home you write BOTH:

1. Config (default home, then loop profiles):
   ```bash
   hermes config set plugins.entries.nerve.settings.nerve_profile operator
   hermes config set plugins.entries.nerve.settings.gate_mode advisory
   for p in $(ls -1 ~/.hermes/profiles); do
     hermes -p "$p" config set plugins.entries.nerve.settings.nerve_profile operator
     hermes -p "$p" config set plugins.entries.nerve.settings.gate_mode advisory
   done
   ```
2. Sidecar, via the plugin's OWN CLI (never hand-edit the JSON — the CLI writes
   the full module map):
   ```bash
   for h in "" $(ls -1d ~/.hermes/profiles/*/); do
     home="$HOME/.hermes/${h%/}"; [ -z "$h" ] && home="$HOME/.hermes"
     (cd "$home/plugins/nerve" && HERMES_HOME="$home" python3 -m hermes_nerve setup --profile operator)
   done
   ```
   `hermes_home()` in `paths.py` honors `HERMES_HOME`, so the sidecar lands in
   the right home. `python3 -m hermes_nerve` works because `__main__.py` exists.

## Backup both targets
Back up `config.yaml` AND `nerve/profile.json` per home (40 files for 20 homes).
Use the per-file-dirname loop from SKILL.md — every source basename collides
otherwise.

## Verify by resolving, not by grepping
The authoritative check is the plugin's own resolver against each home's config
+ sidecar, in a fresh subprocess per home (avoids config-cache bleed):
```bash
for h in "" $(ls -1d ~/.hermes/profiles/*/); do
  home="$HOME/.hermes/${h%/}"; [ -z "$h" ] && home="$HOME/.hermes"
  HERMES_HOME="$home" $HOME/.hermes/hermes-agent/venv/bin/python3 - "$home" <<'PY'
import sys,os
home=sys.argv[1]
sys.path[:0]=[f"{home}/plugins/nerve","$HOME/.hermes/hermes-agent"]
from hermes_cli.config import load_config_readonly
from hermes_nerve.config_resolver import resolve_config
s=(((load_config_readonly() or {}).get('plugins') or {}).get('entries') or {}).get('nerve',{}).get('settings',{}) or {}
r=resolve_config(lambda k,d=None: s.get(k,d))
print(f"{os.path.basename(home):<18} profile={r.profile} gate={r.get_config('gate_mode')} "
      f"kanban={'YES' if r.enabled('work_supervision') else 'no'} "
      f"gate_mod={'ON' if r.enabled('action_gate') else 'off'}")
PY
done
```
Every home must print `profile=operator gate=advisory kanban=no gate_mod=ON`.
Then `ruby -ryaml -e 'ARGV.each{|f| YAML.load_file(f)}' config.yaml profiles/*/config.yaml`
for parse validity.

## Multiplexed gateway = ONE restart, not N
When `gateway.multiplex_profiles: true`, every profile is served by a single
`hermes-gateway.service` process (one PID in `hermes gateway list`). One
`hermes gateway restart` applies the new plugin config to all homes. Do NOT
restart mid-turn from the TUI — that same PID hosts the current session and the
restart kills the in-flight reply. Hand the command to the user instead.

## context.engine stays compressor unless you opt in
`operator` turns on `context_governor`, which makes Nerve REGISTER its `jev`
context engine — but Hermes only USES it when `context.engine: jev`. Default is
`compressor` everywhere. Leaving it compressor is safe (the engine registers
but is not selected); switching to `jev` changes context handling globally and
is a separate, bigger decision — flag it, don't silently flip it.

## Pitfalls
- `gate_mode: off` silently disables `action_gate` even when the module is on —
  the mode is the real switch.
- `operator` does NOT enable Kanban; `work_supervision`/`token_trajectory` stay
  off. If the user says "no kanban," `operator` is the profile that already
  satisfies it — do not also toggle supervision keys.
- Sidecar and config must agree; if you only set the config key, the sidecar's
  `lean` still wins the module set and nothing changes.
- `hermes config get` alone reads the default home; use `hermes -p <p>` for
  profiles.
