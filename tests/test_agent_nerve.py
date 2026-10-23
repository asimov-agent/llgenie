"""The agent image carries the JEV decision layer, and the bots stay autonomous (issue #238).

The host runs Hermes with the Nerve plugin enabled, whose JEV/TypeSafe provider is a decision
layer: it answers "is this the right next step" before the model spends a call on it, and the
curated context sends the model the part of the repo that matters. Wired into the agent image
that means **fewer LLM calls and fewer mistakes** per issue the bots implement or repair — not a
smaller cage. `containers/agent/Dockerfile` is where the host's Hermes CLI lives, so the bots
run the same layer the host does; the provider key travels at run time only, because a key in a
layer is a leak.

THE RULE THESE TESTS PIN: the bots are autonomous, so the integration may never stop a run. A
missing key, a plugin that is not installed, a provider that does not answer — each is reported
LOUDLY and the run continues, because the answer is a normal (slightly more expensive, slightly
more mistake-prone) agent run, not a stopped bot. The bot workflows arm `NERVE_REQUIRE=1`,
which turns the report into a
failure and exists to verify the IMAGE; no bot workflow sets it.

These tests run the REAL scripts as subprocesses against real files: `scripts/install_nerve_ci.sh`
(the build half — must refuse a build that carries a key, and must pin an immutable commit) and
`scripts/agent_jev_preflight.sh` (the run half — must report and never block). Nothing here mocks
the product: the scripts are executed, and the wiring assertions read the same files the pipeline
reads.

The image-level half (the plugin actually loading inside a built image, and the provider
answering a live decision call) is the build's own assertion — `containers/agent/Dockerfile`
runs the install script and greps `hermes plugins list`, and `make agent-jev-preflight` runs the
preflight in the image against the live provider. Neither can run on a host without a built image
and the provider secret, which is exactly why they are asserted at build/run time and not here.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import unit_tests as ut  # noqa: E402  (the unit-suite aggregator, issue #393)
INSTALL = REPO / "scripts" / "install_nerve_ci.sh"
PREFLIGHT = REPO / "scripts" / "agent_jev_preflight.sh"
DOCKERFILE = REPO / "containers" / "agent" / "Dockerfile"
MAKEFILE = REPO / "Makefile"
CI_IMAGES = REPO / "scripts" / "ci_images.py"
WORKFLOWS = REPO / ".github" / "workflows"

# The key the plugin's TypeSafe (JEV) client reads; the shape a leaked key would have in a
# baked layer. Both are asserted against, never written anywhere.
KEY_VAR = "TYPESAFE_API_KEY"
LEAKED_KEY = re.compile(r"(?:hf_|sk-|sk_|jev-)[A-Za-z0-9]{16,}")


def _run(script: Path, env: dict, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a real script with a REAL environment (no stand-in for the thing under test)."""
    base = {"PATH": os.environ["PATH"], "HOME": env.get("HOME", "/tmp")}
    return subprocess.run(["bash", str(script)], env={**base, **env},
                          capture_output=True, text=True, timeout=timeout, cwd=REPO)


#: The stand-in for the third-party package, so the install script can write the profile sidecar
#: through a loader with the real module's contract (see the fixture's own docstring).
PLUGIN_FIXTURE = REPO / "tests" / "fixtures" / "fake-nerve-plugin"


def _home(tmp_path: Path, plugin: bool = True, package: bool = True) -> Path:
    """A real HERMES_HOME.

    `plugin` puts `plugin.yaml` in the bundle (installed); `package` puts the plugin's importable
    `hermes_nerve/` tree there, which the REAL `hermes plugins install` clones and the stand-in
    CLI cannot — the install script imports that tree to write the profile sidecar.
    """
    home = tmp_path / "hermes-home"
    (home / "plugins").mkdir(parents=True, exist_ok=True)
    if plugin or package:
        bundle = home / "plugins" / "nerve"
        bundle.mkdir(parents=True, exist_ok=True)
        if plugin:
            (bundle / "plugin.yaml").write_text('name: nerve\nversion: "0.3.1"\n')
        if package:
            shutil.copytree(PLUGIN_FIXTURE / "hermes_nerve", bundle / "hermes_nerve",
                            dirs_exist_ok=True)
    return home


# ---------------------------------------------------------------------------
# the build half: install_nerve_ci.sh
# ---------------------------------------------------------------------------
def test_the_build_refuses_a_provider_key_in_the_build_environment(tmp_path):
    """A key in the build environment lands in an image layer: the build must refuse it."""

    # Given a build environment that carries the provider key
    r = _run(INSTALL, {KEY_VAR: "jev-notarealkey-0123456789abcdef", "HERMES_HOME": str(_home(tmp_path))})

    # When the install script runs
    # Then it fails loudly, naming the variable and the reason (before any install work)
    assert r.returncode != 0, r.stdout
    assert f"{KEY_VAR} is set in the BUILD environment" in r.stderr
    assert "never in an image layer" in r.stderr


