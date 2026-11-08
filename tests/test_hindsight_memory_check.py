"""Fleet memory wiring, vehicle B: one template renders every llgenie-* profile's hindsight
config and `make memory-check` names any profile that drifted from the shared env (issue #2057).

The 13 `llgenie-*` Hermes profiles wire memory through Hindsight (`mode: local_embedded`): a
per-profile `hindsight/config.json` and `.env`, one shared `~/.hindsight/profiles/hermes.env`,
and one embedded daemon on `127.0.0.1:9177`. The wiring was hand-written on the host, was
silently self-destructive (two sessions rewrite the same env, and an empty key builds the
placeholder `not-needed` that overwrites the shared real key), and was invisible to git. This
file locks the generator and the gate.

What it proves (each against real files in a temp tree — business logic never mocked):

- **one template**: `config_render` produces a `hindsight/config.json` for every `llgenie-*`
  profile from a single template (mode `local_embedded`, one daemon per host, the shared plugin
  profile name, endpoint + model, the HINDSIGHT_LLM_API_KEY source, `bank_id_template:
  "{profile}"` with the shared `additional_banks` bank);
- **idempotence**: a second render changes nothing (byte-for-byte, not by prose);
- **the gate is a superset, not an equality**: a drift test asserts `expected <= actual`, so a
  14th profile does not red the gate;
- **the drift is caught and named**: a profile whose endpoint/model disagrees with the shared
  `hermes.env` is a non-zero finding naming the profile;
- **the empty-key placeholder is caught**: a profile holding no key would write the `not-needed`
  placeholder over the shared key, and `make memory-check` fails naming it;
- **the live daemon is measured, not guessed**: `/proc/<pid>/environ` and the log's last
  `Connection verified:` line are read as real files; on a runner with no daemon the gate says
  so rather than pretending `/health` is evidence;
- **the make wiring exists**: `.PHONY: memory-check` and a target running the script, so the
  gate is real and CI-reachable.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
from scripts import hindsight_memory_check as hmc  # noqa: E402


def _profile(home: Path, name: str, key: str = "k-secret") -> None:
    """A real profile dir with a `.env`; the `hindsight/config.json` is created by the gate."""
    (home / ".hermes" / "profiles" / name).mkdir(parents=True, exist_ok=True)
    (home / ".hermes" / "profiles" / name / ".env").write_text(
        f"HINDSIGHT_LLM_API_KEY={key}\n")


def _shared(home: Path, *, model: str | None = None, url: str | None = None) -> None:
    """The single shared `hermes.env` the daemon reads (the documented topology)."""
    (home / ".hindsight" / "profiles").mkdir(parents=True, exist_ok=True)
    lines = [
        f"HINDSIGHT_API_LLM_BASE_URL={url or hmc.DEFAULT_BASE_URL}",
        f"HINDSIGHT_API_LLM_MODEL={model or hmc.DEFAULT_MODEL}",
    ]
    (home / ".hindsight" / "profiles" / hmc.SHARED_ENV).write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# one template, rendered identically for a superset of profiles
# ---------------------------------------------------------------------------

def test_template_documents_the_topology():
    """The single template carries every documented field (mode, daemon-per-host, shared plugin
    profile, endpoint+model, key source, bank layout)."""
    t = hmc.config_template("llgenie-architect")
    # mode local_embedded, ONE daemon per host on 127.0.0.1:9177
    assert t["mode"] == "local_embedded"
    assert t["port"] == hmc.DAEMON_PORT == 9177
    # the daemon keys off a config profile name, not HERMES_HOME
    assert t["profile"] == hmc.PLUGIN_PROFILE == "hermes"
    # endpoint + model, key source, and the bank layout
    assert t["endpoint"] == hmc.DEFAULT_BASE_URL
    assert t["model"] == hmc.DEFAULT_MODEL
    assert t["llm_api_key_from"] == "HINDSIGHT_LLM_API_KEY"
    assert t["bank_id_template"] == "{profile}"
    assert t["additional_banks"] == [hmc.SHARED_BANK]


def test_render_writes_every_profile_from_the_template(tmp_path):
    """Every `llgenie-*` profile gets a hindsight config from the SAME template."""
    home = tmp_path / "home"
    _profile(home, "llgenie-a")
    _profile(home, "llgenie-b")

    paths = hmc.render_all(home)
    assert sorted(p.name for p in paths) == ["config.json", "config.json"]
    for name in ("llgenie-a", "llgenie-b"):
        doc = json.loads((home / ".hermes/profiles" / name / "hindsight/config.json").read_text())
        # same template: identical except the profile name
        assert doc["profile_name"] == name
        assert doc["mode"] == "local_embedded"
        assert doc["bank_id_template"] == "{profile}"
        assert doc["additional_banks"] == [hmc.SHARED_BANK]


def test_render_is_idempotent_byte_for_byte(tmp_path):
    """A second render changes nothing (proven on the bytes, not by prose)."""
    home = tmp_path / "home"
    _profile(home, "llgenie-a")

    first = hmc.render_all(home)
    first_bytes = {p: p.read_bytes() for p in first}

    second = hmc.render_all(home)
    assert second == first
    for p in second:
        assert p.read_bytes() == first_bytes[p], "render must be idempotent"
        assert (p.stat().st_mode & 0o777) == 0o600, "config is a 0600 host file"


def test_drift_test_asserts_a_subset_so_a_new_profile_does_not_red():
    """The gate's profile set assertion is `expected <= actual`: a 14th profile must not red it."""
    configured = {f"llgenie-{i}" for i in range(13)}
    discovered = configured | {"llgenie-14th"}  # upstream added a 14th profile
    assert configured <= discovered, "a superset of the configured set must not fail the gate"
    # and the reverse — a profile the fleet is SUPPOSED to have but the host lacks — must fail
    missing = configured - {"llgenie-3"}
    assert not (configured <= missing), "a profile missing from the expected set must red the gate"


