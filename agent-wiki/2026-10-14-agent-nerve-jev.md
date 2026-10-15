# The JEV decision layer inside the agent container (issue #238, PR #265)

## What this is for

The Nerve plugin's JEV layer answers the cheap decisions — which step next, is this edit the right
one, does this satisfy the check, is the turn even worth starting — so the expensive model calls are
spent only where they are needed. Wired into the bots that means **more JEV calls, fewer LLM calls**:
fewer tokens, better accuracy, and a faster run, with the context curation keeping the prompt to the
part of the repo that matters.

It is **not** a cage on the bots and not a substitute for the review a PR gets. **The bots are
autonomous, and nothing in this path may stop a run.** The first version of the run half got that
wrong (it refused to run without the provider key) and this is the rewrite.

## The gap

`containers/agent/Dockerfile` installed the Hermes CLI and nothing else, so the issue implementer and
the fix bot — the two places where an agent changes this repo without a human watching — ran without
the decision layer the host runs, and left no JEV telemetry behind.

## The two halves

- **Build** — `scripts/install_nerve_ci.sh` (called by the Dockerfile).
- **Run** — `scripts/agent_jev_preflight.sh`, reached through `make agent-jev-preflight` and run
  automatically by `_implement-issue` (before the model call) and `fix-loop-image` (before the loop).

## Wired the way the host is, per the plugin's own docs

The plugin is installed on this host, so the configuration was read out of its own source and docs
(`~/.hermes/plugins/nerve`, v0.3.1) plus the host's live `~/.hermes/config.yaml` and
`~/.hermes/nerve/profile.json` rather than invented:

| what | value | why |
|---|---|---|
| settings location | `plugins.entries.nerve.settings` | SETUP.md: a value one level up is **never read**. The old `plugins.entries.hermes-nerve` block is dead and nerve warns about it at startup — this PR removes it if a base image carries it |
| provider | `jev_provider: typesafe`, `typesafe_model: jev-latest` | the wire-tested direct TypeSafe path; the key arrives at run time only |
| nervous system | `nervous_enabled: true`, `nervous_turn_admission: true`, `nervous_mode: correct_next`, `nervous_challenge_confidence: 0.86`, `nervous_call_threshold: 0.58` | SETUP.md's "Nervous system defaults" block, verbatim — this is the recommendation, and where the JEV calls come from |
| pre-tool gate | `gate_mode: off` | SETUP.md: the old synchronous gate is "compatibility/special-purpose behavior, not the recommended v0.2 decision architecture". Off on purpose, not a downgrade |
| context | `context_engine_mode`/`context_curation_mode: apply` | `apply` is where prompt tokens are won; the schema default is `shadow`, which only measures |
| work supervision | `work_supervision_mode: advisory` | steers without blocking, which is what an autonomous bot needs; `enforce` stays a build arg |
| profile | sidecar `${HERMES_HOME}/nerve/profile.json` → **`lean`** | the host's profile (`nerve_profile: lean`, empty overrides). A named profile is what decides which modules register at all — reflex, nervous, work_supervision, token_trajectory, receipts — so without the sidecar the settings above would tune modules nobody enabled |

The sidecar is written through the plugin's **own** `save_profile` (imported from
`hermes_nerve.profiles` inside the image): the plugin validates the document strictly (version 1,
known profile name, known module ids) and writes it atomically, and a hand-rolled document would be
rejected at load time — after which the plugin **fails open to Legacy with only a log warning**, i.e.
the layer silently off.

## The run half reports, it does not gate

The old contract was "a bot that cannot be supervised must not run" — wrong for an autonomous bot.
Now: plugin missing, key missing, plugin not enabled, provider not answering → each is reported
loudly with the fix, and the run **continues** (exit 0), because the answer to "JEV is unavailable"
is a normal, slightly more expensive, slightly more mistake-prone agent run, not a stopped bot.
`NERVE_REQUIRE=1` turns any of those into a failure, and it exists to verify the **image**
(`make agent-jev-preflight NERVE_REQUIRE=1`). **No bot workflow sets it** — asserted by
`test_no_bot_workflow_requires_the_layer_or_opts_out_of_it`, alongside the removal of the old
`ALLOW_UNSUPERVISED` opt-out (there is nothing left to opt out of).

## What was verified, and how

`tests/test_agent_nerve.py` — real subprocesses, no mocks, real files:

- build half: refuses a provider key in the build environment, refuses a mutable ref, lands the
  documented settings (including `nervous_turn_admission`), keeps `gate_mode` the *string* `'off'`,
  selects the profile and verifies it through the plugin's loader, refuses a profile the plugin does
  not know, removes the dead pre-0.3.1 block, fails when the plugin is not enabled and when the
  installed pin is not the requested commit;
- run half: without the key it reports `JEV is INACTIVE for this run` and exits **0**; the same home
  with `NERVE_REQUIRE=1` exits 1; a home without the plugin and a provider that does not answer both
  continue with the reason and the remedy in the log; a key already in the home's `.env` is found and
  never echoed;
- wiring: the secret reaches the container at run time in both workflows, the `-e` is on every bot
  target, the preflight step is named for what it does and comes before the implementer's model call,
  both scripts are hash inputs of the image tag, and the public target is a working recipe.

In the real image (`llgenie/agent:latest`, real CLI): the plugin cloned and enabled at `3de7d949`
(`status=enabled source=git pinned@3de7d949 version=0.3.1`), every setting reading back from
`plugins.entries.nerve.settings`, the profile selected through the plugin's loader, the build-time key
refusal firing, and a **live provider decision call answered**
(`provider OK: a real decision call answered`) with the token never printed.

`make check-wiring`, `bash -n` on both scripts, `py_compile`, `lint_linefeeds`,
`check_openspec_tasks`, `make openspec-validate NAME=agent-nerve-jev` → valid.

## The three bugs this found while verifying (each is now a test)

1. **`gate_mode: off` landed as YAML boolean `false`.** The plugin decides
   `action_gate = (gate_mode != "off")`, so a bare `off` turned the Action Gate **ON** — silently.
   The host quotes it for exactly this reason; the install normalises that line to a quoted string
   and asserts the read-back.
2. **`hermes plugins list | grep -q nerve` failed right after the install.** Under `set -o pipefail`
   `grep -q` closes the pipe on first match, the writer dies of SIGPIPE, and the pipeline reports
   failure although the name matched. The check now parses `hermes plugins list --json`.
3. **The public `agent-nerve-gate` target had lost its `ensure` + `docker run` lines**, so it ran a
   stray `-e …` as a command. Caught while rewriting it; `test_the_key_reaches_the_container_through_make_targets`
   now asserts the public target is a working recipe (`ensure` + `$(RUNTIME) run` + the image).

## Left to the maintainer

1. **Add the repo secret `TYPESAFE_API_KEY`** (the value the host's `~/.hermes/.env` holds) — without
   it the bots still run, just without the decision layer (the preflight says so, loudly).
2. **Publish the new agent image** (`publish-agent-image.yml`, workflow_dispatch): the layer changed,
   so the hash tag moved and the bots resolve the new tag.
3. `work_supervision_mode` stays `advisory` unless you decide otherwise
   (`HERMES_NERVE_WORK_SUPERVISION_MODE=enforce` at build time).
4. `HERMES_NERVE_PROFILE` defaults to the host's `lean`; `operator` (adds the context governor and the
   action gate) or `fat_cat` are one build arg away if you want more of the layer in the bots.

Open as PR #265 (reviewable, never merged by the agent).
