---
name: hermes-nerve-jev-engine
description: Use when tuning hermes-nerve Jev engine usage.
---

# hermes-nerve: making Jev used as an engine (no Kanban)

Nerve is a **supervisory** layer, not an LLM replacement. Its design invariant is
"Jev must earn every token it spends" (<=2% overhead on healthy runs), so Jev calls
only fire at decision boundaries. "Jev used less than the LLM" is normal.

## Resolution precedence (what actually wins)

`resolve_config()` in `hermes_nerve/config_resolver.py`:

1. `plugins.entries.nerve.settings.nerve_profile` (config.yaml) — **wins if set**.
2. else sidecar `~/.hermes/nerve/profile.json` -> `nerve_profile`.
3. else `legacy` (v0.2.3 behavior).

If config.yaml names a profile that differs from the sidecar, sidecar `advanced` and
`nerve_modules` are **ignored** for that run.

Settings live at `plugins.entries.nerve.settings.<key>`. An entry-level key
(`plugins.entries.nerve.<key>`) is never passed to the plugin.

## Module sets that matter

- `lean`  = reflex, nervous, **work_supervision, token_trajectory**, receipts  (Kanban-heavy)
- `operator` = reflex, nervous, **action_gate, context_governor**, receipts, local_learning  (Jev-as-engine, **no Kanban**)

Use `operator` (or `custom`) when the goal is "Jev as engine"; use `lean` only when Kanban
worker supervision is wanted. `work_supervision`/`token_trajectory` are the Kanban pair and
can be dropped without losing `reflex`/`nervous`/`action_gate`.

## The trap: gate_mode=off disables action_gate

`gate.evaluate_tool_call()` returns `None` when `gate_mode() == "off"`. So enabling the
`action_gate` module is useless if `gate_mode` is `off` — no Jev call happens per tool call.
Set `gate_mode` to `advisory` (log only, fail-open) or `enforce`/`ask-only` (can block).
In profile mode the resolved mode is `profile_default("gate_mode", env, "advisory")`, so an
explicit `gate_mode: 'off'` in config.yaml overrides the profile default.

## Apply

Config writes by the agent are refused; use the CLI. Values may be re-quoted (`advisory` ->
`'advisory'`) — harmless.

```bash
hermes config set plugins.entries.nerve.settings.nerve_profile operator
hermes config set plugins.entries.nerve.settings.gate_mode advisory
```

Align the plugin sidecar (atomic, with backup):

```bash
cd ~/.hermes/plugins/nerve && python3 -m hermes_nerve.cli setup --profile operator
```

## Verify resolution before trusting it

```bash
cd ~/.hermes/plugins/nerve && $HOME/.hermes/hermes-agent/venv/bin/python3 - <<'PY'
import sys; sys.path[:0]=['$HOME/.hermes/plugins/nerve','$HOME/.hermes/hermes-agent']
from hermes_cli.config import load_config_readonly
from hermes_nerve.config_resolver import resolve_config
s=(((load_config_readonly() or {}).get('plugins') or {}).get('entries') or {}).get('nerve',{}).get('settings',{}) or {}
r=resolve_config(lambda k,d=None: s.get(k,d))
print(r.profile, r.get_config('gate_mode'))
print("ON:",[k for k,v in r.modules.items() if v])
PY
```

## A named profile's modules come VERBATIM from `PROFILES`

`config_resolver` builds a named profile's module set as `dict(PROFILES[name])`. Settings do **not**
enable modules: the later `runtime_enable_flags` pass only turns modules OFF. So a setting written for a
module the profile does not register is **inert — written and never read**, with nothing visibly broken
(no warning at load). This is the trap that makes a config look tuned while the layer is off:

| setting | needs module | inert unless the profile has it |
|---|---|---|
| `gate_mode` != `off` | `action_gate` | `operator`, not `lean` |
| `context_engine_mode` / `context_curation_mode` != `shadow`/`off` | `context_governor` | `operator`, not `lean` |
| `work_supervision_mode` != `shadow` | `work_supervision` | `lean`/`marie_kondo`, not `operator` |
| `nervous_enabled: true` | `nervous` | both |
| `nervous_local_learning` | `local_learning` | `operator` only |

So when baking a profile into an image, a container, or any fixed config: pick the profile and the
settings together, and leave a mode that asks nothing (`gate_mode: off`, `*_mode: shadow`) for a module
the profile does not register. Better, assert it: a build-time check that maps each written setting to
the module it needs and fails when `PROFILES[profile]` does not enable it (`operator` + `apply` +
`advisory` passes; `lean` + the same settings fails on `action_gate` and both `context_*` keys). A
test that only checks the values were written proves nothing — it is exactly the failure mode above.

Write the profile in BOTH places when you control the config: the `nerve_profile` setting and the
`nerve/profile.json` sidecar. `allow_tool_override: false` keeps the model from overriding what the
layer decided, which is the whole point of paying for the decision call.

## Pitfalls

- **Restart required.** Settings are read at plugin registration (process start). The running
gateway keeps the old profile until `hermes gateway restart`. Do NOT restart mid-turn: the
agent turn runs inside the gateway process, so the restart kills the in-flight response.
- **Kanban binding noise.** `work-supervision.sqlite3` fills with `autobind_task_missing` rows
(one per tool call) whenever `work_supervision` is on and there is no
`HERMES_KANBAN_TASK_ID`. Turning the module off stops it; it is not a bug in itself.
- **`work_supervision_mode`, `context_*` keys are inert** when their module is off.
- Live evidence lives in `~/.hermes/nerve/` (`receipts.jsonl`, `nervous-events.jsonl`,
  `decision-outcomes.jsonl`, `work-supervision.sqlite3`), NOT the legacy `~/.hermes/jev/`
  directory, which goes stale after v0.2.2.
- Check the real provider: `receipts.jsonl` records show `provider`/`model` (e.g. typesafe /
  jev-1.13.0).
