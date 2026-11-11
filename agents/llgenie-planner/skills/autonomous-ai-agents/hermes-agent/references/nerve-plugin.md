# Nerve / JEV plugin — usage diagnosis

How to answer "why is Nerve / JEV used so little / not at all", "is JEV active", "is JEV calling the provider". The plugin is a **supervisory watchdog, not an LLM replacement** — low usage is the design intent, not a bug.

## Principle to state first

JEV is a cheap typed reviewer invoked only at **decision boundaries**: turn admission below the confidence threshold (default `call_threshold`, ~0.58), repeated-failure fingerprints, budget checkpoints, completion verification. Healthy runs stay local (`assessment_silent` provenance, no provider call); the plugin operates toward a ~2% overhead target. "JEV should be called more than the main LLM" is inverted from what it does — JEV is meant to be called far *less* often, only where a decision is worth the token spend. More JEV calls is a tuning choice that costs tokens; it is not "cheaper" by default.

## Live data paths

Normal Hermes sessions run in **`~/.hermes/nerve/`**, not `~/.hermes/jev/` (the `jev/` dir is legacy/stale). Probe `~/.hermes/nerve/` first by mtime. Files:

- `receipts.jsonl` — one line per JEV decision with `provider`, `model` (e.g. `typesafe`, `jev-<ver>`), `latency_ms`. Count provider calls from here.
- `decision-outcomes.jsonl` — `decision` records; `decision_id` prefixes `jev-` (provider-sourced) vs `local-` (local, no provider).
- `nervous-events.jsonl` — event stream incl. `assessment_silent` (local-only, no JEV call) vs provider calls.
- `work-supervision.sqlite3` — tables `supervision_diagnostics`, `run_bindings`, `work_events`, `budget_checkpoints`, `run_directives`, `api_usage`, `supervisor_usage`.
- `gate-events.jsonl` — action-gate decisions (only populated if `action_gate` is enabled AND `gate_mode != off`).

### Quantify JEV vs main-LLM calls

```bash
cd ~/.hermes/nerve
# JEV provider calls today (receipts row ~= one JEV decision):
python3 -c "import json,collections; c=collections.Counter()
[ c.__setitem__(l[:10], c.get(l[:10],0)+1) for l in (json.loads(x).get('ts','')[:10] for x in open('receipts.jsonl',encoding='utf-8') if x.strip()) ]
print(sorted(c.items()))"
# main-LLM calls today:
grep '"2026-...-" .*API call #' ~/.hermes/logs/agent.log | wc -l
```

## What controls JEV usage

1. **Modular profile** (`~/.hermes/nerve/profile.json`, `nerve_profile` key) — decides which decision modules are armed. `lean` (committed default) = `{reflex, nervous, work_supervision, token_trajectory, receipts}`. `operator` adds `action_gate` (reviews every tool action → many more JEV calls), `context_governor`, `local_learning`. `fat_cat` = everything except shadow_testing/shared_context. Profiles live in `hermes_nerve/profiles.py`.
2. **`gate_mode`** (`off`/`advisory`/`enforce`) — `off` disables the action-gate even when the `action_gate` module is present. Gate is the highest-volume JEV call site.
3. **Kanban binding** — worker-supervision / token-trajectory modules need `HERMES_KANBAN_TASK_ID` / `HERMES_KANBAN_TASK` set via `ensure_kanban_binding()` in `hermes_nerve/work/autobind.py`. A plain TUI/agent session has none → those modules stay idle.

Each call site (action gate, per-tool review, budget checkpoint, completion DoD check) adds real JEV tokens. "Use JEV more" = turn on `action_gate` or raise `nervous` thresholds, with the token cost acknowledged.

## Interpreting the diagnostic tables

- **`supervision_diagnostics` flooded with `autobind_task_missing` and `run_bindings` = 0** in `work-supervision.sqlite3` is the *expected* state for non-Kanban sessions. `ensure_kanban_binding()` returns None for every tool call when no Kanban task env is present. Not a bug — worker-supervision simply only runs under real Kanban dispatch.
- Log line `Nerve headless supervision did not bind at startup` + `headless_worker=True` = the same missing-Kanban-task condition in Kanban worker runs; check `supervision_diagnostics` before trusting a run as Nerve-supervised.

## Levers — exact config edits

```bash
hermes config set plugins.entries.nerve.settings.nerve_profile operator   # or fat_cat / lean / custom
hermes config set plugins.entries.nerve.settings.gate_mode enforce        # per-tool JEV review (highest call volume)
# verify resolved profile:
cat ~/.hermes/nerve/profile.json
```

Plugin settings live under `plugins.entries.nerve.settings.<key>` — a value at `entries.nerve.<key>` is silently ignored (see the SKILL hard-invariant). `profile.json` may additionally be written directly by the plugin; it is the authoritative record of the resolved profile.
