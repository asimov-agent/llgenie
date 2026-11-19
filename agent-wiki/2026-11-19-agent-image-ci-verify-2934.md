# Agent image CI verify — the publish lane runs the image it published (#2934)

## What was verified against the spec

OpenSpec change `agent-image-ci-verify` (specs/agent-image-ci). All three ADDED requirements are
implemented and locally green:

- **Profile-presence seam**: `scripts/agent_image_profiles_check.py` + `make agent-image-profiles-check`
  — a standard agent leg (env guard, `scrubbed_run`, `AGENT_SHELL_FORWARD`, `AGENT_BOT_MARKER`,
  `ensure agent` first) boots the image and runs the seam INSIDE it, testing per
  `agents/manifest.json` lane (all 13, incl. `llgenie-status-keeper`) that
  `$HERMES_HOME/profiles/<lane>/config.yaml` exists in the image's own filesystem.
  Verdict lines `OK/MISSING <lane>`; any MISSING exits 1 naming it.
- **Prompt smoke in the build lane**: `publish-agent-image.yml` now runs `make agent-image-profiles-check`
  and then `make hermes-smoke` (env `NOUS_API_KEY: secrets.NOUS_PORTAL_API_TOKEN`) AFTER
  `make publish-agent-image` and before the lane can exit green. The smoke call carries no `-m`/alias
  flag: the model chain is the profile's own `config.yaml` (post-#2929 rule).
- **Makefile-only wiring**: both verification commands are Makefile targets; the workflow carries no
  raw `docker run` or `python3 scripts/...` for them. `make check-wiring`, `make check-package-layers`,
  `make check-workflows` green locally.

## Key decisions

- Verification sits in the SAME publish job, after the push: the check and smoke both `ensure agent`,
  which pulls the `:latest` the publish step just moved onto the new content hash — so what is verified
  is exactly what was published (a re-pull also proves the push landed).
- `hermes-smoke` was already host-capable but wired into no CI job (grep: 0 hits across workflows);
  the measured failure that motivated this lane: published `agent:latest` id `ea98772a4319` answered
  `Profile 'llgenie-status-keeper' does not exist`.
- Registration seams touched: `scripts/package-layers.json` (group "Bots and automation"),
  `tests/test_makefile_agents_mk_split.py` (MOVED roster), `Makefile` user-facing roster, docs
  (`docs/BOTS.md`), tests `tests/test_agent_image_profiles_check.py` (7 tests, stubbed subprocess
  boundary — the docker command construction is asserted, not just the verdict).
- Out of scope stays its own issue: the owner dispatch of the lane + published-tag verification is
  #2935 (links back to #2934); the Hermes 0.23.2 pin itself landed via #2932/#2933.

## Current status

Implementation + tests green on `feat/agent-image-ci-verify`; local dry-run against a freshly built
chain-configured agent image recorded below in this entry's follow-up (issue #2934 AC3). PR carries
`closes #2934`; the lane itself can only run green when the owner dispatches it (#2935).