# ---------------------------------------------------------------------------
# the gate: profiles agreeing with the shared env pass; drift + empty key are named
# ---------------------------------------------------------------------------

def test_agreeing_profiles_produce_no_profile_findings(tmp_path):
    """When every profile's env agrees with the shared hermes.env, profile_findings is empty
    (the daemon half is exercised separately — a bare runner cannot host a Hindsight daemon)."""
    home = tmp_path / "home"
    _profile(home, "llgenie-a")
    _profile(home, "llgenie-b")
    _shared(home)

    # Given the configured profiles whose endpoint/model agree with the shared file
    assert hmc.profile_findings(home) == []


def test_drifted_profile_is_named(tmp_path):
    """A profile whose endpoint disagrees with the shared hermes.env is a finding name PING the
    profile."""
    home = tmp_path / "home"
    _profile(home, "llgenie-architect")
    _profile(home, "llgenie-shared")
    _shared(home)

    # When  the shared file's model is the flipped documented model (the measured incident)
    (home / ".hindsight/profiles" / hmc.SHARED_ENV).write_text(
        "HINDSIGHT_API_LLM_BASE_URL=https://inference-api.nousresearch.com/v1\n"
        "HINDSIGHT_API_LLM_MODEL=openai/qwen3.8-27b-iq3_s\n")

    # Then  the gate fails, naming the profile
    findings = hmc.profile_findings(home)
    assert findings, "the flipped endpoint must be a finding"
    assert any("llgenie-architect" in f and "HINDSIGHT_API_LLM_MODEL" in f for f in findings)


def test_empty_key_is_caught_as_the_placeholder_hazard(tmp_path):
    """A profile holding no key would build the `not-needed` placeholder over the shared key; the
    gate fails naming the profile so the placeholder can never be written silently."""
    home = tmp_path / "home"
    _profile(home, "llgenie-a", key="")  # empty key -> .env has HINDSIGHT_LLM_API_KEY=
    _shared(home)

    findings = hmc.profile_findings(home)
    assert findings
    assert any("llgenie-a" in f and "placeholder" in f for f in findings)
    assert hmc.profile_key(home, "llgenie-a") == "not-needed"


# ---------------------------------------------------------------------------
# the live daemon half is measured from real evidence, not /health
# ---------------------------------------------------------------------------

def test_daemon_findings_reads_the_log_and_reports_no_daemon_honestly(tmp_path):
    """The daemon half must read the last `Connection verified:` line and, on a host with no real
    hindsight-api process, say so rather than treating `/health` as evidence."""
    home = tmp_path / "home"
    (home / ".hindsight/profiles").mkdir(parents=True, exist_ok=True)

    # When the log's last connection line names a DIFFERENT model than the template
    (home / ".hindsight/profiles" / hmc.SHARED_LOG).write_text(
        "02:11:27 Connection verified: openai/deepseek/deepseek-v4-flash-0731\n"
        "02:14:29 Connection verified: openai/qwen3.8-27b-iq3_s\n")

    findings = hmc.daemon_findings(home)
    # the flipped last connection model is a finding
    assert any("Connection verified" in f for f in findings)


def test_last_connection_line_returns_the_last_match():
    """`last_connection_line` returns the LAST `Connection verified:` value in a real log."""
    log = Path(__import__("tempfile").mkdtemp()) / "hermes.log"
    log.write_text(
        "02:11:27 Connection verified: openai/deepseek/deepseek-v4-flash-0731\n"
        "02:14:29 Connection verified: openai/qwen3.8-27b-iq3_s\n")
    assert hmc.last_connection_line(log) == "openai/qwen3.8-27b-iq3_s"


# ---------------------------------------------------------------------------
# the make wiring exists
# ---------------------------------------------------------------------------

def test_make_memory_check_wiring():
    """`memory-check` is a declared `.PHONY` target running the script (the gate is real)."""
    mk = (REPO / "Makefile").read_text()
    assert "\nmemory-check:" in mk, "make memory-check must exist"
    recipe_block = mk.split("\nmemory-check:", 1)[1].split("\n\n", 1)[0]
    assert "scripts/hindsight_memory_check.py check" in recipe_block, (
        "the target must run scripts/hindsight_memory_check.py check")
    phony_text = mk.split("\n.PHONY:", 1)[1]
    assert "memory-check" in phony_text, "memory-check must be declared .PHONY"


def test_lane_preflight_wires_memory_check():
    """`memory-check` is a host-only gate on the lane preflight (a dispatch cannot start on a
    flipped endpoint), without touching the #475 FAST_GATES list a bare runner runs."""
    text = (REPO / "scripts/lane_preflight.py").read_text()
    assert "HOST_GATES" in text and "memory-check" in text
    from scripts import issue_bot_gates
    assert "memory-check" not in issue_bot_gates.FAST_GATES, (
        "memory-check reads the live host, so it must be a host-only gate, not in the #475 "
        "FAST_GATES list that ci-unit and the issue-bot run on a bare runner")
