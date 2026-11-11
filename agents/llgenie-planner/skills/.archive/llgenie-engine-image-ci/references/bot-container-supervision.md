# The bot container: nerve/JEV supervision, and how to verify it on the host

Moved out of SKILL.md (which hit its 100k character ceiling). Covers the agent image's Hermes
plugins (nerve, JEV) and how to confirm the container sees them.


The agent image (`containers/agent/Dockerfile`) runs the bots' Hermes CLI, so anything the host's
Hermes has that the image lacks is a gap the bot silently works around. Wiring the nerve plugin
(issue #238) produced four reusable lessons:

- **Pin the plugin to a 40-char SHA**: `hermes plugins install <owner/repo> --ref <sha>
  --yes-deps --enable` is the CI-safe form (`--yes-deps` answers the dependency prompt, `--enable`
  skips the confirmation). A tag or branch is refused with a message saying so, because the image's
  hash tag claims what is inside it.
- **`hermes config set` resolves the value as YAML**, so `hermes config set ... gate_mode off`
  stores the BOOLEAN `false` — and the plugin's own rule is `gate_mode != "off"` → it turns the
  Action Gate **ON**. Any value that is a YAML 1.1 boolean word (`off`, `on`, `yes`, `no`, `true`,
  `false`) must end up QUOTED in `config.yaml`; the host's config quotes it for exactly this reason.
  Normalise the single line and assert the read-back (`hermes config get ... == off`, a string).
- **Check plugin state through `hermes plugins list --json`**, never by grepping the Rich table:
  the columns depend on the terminal width, and `hermes plugins list | grep -q nerve` under
  `set -o pipefail` reports FAILURE even on a match — `grep -q` exits on the first hit, the writer
  dies of SIGPIPE, and pipefail propagates it. The JSON also carries `source: git pinned@<sha8>`,
  which lets the build assert the pin that landed.
- **Verify the image halves on the dev host, cheaply**: the published agent image is already local,
  so mount the scripts and run them inside it instead of rebuilding —
  `docker run --rm -v "$PWD/scripts:/scripts:ro" llgenie/agent:latest bash -lc 'install -m755
  /scripts/<x>.sh /usr/local/bin/ && /usr/local/bin/<x>.sh'`. A `:ro` bind mount cannot be
  `chmod`ed ("Read-only file system") — `install -m755` into the container instead. Do the
  key-less and key-present runs in ONE container: the build half REFUSES to run with a provider key
  in its environment (that is the point), so run it as `env -u TYPESAFE_API_KEY /usr/local/bin/
  install_nerve_ci.sh`, then the run-time gate with the key present. Pass the key as `-e VAR`
  (docker copies it from docker's own env) so the value never appears on the command line.
- **`ENV` that must be a build-time override needs a matching `ARG` declared.** Putting
  `ENV HERMES_NERVE_PROFILE=${HERMES_NERVE_PROFILE}` in the Dockerfile without a preceding
  `ARG HERMES_NERVE_PROFILE=` makes the build print `UndefinedVar: Usage of undefined variable` and
  the image keeps a stale value — a fix that appears to set the env but never takes. Declare the
  `ARG` with the host's default next to the other nerve args.

- **A bot gate belongs inside the image and inside the make target** (`_implement-issue` runs
  `make _agent-nerve-gate` before `hermes -z`; `fix-loop-image` runs the script before
  `scripts/fix_loop.sh`), never as a second workflow step — the workflow guard requires one
  `make ci-*`/bot target per job, and a gate in the workflow can be skipped by the next caller.

- **JEV is a PRECONDITION for bot runs, and the preflight has two modes.** The bot workflows ARM the
  gate — `make agent-jev-preflight NERVE_REQUIRE=1` in a "Prove the JEV engine is active" step — so
  a bot run does not start with the JEV engine off (a non-zero exit before any model call is spent).
  The default mode stays REPORT-and-CONTINUE for a manual/local invocation (JEV unavailable = a
  slightly more expensive run, not a stopped one). A maintainer can must be told which: the header
  comment, README and test docstrings must name BOTH modes. When the contract flips from advisory to
  required, SWEEP header comments, README and test docstrings for the now-false claim (e.g. "no bot
  workflow sets it") and correct all of them in the SAME commit — a file that contradicts the
  pipeline misleads the next maintainer and the understated gate is the failure shape.

- **A status signal must not overstate what it verified.** The preflight's final annotation must
  report the offline path truthfully: when the provider was skipped / not contacted
  (`NERVE_GATE_SKIP_PROVIDER=1`), say "JEV is configured … the provider was NOT contacted", and
  reserve "answered a real decision call" for a live call that actually succeeded. A signal that
  claims a live call when none happened is worse than no signal — pin BOTH exact strings with a test
  covering the offline and the online path, and make the online path really run the provider by
  dropping the skip var in the same test.

- **After a parallel session edited `main` during your merge window, re-grep your test anchors before
  inserting.** When you open a fresh worktree off the new `main` for a follow-up fix, a test (or
  symbol) you remember from your now-merged PR may have been renamed or reshaped by the maintainer
  or another agent while it merged. Grep the CURRENT file for the anchor symbol before placing a new
  test before/after it, and assert on the actual symbol, not your memory — a stale anchor silently
  fails the insert and you re-derive the whole shape unnecessarily.

- **Changing `ci_images.py`'s `IMAGES[...]` inputs breaks `tests/test_ci_images.py`.** Its fixtures
  seed exactly the files the image hashes, and `ci_images.tag()` reads them by path, so a new
  script in the tuple makes those tests fail with `FileNotFoundError` inside `pytest-of-*/scripts/`
  (measured: adding two scripts to `IMAGES["agent"]` failed two tests in `linux / unit`). Seed them
  from the registry (`*ci_images.IMAGES["agent"][1]`) rather than a literal list, and keep the
  build-context assertion `{"Dockerfile"} | {names of that tuple}` — the context always carries the
  Dockerfile itself. Reproduce any `unit` failure in the test image before pushing:
  `docker run --rm -v "$PWD":/repo:ro -w /repo llgenie/test:latest python -m pytest <files> -q -p
  no:cacheprovider --noconftest` — 2 seconds there beats a 20-minute CI round trip.