def test_the_build_requires_an_immutable_commit_pin(tmp_path):
    """A tag or branch would make the image's hash tag lie about what is inside it."""

    # Given a ref that is a tag, not a 40-character commit SHA
    r = _run(INSTALL, {"HERMES_NERVE_REF": "v0.3.1", "HERMES_HOME": str(_home(tmp_path))})

    # When the install script runs
    # Then it refuses, and says why
    assert r.returncode != 0, r.stdout
    assert "40-character commit SHA" in r.stderr
    assert "would not pin the image" in r.stderr


def test_the_build_pins_the_release_commit_and_the_hosts_settings():
    """The image's nerve pin and settings are the host's, and they are visible in the repo."""

    # Given the build script and the Dockerfile that runs it
    install = INSTALL.read_text()
    dockerfile = DOCKERFILE.read_text()

    # When the pin and the settings are read
    # Then the pin is an immutable SHA of the traced repo, with the tag it came from recorded
    m = re.search(r'HERMES_NERVE_REF:-([0-9a-f]{40})', install)
    assert m, "the install script must default NERVE_REF to a 40-character commit SHA"
    assert "keeltrace/hermes-nerve" in install and "v0.3.1" in install, (
        "the pin must name the repo and the release the SHA is taken from"
    )
    assert m.group(1) in dockerfile, "the Dockerfile must carry the same pin the install script defaults to"

    # And the settings are the host's, written where Hermes actually reads them
    for key, value in (("jev_provider", "typesafe"), ("typesafe_model", "jev-latest"),
                       ("nervous_enabled", "true"), ("nervous_mode", "correct_next"),
                       ("gate_mode", "off"), ("gate_scope", "all"),
                       ("context_engine_mode", "apply"), ("context_curation_mode", "apply"),
                       ("context_engine_register", "true"),
                       ("work_supervision_mode", "advisory")):
        assert f"set_setting {key} " in install, f"{key} is not wired by the install script"
    assert "plugins.entries.nerve.settings." in install, (
        "settings must go under plugins.entries.<id>.settings: a value one level up is ignored"
    )
    assert value and "work_supervision_mode" in install

    # And the build proves the layer instead of assuming it
    assert "hermes plugins list | grep -q 'nerve'" in dockerfile
    assert "plugins/nerve/plugin.yaml" in dockerfile


