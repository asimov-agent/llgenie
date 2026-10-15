# agent-nerve-jev — proposal

Issue: [#238](https://github.com/asimov-agent/llgenie/issues/238)

## Why

The bots implement and repair with the Hermes CLI inside the agent image
(`containers/agent/Dockerfile`), and the **host** runs Hermes with the Nerve plugin enabled. That
plugin's JEV layer answers the cheap decisions — which step next, is this edit the right one, does
this satisfy the check, is the turn even worth starting — so the expensive model calls are spent only
where they are needed. Wired into the bots the trade is **more JEV calls, fewer LLM calls**: fewer
tokens, better accuracy, and a faster run, with context curation keeping the prompt to the part of the
repo that matters.

A container that only ran `install.sh` got the CLI and **no plugin**, so the bots ran without that
layer and left no JEV telemetry — and the engine-gap work (#229 / #234) hands per-engine issues to
exactly this bot.

The second mistake to avoid is subtler: **the bots are autonomous**, so the layer must never become a
precondition for their work. An unavailable decision layer is a reason to run a slightly more
expensive agent, not a reason to stop a bot.

The reverse mistake is worse than the gap: baking the provider key into the image leaks it to anyone
who can pull the image. The key travels exactly like `NOUS_API_KEY` — a CI secret, `docker run -e`,
never a layer.

## What Changes

- **`scripts/install_nerve_ci.sh`** (build half): installs the plugin at an **immutable** commit,
  then wires it **the way the host is wired, per the plugin's own `docs/SETUP.md`** (v0.3.1):
  - the **nervous-system block** under `plugins.entries.nerve.settings` — `nervous_enabled`,
    `nervous_turn_admission`, `nervous_mode: correct_next`, `nervous_challenge_confidence: 0.86`,
    `nervous_call_threshold: 0.58`;
  - the provider (`jev_provider: typesafe`, `typesafe_model: jev-latest`);
  - `context_engine_mode`/`context_curation_mode: apply` (the schema default is `shadow`, which only
    measures) and `work_supervision_mode: advisory` (steers without blocking);
  - `gate_mode: off` — SETUP.md calls the old synchronous pre-tool gate compatibility behaviour, not
    the recommended decision architecture;
  - the **profile sidecar** `${HERMES_HOME}/nerve/profile.json` = the host's `lean`, written through
    the plugin's own `save_profile` (validated, atomic). Without a sidecar the plugin falls back to
    Legacy registration and the settings above would tune modules nobody enabled;
  - removal of the dead pre-0.3.1 `plugins.entries.hermes-nerve` block if a base image carries it.
  The build fails on a mutable ref, a provider key in the build environment, a bundle that did not
  land, a plugin that is not enabled, a profile the plugin does not know, or a setting that did not
  land where Hermes reads it.
- **`scripts/agent_jev_preflight.sh`** (run half): reports whether the layer is available for THIS
  run — plugin bundle in this `HERMES_HOME`, key present (env or the home's `.env`, written back to
  it mode 600 because Hermes resolves credentials per home), plugin *enabled*, provider answering a
  **real** decision call through the plugin's own live smoke. **Every failure is reported and the run
  CONTINUES (exit 0).** `NERVE_REQUIRE=1` turns the report into a failure and exists to verify the
  image; no bot workflow sets it, and the old `ALLOW_UNSUPERVISED` opt-out is gone (there is nothing
  left to opt out of).
- **`containers/agent/Dockerfile`**: build args for the pin/provider/profile/supervision mode,
  explicit `HERMES_HOME`, the two scripts COPYed and run, and the layer asserted at build time.
- **`scripts/ci_images.py`**: both scripts are hash inputs of the agent image, so changing either
  moves the tag a job resolves.
- **Makefile**: `agent-jev-preflight` (public) + `_agent-jev-preflight` (internal), run by
  `_implement-issue` and `fix-loop-image` before any agent work, `-e TYPESAFE_API_KEY` on every bot
  target, `.PHONY`, help text, and the new test file in `make test-unit`.
- **`.github/workflows/issue-bot.yml` / `fix-bot.yml`**: `TYPESAFE_API_KEY` from the repo secret as
  run-time env, and a preflight step of the implementer before it spends model time, named for what
  it does ("Check the JEV layer is available (never blocks the run)").
- **`tests/test_agent_nerve.py`**: real subprocesses, no mocks of the scripts; the plugin package
  itself is stood in for by `tests/fixtures/fake-nerve-plugin/hermes_nerve/profiles.py` (a third-party
  dependency cannot be vendored; the stand-in reproduces the real module's documented contract, and
  the real loader is exercised inside the built image).
- **README**: the "JEV decision layer in the container" section.

## Decisions recorded

- **The layer never blocks a run.** The first cut of the run half made a missing key fatal ("a bot
  that cannot be supervised must not run"); that is the wrong contract for an autonomous bot. The
  maintainer's requirement: the bots work on their own, and JEV is what makes that work cheaper and
  more accurate — not a gate that can stop it.
- **`work_supervision_mode: advisory`** (the host's value): steers without blocking; `enforce` stays
  a build arg.
- **Profile `lean`, the host's** (`HERMES_NERVE_PROFILE` overrides it). `operator` would add the
  context governor and the action gate; the host chose lean, and mirroring the host is the point.

## Out of scope

- Changes to the plugin itself (`keeltrace/hermes-nerve`).
- The auto-fix bot's own logic (#222) — this is what makes its runs cheaper.
- The Kanban worker supervision path: these bots are headless command runs, not Kanban cards.
