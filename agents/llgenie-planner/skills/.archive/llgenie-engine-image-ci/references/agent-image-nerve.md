# The agent image's nerve / JEV layer: profile vs settings

The bot image (`containers/agent/Dockerfile` → `scripts/install_nerve_ci.sh`) installs the `keeltrace/hermes-nerve`
plugin at a pinned commit and wires it the way a host runs it. Two halves decide whether the decision layer is
actually ON, and they are easy to disagree:

- **the profile sidecar** `${HERMES_HOME}/nerve/profile.json` (`{"version": 1, "nerve_profile": <name>, …}`), written
  through the plugin's own `save_profile` so it is validated and atomic;
- **the settings** under `plugins.entries.nerve.settings.<key>` (a value one level up is silently ignored and the
  schema default wins).

## A named profile decides the MODULES; settings only tune them

`hermes_nerve/config_resolver.py` builds a named profile's module set from `PROFILES[name]` **verbatim**
(`modules = dict(PROFILES[name])`). Only the `legacy`/`custom` branch derives modules from flags, and the later
`runtime_enable_flags` pass can only switch a module **off**. So writing a setting for a module the profile does
not register produces a setting that is written and never read — configured on paper, off in the run, with
nothing visibly broken.

Concrete module sets (v0.3.x):

| profile | modules |
|---|---|
| `operator` | reflex, nervous, **action_gate**, **context_governor**, receipts, **local_learning** |
| `lean` | reflex, nervous, work_supervision, token_trajectory, receipts |
| `marie_kondo` | reflex, work_supervision, token_trajectory, receipts |

Consequences to state plainly when reviewing such a config:

- `context_engine_mode: apply` / `context_curation_mode: apply` need `context_governor`; under `lean` they are inert.
- `gate_mode: advisory|enforce` needs `action_gate`; under `lean` the pre-tool decision cannot fire at all
  (`gate_mode: off` there is honest, not a downgrade).
- Supervision settings need `work_supervision`; under `operator` that module is off, so a non-`shadow` mode asks a
  module that is not running.
- `nervous_local_learning` defaults true but the module must still be in the profile.

## Verify the pair at BUILD time, against the INSTALLED plugin

After writing the settings and the sidecar, run a parity check that imports the plugin's own `PROFILES` from
`$HERMES_HOME/plugins/nerve` and fails the build when an active setting's module is not enabled. Rules that earn
their keep:

| setting | module it needs | active when |
|---|---|---|
| `gate_mode` | `action_gate` | != `off` |
| `context_engine_mode` | `context_governor` | not in `shadow`, `off` |
| `context_curation_mode` | `context_governor` | not in `shadow`, `off` |
| `work_supervision_mode` | `work_supervision` | != `shadow` |
| `nervous_enabled` | `nervous` | true |

A shadow/off setting must demand nothing (a mode that measures nothing is not a request). Print the resolved
module set on success so the build log says what is on. Make the rule importable as well as CLI-runnable, so a
hermetic test can prove both directions with synthetic profile tables — one that enables everything, one that does
not — without installing the plugin.

## When comparing a host to the image

Read both sides before editing: the host's `~/.hermes/config.yaml` → `plugins.entries.nerve.settings` plus
`~/.hermes/nerve/profile.json`, and the image's `scripts/install_nerve_ci.sh` defaults / `containers/agent/Dockerfile`
`ARG`s. A difference is only a defect when it changes which modules register; a differing comment or a
build-arg override that resolves to the same value is not. Write the profile into the settings as well as the
sidecar (the host carries both), so `hermes config get plugins.entries.nerve.settings.nerve_profile` answers.

## Runtime half

`scripts/agent_jev_preflight.sh` reports (never blocks) whether the layer is available for THIS run: plugin in
the home, plugin enabled, provider key present (value never printed — filtered through a redactor), and a live
provider smoke. `NERVE_REQUIRE=1` turns any of those into a non-zero exit and is the image-verification mode.
A `--rm` bot container still loses anything the layer learns between runs; treat that as a documented limit, not
a bug to paper over.