def _with_fake_hermes(tmp_path: Path, **extra: str) -> dict:
    """A PATH with a `hermes` that answers like the real CLI, plus the extra env.

    The scripts under test run for real; only the CLI is a stand-in, and it is a faithful one:
    it stores `config set` values with YAML 1.1 scalar resolution (a bare `off` becomes the
    boolean false — the trap the gate-mode normalisation exists for).
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "hermes"
    stub.write_text((REPO / "tests" / "fixtures" / "fake-hermes" / "hermes").read_text())
    stub.chmod(0o755)
    return {"PATH": f"{bin_dir}:{os.environ['PATH']}", **extra}


def test_the_build_wires_the_hosts_settings_and_keeps_gate_mode_a_string(tmp_path):
    """The settings land where Hermes reads them — and `off` stays the string, not YAML false."""

    # Given a home and a CLI that behaves like the real one
    home = _home(tmp_path, plugin=False)
    r = _run(INSTALL, {**_with_fake_hermes(tmp_path), "HERMES_HOME": str(home)})

    # When the build half runs end to end
    # Then it succeeds
    assert r.returncode == 0, r.stderr + r.stdout

    # And the config carries the host's settings under the path Hermes reads
    cfg = (home / "config.yaml").read_text()
    for line in ("jev_provider: typesafe", "typesafe_model: jev-latest", "nervous_enabled: true",
                 "nervous_mode: correct_next", "gate_scope: all", "work_supervision_mode: advisory"):
        assert line in cfg, f"{line!r} is missing from the config the build wrote"
    assert "  - nerve" in cfg, "the plugin is not in plugins.enabled"

    # And gate_mode is the QUOTED STRING: a bare `off` is a YAML 1.1 boolean, and the plugin
    # reads `gate_mode != "off"` as "turn the Action Gate ON"
    assert "gate_mode: 'off'" in cfg, cfg
    assert "gate_mode: false" not in cfg, "the Action Gate would be ON: YAML read `off` as boolean false"

    # And the build reported the layer it verified
    assert "installed and enabled" in r.stdout


def test_the_build_selects_the_hosts_profile_through_the_plugins_own_loader(tmp_path):
    """The settings only tune modules a PROFILE registered, so the sidecar is part of the setup.

    The host runs `lean` (its `$HERMES_HOME/nerve/profile.json`), and the plugin's own loader is
    what the install script writes through — an invented document would be rejected at load time
    and the plugin would fail open to Legacy with only a log warning.
    """

    # Given a home and a CLI that behave like the real ones
    home = _home(tmp_path, plugin=False)
    r = _run(INSTALL, {**_with_fake_hermes(tmp_path), "HERMES_HOME": str(home)})

    # When the build half runs
    # Then it succeeds and reports the profile it selected
    assert r.returncode == 0, r.stderr + r.stdout
    assert "nerve profile 'lean' selected" in r.stdout

    # And the sidecar is at the documented path, in the plugin's own shape
    sidecar = home / "nerve" / "profile.json"
    assert sidecar.exists(), "the profile sidecar was not written"
    doc = json.loads(sidecar.read_text())
    assert doc["version"] == 1 and doc["nerve_profile"] == "lean"
    assert doc["nerve_modules"] == {} and doc["advanced"] == {}

    # And the plugin's loader reports the same thing (the check the script itself makes)
    sys.path.insert(0, str(home / "plugins" / "nerve"))
    try:
        import hermes_nerve.profiles as profiles
        assert profiles.load_profile(str(home))["nerve_profile"] == "lean"
    finally:
        sys.path.pop(0)


def test_the_build_refuses_a_profile_the_plugin_does_not_know(tmp_path):
    """A typo would silently select nothing, so the build names the profiles it accepts."""

    # Given a profile name that is not in the plugin's table
    home = _home(tmp_path, plugin=False)
    r = _run(INSTALL, {**_with_fake_hermes(tmp_path), "HERMES_HOME": str(home),
                       "HERMES_NERVE_PROFILE": "legendary"})

    # When the build half runs
    # Then it fails, naming the profile and the accepted set
    assert r.returncode != 0, r.stdout
    assert "unknown nerve profile 'legendary'" in r.stderr
    assert "lean" in r.stderr


def test_the_build_sets_the_documented_nervous_defaults(tmp_path):
    """The documented decision architecture is the nervous block, not the old pre-tool gate."""

    # Given a home and a CLI that behave like the real ones
    home = _home(tmp_path, plugin=False)
    r = _run(INSTALL, {**_with_fake_hermes(tmp_path), "HERMES_HOME": str(home)})

    # When the build half runs
    # Then the config carries the documented block (SETUP.md "Nervous system defaults")
    assert r.returncode == 0, r.stderr + r.stdout
    cfg = (home / "config.yaml").read_text()
    for line in ("nervous_enabled: true", "nervous_turn_admission: true",
                 "nervous_mode: correct_next", "nervous_challenge_confidence: 0.86",
                 "nervous_call_threshold: 0.58", "context_engine_mode: apply",
                 "context_curation_mode: apply"):
        assert line in cfg, f"{line!r} is missing from the config the build wrote"

    # And the script's own read-back covers every one of them, so a silent miss cannot pass
    script = INSTALL.read_text()
    for key in ("nervous_enabled", "nervous_turn_admission", "nervous_mode",
                "nervous_challenge_confidence", "nervous_call_threshold",
                "context_engine_mode", "context_curation_mode", "gate_mode",
                "work_supervision_mode"):
        assert f'"{key} ' in script, f"{key} is written but never read back"


def test_the_build_removes_the_dead_pre_0_3_1_settings_block(tmp_path):
    """`plugins.entries.hermes-nerve` is never read by Hermes, and nerve warns about it."""

    # Given a home whose config still carries the pre-0.3.1 block
    home = _home(tmp_path, plugin=False)
    (home / "plugins" / "nerve").mkdir(parents=True, exist_ok=True)
    env = _with_fake_hermes(tmp_path, HERMES_HOME=str(home))
    subprocess.run(["bash", "-c", 'mkdir -p "$HERMES_HOME" && '
                    'printf "plugins:\n  entries:\n    hermes-nerve:\n      settings:\n'
                    '        reflex_backend: laya\n" > "$HERMES_HOME/config.yaml"'],
                   env={**env, "HERMES_HOME": str(home)}, check=True)

    # When the build half runs
    r = _run(INSTALL, env)

    # Then it succeeded, said why it removed the block, and the block is gone
    assert r.returncode == 0, r.stderr + r.stdout
    assert "removed the dead plugins.entries.hermes-nerve block" in r.stdout
    assert "hermes-nerve" not in (home / "config.yaml").read_text()


def test_the_build_fails_when_the_installed_plugin_is_not_enabled(tmp_path):
    """Installed-but-disabled is the silent failure: the plugin is on disk, the run is not."""

    # Given a CLI that reports the plugin as disabled
    home = _home(tmp_path, plugin=False)
    r = _run(INSTALL, {**_with_fake_hermes(tmp_path, FAKE_HERMES_STATUS="disabled"),
                       "HERMES_HOME": str(home)})

    # When the build half runs
    # Then it fails, naming the status it saw
    assert r.returncode != 0, r.stdout
    assert "is not enabled in" in r.stderr


def test_the_build_fails_when_the_checkout_is_not_the_pinned_commit(tmp_path):
    """A pin the image hash claims but the plugin does not have would be a lie in the tag."""

    # Given a CLI whose installed bundle reports a different commit
    home = _home(tmp_path, plugin=False)
    r = _run(INSTALL, {**_with_fake_hermes(tmp_path, FAKE_HERMES_PIN="deadbeef"),
                       "HERMES_HOME": str(home)})

    # When the build half runs
    # Then it fails, naming the pin it expected
    assert r.returncode != 0, r.stdout
    assert "not the pinned commit 3de7d949" in r.stderr


# ---------------------------------------------------------------------------
# the run half: agent_jev_preflight.sh — it reports, it never blocks
# ---------------------------------------------------------------------------
def test_a_missing_provider_key_is_reported_and_the_run_continues(tmp_path):
    """The acceptance: JEV unavailable costs the run its decision layer, not its progress."""

    # Given a home with the plugin installed and NO provider key anywhere
    home = _home(tmp_path)
    r = _run(PREFLIGHT, {"HERMES_HOME": str(home), "NERVE_GATE_SKIP_PROVIDER": "1"})

    # When the preflight runs
    # Then the bot's run still proceeds (exit 0) ...
    assert r.returncode == 0, r.stderr

    # ... and it SAYS the layer is inactive, naming the secret and both ways to supply it
    assert f"{KEY_VAR} is not set" in r.stderr
    assert "JEV is INACTIVE for this run" in r.stderr
    assert "more LLM" in r.stderr and "mistakes" in r.stderr
    assert f"repo secret {KEY_VAR}" in r.stderr
    assert "continuing without JEV" in r.stdout

    # And it never printed a key (there was none to print)
    assert not LEAKED_KEY.search(r.stdout + r.stderr)


def test_nerve_require_turns_the_report_into_a_failure(tmp_path):
    """`NERVE_REQUIRE=1` is the strict mode (the bot workflows and an image check arm it):
    the same home exits non-zero on purpose."""

    # Given the same key-less home, and the verify-only flag
    home = _home(tmp_path)
    r = _run(PREFLIGHT, {"HERMES_HOME": str(home), "NERVE_GATE_SKIP_PROVIDER": "1",
                         "NERVE_REQUIRE": "1"})

    # When the preflight runs
    # Then it fails, and says the flag is why
    assert r.returncode != 0, r.stdout
    assert f"{KEY_VAR} is not set" in r.stderr
    assert "NERVE_REQUIRE=1" in r.stderr
    assert "the JEV layer is required here" in r.stderr


def test_a_home_without_the_plugin_is_reported_and_the_run_continues(tmp_path):
    """An image that lost the plugin is named, and the bot still does its work."""

    # Given a home with no plugin on disk
    home = _home(tmp_path, plugin=False)
    r = _run(PREFLIGHT, {"HERMES_HOME": str(home)})

    # When the preflight runs
    # Then it continues, naming the path it looked at and how the image is built
    assert r.returncode == 0, r.stderr
    assert "the nerve plugin is not installed in" in r.stderr
    assert "containers/agent/Dockerfile" in r.stderr
    assert "JEV is INACTIVE for this run" in r.stderr


def test_a_provider_that_does_not_answer_does_not_stop_the_run(tmp_path):
    """A provider outage is a reason to run without JEV, not a reason to stop working."""

    # Given a home whose plugin is enabled but whose live smoke fails
    home = _home(tmp_path)
    smoke = home / "plugins" / "nerve" / "scripts"
    smoke.mkdir(parents=True, exist_ok=True)
    (smoke / "live_api_smoke.py").write_text(
        "import sys\nprint('provider unreachable')\nsys.exit(1)\n")
    env = _with_fake_hermes(tmp_path, HERMES_HOME=str(home), FAKE_HERMES_STATUS="enabled",
                            **{KEY_VAR: "jev-realkey-0123456789abcdef"})

    # When the preflight runs against that provider
    r = _run(PREFLIGHT, env)

    # Then the run continues, with the provider's own message shown and the key redacted
    assert r.returncode == 0, r.stderr
    assert "provider unreachable" in r.stderr
    assert "did not answer a live decision call" in r.stderr
    assert not LEAKED_KEY.search(r.stdout + r.stderr), "the preflight must never echo the key"

    # And the verify-only mode is what turns exactly that into a failure
    r = _run(PREFLIGHT, {**env, "NERVE_REQUIRE": "1"})
    assert r.returncode != 0, r.stdout
    assert "the JEV layer is required here" in r.stderr


def test_every_bot_workflow_arms_the_gate_so_no_job_runs_unsupervised():
    """The maintainer's rule, asserted: JEV IS a precondition for a bot run. A job whose image has
    the engine turned off fails the preflight before it spends a model call - and no bot workflow
    carries an escape hatch."""

    for wf in ("issue-bot.yml", "fix-bot.yml"):
        text = (WORKFLOWS / wf).read_text()
        assert "NERVE_REQUIRE=1" in text, f"{wf} does not arm the gate: it would run unsupervised"
        assert "ALLOW_UNSUPERVISED" not in text, f"{wf} must not carry an escape hatch in CI"

def test_the_preflight_reads_an_existing_home_env_and_never_echoes_it(tmp_path):
    """The key may already live in the home (the host's layout); the preflight must find it."""

    # Given a home whose .env already carries the key, and a CLI that answers like the real one
    # in that home (the plugin is not enabled there)
    home = _home(tmp_path)
    (home / ".env").write_text(f'{KEY_VAR}="jev-from-home-env-0123456789abcdef"\n')
    env = _with_fake_hermes(tmp_path, HERMES_HOME=str(home), NERVE_GATE_SKIP_PROVIDER="1")

    # When the preflight runs offline (provider skipped) but the plugin is not enabled here
    r = _run(PREFLIGHT, env)

    # Then the key check passed (it did not report a missing key), the ENABLED check is what it
    # reported, and the run still continued
    assert f"{KEY_VAR} is not set" not in r.stderr, r.stderr
    assert "is 'disabled' in" in r.stderr, r.stderr
    assert r.returncode == 0, r.stderr
    assert not LEAKED_KEY.search(r.stdout + r.stderr), "the preflight must never echo the key"


def test_the_run_annotates_whether_jev_is_on_or_off(tmp_path):
    """A non-blocking layer must still be VISIBLE: the run says JEV is ON, or warns that it is off.

    The layer never stops a run, so "JEV was inactive" would otherwise only exist in a log nobody
    reads. In Actions the preflight annotates the run (`::notice` / `::warning`, which also reach
    the job summary) and writes the outcome to the step summary; locally it stays plain text.
    """

    # Given a key-less home and a home that has everything the layer needs
    home = _home(tmp_path)
    off = _run(PREFLIGHT, {"HERMES_HOME": str(home), "NERVE_GATE_SKIP_PROVIDER": "1",
                           "GITHUB_ACTIONS": "true"})

    # When the preflight reports in a workflow
    # Then the off case carries a GitHub warning, and still exits 0
    assert off.returncode == 0, off.stderr
    assert "::warning title=JEV decision layer::" in off.stdout + off.stderr
    assert "JEV is INACTIVE for this run" in off.stderr

    # And the same home, with a plugin that answers, carries a notice instead
    smoke = home / "plugins" / "nerve" / "scripts"
    smoke.mkdir(parents=True, exist_ok=True)
    (smoke / "live_api_smoke.py").write_text('print(\'{"ok": true}\')\n')
    on = _run(PREFLIGHT, _with_fake_hermes(tmp_path, HERMES_HOME=str(home),
                                          FAKE_HERMES_STATUS="enabled",
                                          GITHUB_ACTIONS="true",
                                          **{KEY_VAR: "jev-okkey-0123456789abcdef"}))
    assert on.returncode == 0, on.stderr
    assert "::notice title=JEV decision layer::" in on.stdout
    assert "JEV is ON for this run" in on.stdout

    # And outside Actions there is no annotation noise, only the plain lines
    plain = _run(PREFLIGHT, {"HERMES_HOME": str(home), "NERVE_GATE_SKIP_PROVIDER": "1"})
    assert "::warning" not in plain.stdout + plain.stderr
    assert "::notice" not in plain.stdout + plain.stderr

    # And the step summary is written when Actions offers one
    summary = tmp_path / "summary.md"
    _run(PREFLIGHT, {"HERMES_HOME": str(home), "NERVE_GATE_SKIP_PROVIDER": "1",
                     "GITHUB_ACTIONS": "true", "GITHUB_STEP_SUMMARY": str(summary)})
    assert "JEV decision layer" in summary.read_text()


def test_the_workflow_comments_describe_the_layer_it_actually_runs():
    """A comment that says "fails the run when the key is missing" is a lie about an autonomous bot."""

    for wf in ("issue-bot.yml", "fix-bot.yml"):
        text = (WORKFLOWS / wf).read_text()
        assert "fewer llm calls" in text.lower(), f"{wf} must say what the layer is for"
        assert "never stop" in text or "never stops" in text, f"{wf} must say it never blocks a run"
        for stale in ("fails the run when it is missing", "fails loudly instead of repairing",
                      "so the bot never implements an issue unsupervised"):
            assert stale not in text, f"{wf} still describes the old gate contract: {stale!r}"


def test_the_key_value_itself_never_reaches_stdout_or_stderr(tmp_path):
    """The literal value must never be printed — not on success, not in a home's `.env`, not when
    the provider misbehaves and echoes it back.

    The key-shaped regex the other tests use proves nothing about a real credential's value, so this
    test passes a distinctive one and greps the WHOLE output for that exact string.
    """
    secret = "jev-NEVER-PRINT-THIS-0123456789abcdef"

    # Given a home with a plugin whose smoke FAILS and PRINTS THE KEY (the worst case: a provider
    # that echoes the credential in its error text)
    home = _home(tmp_path)
    smoke = home / "plugins" / "nerve" / "scripts"
    smoke.mkdir(parents=True, exist_ok=True)
    (smoke / "live_api_smoke.py").write_text(
        "import os, sys\n"
        "print('auth failed for key ' + os.environ.get('TYPESAFE_API_KEY', ''))\n"
        "sys.exit(1)\n")

    # When the preflight runs with the key in the environment
    r = _run(PREFLIGHT, _with_fake_hermes(tmp_path, HERMES_HOME=str(home),
                                         FAKE_HERMES_STATUS="enabled", **{KEY_VAR: secret}))

    # Then the run continued, showed the provider's message, and the VALUE is nowhere in the output
    assert r.returncode == 0, r.stderr
    assert "auth failed" in r.stderr, "the provider's own message must still be visible"
    assert secret not in r.stdout + r.stderr, "the provider key leaked into the run log"
    assert "***REDACTED-KEY***" in r.stderr, "the leak was not reported as redacted"

    # And the same holds when the key already lives in the home's `.env` and the provider answers
    home2 = _home(tmp_path / "second")
    (home2 / ".env").write_text(f"{KEY_VAR}={secret}\n")
    smoke2 = home2 / "plugins" / "nerve" / "scripts"
    smoke2.mkdir(parents=True, exist_ok=True)
    (smoke2 / "live_api_smoke.py").write_text('print(\'{"ok": true}\')\n')
    r2 = _run(PREFLIGHT, _with_fake_hermes(tmp_path / "second", HERMES_HOME=str(home2),
                                          FAKE_HERMES_STATUS="enabled"))
    assert r2.returncode == 0, r2.stderr
    assert secret not in r2.stdout + r2.stderr, "the key from the home's .env leaked into the output"


def test_no_message_interpolates_the_key_value():
    """Static check on the source: no printing line expands the value — a future edit that echoes
    `$key` fails here. Reading it (`key="${key%...}"`) and writing it to the home's `.env` (a
    redirect to a file, mode 600) are fine; naming the VARIABLE in a message is fine; putting the
    VALUE into stdout/stderr is not.
    """
    text = PREFLIGHT.read_text()
    printing = re.compile(r"^(say|warn|echo|printf|annotate)\b")
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#") or not printing.match(stripped):
            continue
        if ">>" in stripped:
            continue          # a redirect to a FILE (the home's .env, mode 600) is not output
        assert not re.search(r"\$\{?key\b", stripped), f"line {n} prints the key value: {stripped}"

    # And the one place a third party prints is filtered through the redactor
    assert "| redact" in text, "the provider smoke's output must pass through the redactor"
    assert "never printed" in text


# ---------------------------------------------------------------------------
# the wiring: the key travels at run time, and the scripts move the image tag
# ---------------------------------------------------------------------------
def test_the_annotation_does_not_claim_a_call_that_was_skipped(tmp_path):
    """The ON/OFF signal must not overstate itself: the offline path says the provider was NOT
    contacted, because a maintainer reading "JEV is ON … answered a real decision call" would
    believe a live call happened."""
    home = _home(tmp_path)
    env = _with_fake_hermes(tmp_path, HERMES_HOME=str(home), FAKE_HERMES_STATUS="enabled",
                            GITHUB_ACTIONS="true", NERVE_GATE_SKIP_PROVIDER="1",
                            **{KEY_VAR: "jev-annot-0123456789abcdef"})
    r = _run(PREFLIGHT, env)
    assert r.returncode == 0, r.stderr
    assert "JEV is configured for this run" in r.stdout
    assert "the provider was NOT contacted" in r.stdout
    assert "answered a real decision call" not in r.stdout

    # And with the provider actually contacted, the notice says so
    smoke = home / "plugins" / "nerve" / "scripts"
    smoke.mkdir(parents=True, exist_ok=True)
    (smoke / "live_api_smoke.py").write_text('print(\'{"ok": true}\')\n')
    r2 = _run(PREFLIGHT, {**env, "NERVE_GATE_SKIP_PROVIDER": ""})
    assert r2.returncode == 0, r2.stderr
    assert "answered a real decision call" in r2.stdout


def test_the_docs_match_the_armed_contract():
    """The bot workflows ARM the gate now, so nothing may still claim "no bot workflow sets it"."""
    pre = PREFLIGHT.read_text()
    readme = (REPO / "README.md").read_text()
    assert "No bot workflow sets it." not in pre, "the preflight still denies the armed gate"
    assert "no bot workflow sets it" not in readme, "the README still denies the armed gate"
    assert "both bot workflows arm it" in readme
    assert "BOT WORKFLOWS ARM IT" in pre


def test_the_workflows_pass_the_key_at_run_time_only():
    """Every bot workflow hands the key to the container; none of them bakes it."""

    # Given the two bot workflows
    issue_bot = (WORKFLOWS / "issue-bot.yml").read_text()
    fix_bot = (WORKFLOWS / "fix-bot.yml").read_text()

    # When the key's presence is checked
    # Then both take it from the repo secret and pass it to the process env (docker run -e)
    for name, text in (("issue-bot.yml", issue_bot), ("fix-bot.yml", fix_bot)):
        assert f"{KEY_VAR}: ${{{{ secrets.{KEY_VAR} }}}}" in text, f"{name} does not wire the secret"

    # And the preflight is a real step of the implementer, before any agent work, named for what
    # it does (it reports; it does not gate)
    assert "run: make agent-jev-preflight NERVE_REQUIRE=1" in issue_bot
    assert "name: Prove the JEV engine is active" in issue_bot
    assert issue_bot.index("Prove the JEV engine is active") < issue_bot.index(
        "Implement the issue (Hermes reads issue.md"), (
        "the preflight step must come before the implementer spends model time"
    )

    # And no file in the image's build context mentions a key value
    for path in (DOCKERFILE, INSTALL, PREFLIGHT, REPO / "scripts" / "install_hermes_ci.sh"):
        assert not LEAKED_KEY.search(path.read_text()), f"{path.name} contains something key-shaped"
        assert f"ENV {KEY_VAR}=" not in path.read_text(), f"{path.name} writes the key into the image env"


def test_the_key_reaches_the_container_through_make_targets():
    """The make targets are the only path into the image, so they carry the `-e`."""

    # Given the Makefile
    mk = MAKEFILE.read_text()

    # When each bot target's docker run is read
    # Then each passes the provider key by NAME (never a value), and the preflight is reachable
    for target in ("agent-jev-preflight:", "implement-issue:", "hermes-smoke:"):
        block = mk.split(target, 1)[1].split("\n\n", 1)[0]
        assert f"-e {KEY_VAR}" in block, f"make {target} does not pass {KEY_VAR} into the container"

    # And the fix loop runs the preflight before it repairs anything
    fix_loop = mk.split("fix-loop-image:", 1)[1].split("\n\n", 1)[0]
    assert f"-e {KEY_VAR}" in fix_loop
    # The invariant is ORDER — the preflight runs before anything is repaired — not the exact
    # adjacency of two words in one shell line. Pinning the contiguous string made a legitimate
    # change (passing FIX_REPORT_FILE into the loop, issue #538) red both unit jobs on PR #539
    # while the preflight still ran first.
    assert "scripts/agent_jev_preflight.sh" in fix_loop
    assert fix_loop.index("scripts/agent_jev_preflight.sh") < fix_loop.index("scripts/fix_loop.sh")
    # ... and they are chained in ONE shell command, so the loop cannot run in a container the
    # preflight never touched (the report file is passed as an assignment on the loop's own command).
    shell_line = fix_loop.split("bash -lc '", 1)[1].split("';", 1)[0]
    assert "scripts/agent_jev_preflight.sh" in shell_line
    assert "scripts/fix_loop.sh" in shell_line

    # And the implementer's internal recipe reports first (the bot path cannot skip it)
    impl = mk.split("_implement-issue:", 1)[1].split("\n\n", 1)[0]
    assert "$(MAKE) _agent-jev-preflight" in impl
    assert impl.index("_agent-jev-preflight") < impl.index("hermes -z")

    # And the public target is a WORKING recipe: `ensure` + a docker run, not a stray flag line
    public = mk.split("\nagent-jev-preflight:", 1)[1].split("\n\n", 1)[0]
    assert "scripts/ci_images.py ensure agent" in public
    assert "$(RUNTIME) run" in public and "$(AGENT_IMAGE) bash -lc" in public


def test_a_changed_nerve_script_moves_the_agent_image_tag():
    """The image a bot uses is the image of THIS commit: every COPYed file is a hash input."""

    # Given the image registry that computes the agent tag
    src = CI_IMAGES.read_text()

    # When the agent image's inputs are read
    # Then every file the Dockerfile COPYs is one of them, or a change would not rebuild it
    inputs = src.split('"agent": (', 1)[1].split(")", 1)[0]
    for name in ("scripts/install_hermes_ci.sh", "scripts/install_nerve_ci.sh",
                 "scripts/agent_jev_preflight.sh"):
        assert name in inputs, f"{name} is COPYed by the Dockerfile but is not a hash input"
        assert (REPO / name).exists(), f"{name} does not exist"
        assert f"COPY {Path(name).name} " in DOCKERFILE.read_text(), f"{name} is not COPYed by the Dockerfile"

    # And nothing still points at the old gate name
    for path in (MAKEFILE, DOCKERFILE, CI_IMAGES, INSTALL, PREFLIGHT,
                 WORKFLOWS / "issue-bot.yml", WORKFLOWS / "fix-bot.yml"):
        assert "agent_nerve_gate" not in path.read_text(), f"{path.name} still names the old gate script"


def test_the_preflight_is_documented_for_the_reader():
    """`make help` and the README say what it is, and it is a declared phony target."""

    # Given the Makefile and the README
    mk = MAKEFILE.read_text()
    readme = (REPO / "README.md").read_text()

    # When the target's documentation is read
    # Then help and the README both carry it, and .PHONY declares it
    assert "make agent-jev-preflight" in mk.split("\nhelp:", 1)[1]
    assert "agent-jev-preflight" in mk.split(".PHONY:", 1)[1].split("\n\n", 1)[0]
    assert "agent-jev-preflight" in readme and KEY_VAR in readme

    # And the README says the layer is about cost and correctness, and that it never blocks
    assert "fewer LLM calls" in readme
    assert "never blocks" in readme or "never stops a run" in readme

    # And the test file itself is in the unit suite the aggregator computes (issue #393)
    assert "tests/test_agent_nerve.py" in ut.select(REPO)


def test_every_bot_workflow_arms_the_jev_gate():
    """The maintainer's rule: a bot job must NOT start when the JEV engine is off. Every workflow
    that runs the agent calls the preflight with NERVE_REQUIRE=1, so a turned-off engine fails the
    job before it spends a model call."""
    bots = ["issue-bot.yml", "fix-bot.yml"]
    for name in bots:
        text = (REPO / ".github" / "workflows" / name).read_text()
        assert "agent-jev-preflight" in text, f"{name} never checks the JEV engine"
        assert "NERVE_REQUIRE=1" in text, f"{name} checks it but does not ARM it (report only)"
    assert "never blocks the run" not in (REPO / ".github" / "workflows" / "issue-bot.yml").read_text(), \
        "the gate must not be described as advisory"


def test_an_unsupported_provider_is_refused_loudly(tmp_path):
    """Issue #311: the preflight advertised `openrouter` and `opencode` as supported providers and
    mapped each to a key the repo does not define. A provider the repo does not configure must be
    refused, naming the one it does."""

    # Given HERMES_NERVE_PROVIDER set to a provider the repo does not configure
    r = _run(PREFLIGHT, {"HERMES_HOME": str(_home(tmp_path)), "HERMES_NERVE_PROVIDER": "openrouter",
                         "NERVE_REQUIRE": "1"})

    # When the preflight runs
    # Then it exits non-zero ...
    assert r.returncode != 0, r.stdout

    # ... and its message names `typesafe` as the only supported provider
    assert "unsupported HERMES_NERVE_PROVIDER='openrouter'" in r.stderr, r.stderr
    assert "(typesafe)" in r.stderr, r.stderr

    # ... and it no longer advertises the removed providers
    assert "(typesafe | openrouter | opencode)" not in r.stderr, r.stderr


def test_the_typesafe_provider_selects_its_key(tmp_path):
    """Issue #311: the provider case mapped `typesafe` to TYPESAFE_API_KEY and two more providers to
    keys the repo does not define. The one provider the repo configures must select its own key."""

    # Given HERMES_NERVE_PROVIDER=typesafe and NO key in the environment or the home
    r = _run(PREFLIGHT, {"HERMES_HOME": str(_home(tmp_path)), "HERMES_NERVE_PROVIDER": "typesafe"})

    # When the preflight's provider case runs
    # Then the key variable it checks is TYPESAFE_API_KEY
    assert "TYPESAFE_API_KEY is not set" in r.stderr, r.stderr

    # ... and it never looks for a key the repo does not define
    assert "OPENROUTER_API_KEY" not in r.stdout + r.stderr
    assert "OPENCODE_API_KEY" not in r.stdout + r.stderr


def test_a_provider_key_in_the_build_environment_fails_the_build(tmp_path):
    """Issue #311: the build guard names the WHOLE provider-key namespace, so a future provider key
    is caught by the same guard even though the repo now configures only `typesafe`."""

    # Given a build environment carrying each provider key in turn
    for var in ("TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "OPENCODE_API_KEY"):
        r = _run(INSTALL, {"HERMES_NERVE_REF": "0" * 40, "HERMES_HOME": str(_home(tmp_path)),
                           var: "jev-notarealkey-0123456789abcdef"})

        # When the install script runs
        # Then the build fails loudly and names the offending variable
        assert r.returncode != 0, r.stdout
        assert f"{var} is set in the BUILD environment" in r.stderr, (var, r.stderr)

    # And the Dockerfile's own guard covers the same three names, so the layer is checked too
    guard = DOCKERFILE.read_text()
    assert "^(TYPESAFE|OPENROUTER|OPENCODE)_API_KEY=" in guard, \
        "the Dockerfile build guard must name the whole provider-key namespace"
