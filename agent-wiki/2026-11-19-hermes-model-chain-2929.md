# Hermes model chain: profiles load their models from one base config (issue #2929, PR #TBD)

## What was verified against the spec (`openspec/changes/hermes-model-chain/`)

- **One chain file, one seam.** `agents/hermes-base-config.yaml` declares the model chain:
  primary `meituan/longcat-2.5:free` via alias `nous-longcat`, fallbacks in alias order
  (`nous-hy4` → `nous-step` → `nous-qwen4max` → `nous-solar`), paid `deepseek/deepseek-v4-flash-0731`
  LAST; per-model budgets read from the live Nous catalog (128k max_tokens for longcat/hy3/qwen4max/step,
  16k for hy4-flash/solar-mini4, 64k for deepseek). `scripts/apply_hermes_base_config.py` is the ONLY
  writer of the owned keys (`model`, `fallback_providers`) — merge-based, never a wholesale config
  replacement; `CHECK=1` compares instead of writes; `--lanes` limits the write to `llgenie-*` profiles
  (the interactive default home's model config is not the bots' chain's owner), `--all` covers home + profiles.
- **No bot sets a model anymore.** Every agent invocation is a profile: `hermes -p llgenie-<lane>`.
  `nous-alias`/`nous-model` are deleted from the Makefile and the 9 call sites (`mk/bots.mk` ×6,
  `mk/agents.mk` ×1, `mk/engines.mk` ×2) became `-p llgenie-<lane>`; `scripts/fix_loop.sh` AGENT_CMD
  runs `-p llgenie-issse-implementer` with no `-m`; `scripts/hermes_smoke.py` takes `--profile`.
  The referee refuses a `-m`/`--model` flag in any bot call file.
- **The referee is the chain gate.** `scripts/agent_model_pin.py` (`make check-agent-model`, a
  `ci-unit` step) validates: base config parses; primary first + every alias in the chain with the
  paid model last; the primary is NOT in its own fallback list; budgets match the catalog rules; no
  `-m` bot flags; the install seam (`scripts/install_hermes_ci.sh`), provisioner
  (`scripts/provision_agent_profiles.py`) and lanes check (`scripts/agent_lanes_check.py`) reference
  the base config; and every `-p <lane>` name is declared in `agents/manifest.json`. The Hermes
  VERSION pin checks from the concurrent version-pin change are kept intact — the referee gained
  chain checks, it did not lose version checks (18 tests green in `tests/test_agent_model_pin.py`).
- **Host and image land the chain through the SAME seam.** `install_hermes_ci.sh` applies the base
  config instead of the old alias-setup block; the Dockerfile drops `HERMES_MODEL_ID`/`HERMES_ALIAS`
  ARGs and bakes the chain via COPY + apply (`--all`); `provision_agent_profiles.py` imports the seam
  and lands the chain into every lane profile's `config.yaml`, and `agent_lanes_check.py` refuses a
  profile whose chain drifts from the base. Host parity proof: `make provision-agent-profiles` landed
  the chain into every live lane profile (rc=0), `make apply-hermes-base-config CHECK=1` rc=0,
  `make check-agent-model` rc=0.
- **Registration (measured, not assumed).** `apply_hermes_base_config` joins package-layers
  "Bots and automation" with a stated `agent_lanes_check → apply_hermes_base_config` allowed edge
  (one owned-key comparison shared by gate and installer); the `apply-hermes-base-config` target lives
  in `mk/agents.mk` and was added to the agents-split roster in
  `tests/test_makefile_agents_mk_split.py`; documented in `docs/BOTS.md`; `make check-wiring` rc=0 —
  the script is CI-REACHED (install_hermes_ci.sh + provisioner import + Dockerfile COPY), so no
  `host-only-wiring.json` entry is needed for the script; the host-only TARGET needs none either
  (wiring is about unwired documents/scripts, `make check-wiring` green).

## Key decisions

- The fallback list never contains the primary model — Hermes hops only after the primary fails, so
  the chain is longcat → 5 free fallbacks → deepseek paid last; the referee enforces that ordering.
- `make apply-hermes-base-config` (host) defaults to `--lanes`: the interactive default home is not
  the bots' chain's owner. The image path uses `--all` so the global home and every profile agree.
- Out-of-scope work is its own issue: a live per-profile model-call smoke proof is deferred (filed as
  its own issue; named in the PR body), as is the pinned-model config for the status-keeper profile
  family — the chain lands uniformly for all 11 manifest lanes.

## Current status

Branch `feat/hermes-model-chain`; tasks 1–12 ticked with local proofs; gates green locally
(`check-agent-model`, `apply-hermes-base-config CHECK=1`, `check-wiring`, `check-package-layers`,
targeted 8-file batch ALL PASS, full `make test-unit` green after the registration fixes); the PR
targets upstream main with `closes #2929`.
