# Profile-loaded Hermes model chain (issue #2929)

## Why

Every CI bot invocation hard-codes one model: `nous-alias := -m nous-deepseek` (Makefile:240-241) is
appended to all 9 Hermes call sites, `scripts/fix_loop.sh` passes `-m ${FIX_AGENT_ALIAS:-nous-deepseek}`,
and `scripts/install_hermes_ci.sh` writes the single alias into the image's GLOBAL Hermes config. The 13
lane profiles the image installs carry no model config at all, and the pin
(`deepseek/deepseek-v4-flash-0731`) — the chain's LAST-resort model — is what answers every bot call
today, while five `:free` Nous catalog entries are live. The owner's policy is the opposite: free Nous
models first (LongCat first), the other free models as fallbacks, deepseek-v4-flash-0731 last — loaded
per profile from a base `config.yaml` that is the same for every llgenie profile.

## What changes

- **New `agents/hermes-base-config.yaml`** — the ONE base Hermes model config. Measured against
  Hermes 0.23.2, profile mode sends `model.default` verbatim to the endpoint (an alias there 404s)
  and a `fallback_providers` entry only hops when it names the full route (`provider: custom` +
  `base_url` + `key_env`), so the config is shaped accordingly: `model.default` is
  `meituan/longcat-2.5:free`; the `model` block carries the route (`provider: custom`, the Nous
  OpenAI-compatible `base_url`, `key_env: NOUS_API_KEY`, `max_tokens: 16000`) plus the six aliases
  (`nous-longcat` … `nous-deepseek`) bound to catalog ids; the `fallback_providers` chain repeats
  the route shape in order `tencent/hy4-flash:free` → `stepfun/step-3.7-flash:free` →
  `qwen/qwen4-max:free` → `upstage/solar-mini4:free` → `deepseek/deepseek-v4-flash-0731` (LAST);
  every alias carries its catalog `context_window` and the 16000-token reply budget (#405 precedent).
- **New `scripts/apply_hermes_base_config.py`** — merges the base's owned keys (the whole `model`
  route block, its aliases, `fallback_providers`) into a Hermes home config and every lane profile's
  `config.yaml`, preserving keys the base does not own.
- **New `scripts/seed_profile_hermes_env.py`** — profile mode reads `key_env` from the PROFILE's own
  `.env`, not the caller's process environment (measured). The image seeds `NOUS_API_KEY` from the
  leg's environment into the global home's and every llgenie profile's `.env` at leg start through a
  `/etc/profile.d` hook (agent legs boot `bash -lc`); the host reaches the same script through the
  new `make seed-hermes-profile-env` (`--lanes`, never touching the interactive default home's
  `.env`). The seed never invents, prints, or duplicates a value and no-ops loudly when no key is
  in the environment.
- **Install + image** — `install_hermes_ci.sh` installs the base config (global home + per-profile write
  via the provisioner) instead of the single alias; `containers/agent/Dockerfile` drops
  `HERMES_MODEL_ID`/`HERMES_ALIAS` single-pin ARGs, bakes and asserts the CHAIN (primary + 5 fallbacks,
  order-sensitive, deepseek last), and `agent_lanes_check.py` refuses profiles whose chain differs.
- **Bot invocations carry no model** — `nous-alias` is deleted; the 9 call sites run
  `hermes -p llgenie-<lane>` (issue-evidence→`llgenie-planner`, refine→`llgenie-planner`,
  dedupe→`llgenie-planner`, triage→`llgenie-planner`, architecture→`llgenie-architect`,
  implement→`llgenie-issse-implementer`, rebase→`llgenie-pr-merge-conflict`,
  registry-review/engine-params→`llgenie-engine-improver`); `fix_loop.sh` drops `-m` and runs
  `-p llgenie-issse-implementer`; `hermes_smoke.py` proves the profile-resolved route instead of `--alias`.
- **`scripts/agent_model_pin.py` becomes the chain referee** — `make check-agent-model` reads the base
  config and refuses drift in chain order, budgets, route shape (every route names `provider`,
  `base_url`, `key_env`; no alias in the default slot), and wiring (no `-m nous` left in any bot
  recipe; install/provision/lanes-check reference the base file; the Dockerfile wires the seed hook).

Supersedes the single-snapshot pin requirements of `bot-model-1017`/`agent-image-model-pinned-2818`: the
chain's LAST member keeps the exact snapshot id, and the same gate family (`check-agent-model`) now
enforces the chain instead of one value.

## Impact

- Affected specs: new capability `agent-model-chain` (this change).
- Affected code: `agents/hermes-base-config.yaml` (new), `scripts/apply_hermes_base_config.py` (new),
  `scripts/seed_profile_hermes_env.py` (new), `scripts/agent_model_pin.py`,
  `scripts/install_hermes_ci.sh`, `containers/agent/Dockerfile`,
  `scripts/provision_agent_profiles.py`, `scripts/agent_lanes_check.py`, `scripts/ci_images.py`
  (agent build stages the seed script), `Makefile`, `mk/bots.mk`, `mk/agents.mk`, `mk/engines.mk`,
  `scripts/fix_loop.sh`, `scripts/hermes_smoke.py`, `scripts/package-layers.json`.
- Affected tests: `tests/test_agent_model_pin.py` (rewritten), `tests/test_apply_hermes_base_config.py`,
  `tests/test_seed_profile_hermes_env.py` (new), `tests/test_provision_agent_profiles.py`,
  `tests/test_makefile_agents_mk_split.py`, `tests/test_fix_loop.py`,
  `tests/test_hermes_smoke.py`, `tests/test_issue_implementer.py`, `tests/test_agent_skills.py`,
  `tests/test_rebase_bot_sweep.py`.
- Out of scope (filed as #2930, #2931): weekly `:free` catalog-membership monitoring; per-run
  model-route reporting.
