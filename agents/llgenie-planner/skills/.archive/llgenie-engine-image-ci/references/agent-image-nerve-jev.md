# Agent image — Hermes + nerve/JEV layer

What the bots' agent image must carry, and how to change it without shipping a config that looks
configured and is off in the run.

## The pieces

| File | Role |
|---|---|
| `containers/agent/Dockerfile` | ARGs for the plugin pin, provider, profile, gate/supervision modes; `COPY`s the install scripts into the build context |
| `scripts/install_nerve_ci.sh` | BUILD half: installs the plugin at an immutable 40-char SHA, drops the unused `laya` extra, enables it, writes `plugins.entries.nerve.settings.*`, writes the profile sidecar, verifies, then runs the parity check |
| `scripts/agent_jev_preflight.sh` | RUN half: reports whether the layer is available for THIS run, wires the provider key into `$HERMES_HOME/.env`, never blocks (unless `NERVE_REQUIRE=1`, which image checks and bot workflows arm) |
| `scripts/nerve_profile_check.py` | the parity rule (setting → required module) against the INSTALLED plugin's `PROFILES` table; `--self-test` via `make nerve-profile-check` |
| `scripts/ci_images.py` (`IMAGES["agent"]`) | the hash inputs: every COPYed/RUN file must be listed, or a change does not move the image tag |

## The trap: settings cannot switch a module ON

A **named** nerve profile resolves its module set verbatim from the plugin's
`hermes_nerve/profiles.py` (`modules = dict(PROFILES[name])`). Settings are only read afterwards, and that
pass can turn modules **off**, never on (`legacy`/`custom` is the only branch that derives modules from
flags). So writing `context_engine_mode: apply` or `gate_mode: advisory` under a profile without
`context_governor` / `action_gate` is written-and-never-read: the layer is off with nothing visibly broken.

v0.3.1 module sets:

- `operator`: reflex, nervous, **action_gate**, **context_governor**, receipts, **local_learning**
- `lean`: reflex, nervous, work_supervision, token_trajectory, receipts
- `marie_kondo`: reflex, work_supervision, token_trajectory, receipts

Rule table the build enforces: `gate_mode` != `off` → `action_gate`; `context_engine_mode` /
`context_curation_mode` not `shadow|off` → `context_governor`; `work_supervision_mode` != `shadow` →
`work_supervision`; `nervous_enabled` → `nervous`. A mode of `shadow`/`off` asks nothing, so it must not
demand its module — that is what lets one settings block serve several profiles.

## Comparing to the host (do this before changing the image's layer)

Read the live host rather than a doc:

```bash
grep -A20 '^  entries:' ~/.hermes/config.yaml                  # plugins.entries.nerve.settings.* = host values
cat ~/.hermes/nerve/profile.json                               # sidecar: which profile decides the module set
head -5 ~/.hermes/plugins/nerve/plugin.yaml                     # installed plugin version
sed -n '1,40p' ~/.hermes/plugins/nerve/hermes_nerve/profiles.py  # the real PROFILES tables
```

The host carries the profile in BOTH places (the `nerve_profile` setting and the sidecar) and pins
`allow_tool_override: false`; the image should mirror it key for key, including `gate_scope: all`.

## Build pitfalls

- **`--yes-deps` kills the build.** Hermes then takes a *universal* `uv lock`; the plugin's optional `laya`
  extra pulls `torch`, which has no wheels for `python_full_version >= '3.14'` / android, so the lock has no
  solution and the plugin is never admitted. Install with `--no-deps`, remove that one extra from the
  INSTALLED `pyproject.toml`, then `hermes plugins enable nerve`; ASSERT the extra was still there, so a pin
  that drops it fails loudly instead of resolving extras blind.
- **Never put the provider key in the build env.** The install script refuses a build that carries
  `TYPESAFE_API_KEY` / any provider key; the key travels at run time (`docker run -e …`) and the preflight
  writes it into `$HERMES_HOME/.env` (mode 600, never printed).
- **YAML 1.1 reads a bare `off` as boolean false**, and the plugin tests `gate_mode != "off"`, so a bare
  write turns the action gate ON. Write it quoted (`gate_mode: 'advisory'`) and normalise/verify the line.
- **A new script the build runs is a hash input.** Add it to `IMAGES["agent"]` in `scripts/ci_images.py` and
  `COPY` it in the Dockerfile, or "the image of this commit" silently is not.
- **An absolute path inside the build is wrong in tests.** Resolve helper scripts relative to the running
  script (`"$(dirname "$0")/x.py"`) so the same file works at `/usr/local/bin/` in the image and in
  `scripts/` under `make test-unit`.
- **The parser for `IMAGES` is textual.** Keep inline comments OUT of the `IMAGES["agent"]` tuple — a comment
  between two string literals breaks the test that derives the hash inputs from the source.
- **The plugin stand-in must carry `PROFILES`.** `tests/fixtures/fake-nerve-plugin/hermes_nerve/profiles.py` is
  the dependency stand-in the build tests import; when the real plugin surface grows (e.g. the module table
  the parity check reads), extend the fixture — standing in for an external package is not mocking the code
  under test.

## Not solvable by configuration

`local_learning` state dies with a `--rm` bot container; durable learning needs a mounted state directory —
its own change, with its own evidence, not a settings tweak.
