#!/usr/bin/env python3
"""The agent's shell sees every credential a container receives (issue #358).

Hermes strips provider credentials from its terminal tool on purpose, so a key forwarded as
`-e NOUS_API_KEY` reaches the container and the Hermes process while the AGENT's shell reads it
EMPTY — a bot that then does nothing, green. The fix forwards each key as `_HERMES_FORCE_<NAME>`
from ONE Makefile list. This suite proves the hermetic half, with SENTINEL values only:

* the Makefile: `AGENT_SHELL_KEYS` names every credential an agent leg forwards, and the forced
  names travel BY NAME — a `make -n` rendered with the sentinels set must not contain a sentinel;
* make's export: on the host, `make` really exports `_HERMES_FORCE_<NAME>` = `<NAME>` to a recipe,
  exports nothing for an unset key, and re-creates nothing inside a container (so the check proves
  what `docker run` forwarded);
* the loudness: a key missing from the container is exit 2, never a skip, and the only opt-out says
  `NOT CONFIGURED` and appears in no workflow;
* the wiring: the bot workflows run `make agent-shell-keys-check`, and the target runs the script
  inside the agent image.

The probe against the REAL Hermes (`LocalEnvironment`) runs where Hermes is installed — the agent
image in the bot jobs, and this host: it is the live half of the scenario, and the wiring test below
asserts it has not been dropped. This suite itself needs only make + python, so `make test-unit`
stays hermetic.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "agent_shell_keys_check.py"
WORKFLOWS = ROOT / ".github" / "workflows"

# secret-output: test value — sentinels, never credentials.
SENTINEL = "SENTINELvalue0123456789abcdef"
FORCE = "_HERMES_FORCE_"
#: Every credential a container in this repo receives (the Makefile list must name them).
CREDENTIALS = ("NOUS_API_KEY", "GH_TOKEN", "HF_TOKEN", "TYPESAFE_API_KEY")
#: `-e` names an agent leg may carry that are NOT credentials (knobs, not secrets).
NON_CREDENTIAL_ENV = {
    "HERMES_REASONING", "REPO", "FIX_CHECK", "FIX_ROUNDS", "AGENT_SHELL_CHECK_KEYS",
    "HERMES_NERVE_PROVIDER", "NERVE_REQUIRE", "NERVE_GATE_SKIP_PROVIDER",
}
#: The bot jobs that start the agent image: (workflow, the keys that job actually sets).
BOT_JOBS = {
    "fix-bot.yml": ("NOUS_API_KEY", "GH_TOKEN", "TYPESAFE_API_KEY"),
    "issue-bot.yml": ("NOUS_API_KEY", "TYPESAFE_API_KEY"),
    "issue-refiner.yml": ("NOUS_API_KEY", "TYPESAFE_API_KEY"),
    "rebase-bot.yml": ("NOUS_API_KEY", "TYPESAFE_API_KEY"),
}


def _clean_env(**extra) -> dict:
    """The process env with every credential and every forced name removed, plus `extra`."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(FORCE) and k not in ("GH_TOKEN", "GITHUB_TOKEN", *CREDENTIALS)}
    env.update(extra)
    return env


def _keys() -> list[str]:
    """AGENT_SHELL_KEYS as make itself expands it — never a second copy of the list."""
    r = subprocess.run(["make", "-s", "--no-print-directory", "-f", "Makefile", "-f", "-", "_print-keys"],
                       cwd=ROOT, input="_print-keys:\n\t@echo $(AGENT_SHELL_KEYS)\n",
                       capture_output=True, text=True, env=_clean_env())
    assert r.returncode == 0, r.stderr
    return r.stdout.split()


def _agent_legs() -> list[tuple[str, str]]:
    """(target, recipe body) for every make target that starts the agent image."""
    mk = (ROOT / "Makefile").read_text()
    legs = []
    for m in re.finditer(r"(?m)^([a-z0-9][a-z0-9._-]*):.*?$", mk):
        start = m.end()
        nxt = re.search(r"(?m)^[a-z0-9][a-z0-9._-]*:", mk[start:])
        body = mk[start:start + (nxt.start() if nxt else len(mk) - start)]
        if "$(AGENT_IMAGE)" in body:
            legs.append((m.group(1), body))
    return legs


# ---------------------------------------------------------------------------
# Given: one list, and every agent leg forwards it
# ---------------------------------------------------------------------------
def test_the_list_names_every_credential_an_agent_leg_forwards():
    keys = _keys()

    # Then every credential a container receives is in the list
    for name in CREDENTIALS:
        assert name in keys, f"AGENT_SHELL_KEYS does not name {name}: {keys}"

    # And every credential an agent leg spells out is a member (no key the agent cannot see)
    legs = _agent_legs()
    assert legs, "no make target starts the agent image — the Makefile changed shape"
    forwarded: set[str] = set()
    for _target, body in legs:
        for name in re.findall(r"-e\s+([A-Z][A-Z0-9_]*)\b", body):
            forwarded.add(name)
    unknown = sorted(forwarded - set(keys) - NON_CREDENTIAL_ENV)
    assert not unknown, f"an agent leg forwards a credential the agent's shell is not proven to see: {unknown}"

    # And every agent leg forwards the forced twins, so none can be the one that forgot
    for target, body in legs:
        assert "$(AGENT_SHELL_FORWARD)" in body, f"{target} does not forward the forced names"


def test_the_forced_names_travel_by_name_never_by_value():
    # Given sentinel values for every credential
    env = _clean_env(IN_CONTAINER="", **{k: SENTINEL for k in CREDENTIALS})

    # When  make renders the check's command line
    r = subprocess.run(["make", "-n", "--no-print-directory", "agent-shell-keys-check", "IN_CONTAINER="],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    out = r.stdout + r.stderr

    # Then  every listed key is forwarded in its forced form, and no value is anywhere in it
    for k in _keys():
        assert f"-e {FORCE}{k}" in out, f"`-e {FORCE}{k}` is not forwarded:\n{out[-400:]}"
    assert SENTINEL not in out, "a sentinel value reached a command line"


# ---------------------------------------------------------------------------
# make exports the forced name from the plain one (host) and re-creates none (container)
# ---------------------------------------------------------------------------
def _recipe_lengths(env: dict, in_container: str = "") -> dict[str, int]:
    probe = "_probe:\n" + "".join(
        '\t@v="$${%s%s}"; printf "%%s=%%s\\n" %s%s "$${#v}"\n' % (FORCE, k, FORCE, k) for k in _keys())
    r = subprocess.run(["make", "-s", "--no-print-directory", "-f", "Makefile", "-f", "-", "_probe",
                        "IN_CONTAINER=%s" % in_container],
                       cwd=ROOT, input=probe, env=env, capture_output=True, text=True)
    out = {}
    for line in r.stdout.splitlines():
        k, sep, v = line.partition("=")
        if sep and v.isdigit():
            out[k] = int(v)
    return out


def test_make_exports_the_forced_name_from_the_plain_one():
    # Given a host where two credentials are set and the others are not
    got = _recipe_lengths(_clean_env(IN_CONTAINER="", **{k: SENTINEL for k in CREDENTIALS[:2]}))

    # Then  the set keys are exported as _HERMES_FORCE_<NAME>, the unset ones export nothing
    for k in CREDENTIALS[:2]:
        assert got.get(FORCE + k) == len(SENTINEL), f"{FORCE}{k} was not exported from {k}: {got}"
    for k in CREDENTIALS[2:]:
        assert got.get(FORCE + k) == 0, f"{FORCE}{k} was exported although {k} is unset: {got}"

    # And inside a container nothing is re-created (the check proves what docker forwarded)
    inside = _recipe_lengths(_clean_env(**{k: SENTINEL for k in CREDENTIALS}), in_container="1")
    assert inside and all(v == 0 for v in inside.values()), f"an inner make re-created a forced name: {inside}"


# ---------------------------------------------------------------------------
# the loudness: a missing key fails, the opt-out says so, no workflow uses it
# ---------------------------------------------------------------------------
def test_a_missing_key_is_loud_and_the_opt_out_says_so():
    # Given a container with no credential set
    env = _clean_env()

    # When  the probe runs with a name from the list (it fails before any Hermes probe)
    r = subprocess.run(["python3", str(SCRIPT), "NOUS_API_KEY"], env=env, capture_output=True, text=True)

    # Then  it exits 2 and names the variable — never a silent pass
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "NOUS_API_KEY" in r.stderr and "FATAL" in r.stderr, r.stderr
    assert SENTINEL not in (r.stdout + r.stderr)

    # And the opt-out is explicit and says nothing was verified
    r2 = subprocess.run(["python3", str(SCRIPT), "NOUS_API_KEY", "--allow-unconfigured"],
                        env=env, capture_output=True, text=True)
    assert r2.returncode == 0 and "NOT CONFIGURED" in r2.stdout, (r2.returncode, r2.stdout)

    # And no workflow pairs the check with the opt-out
    for f in WORKFLOWS.glob("*.yml"):
        for line in f.read_text().splitlines():
            assert not ("agent-shell-keys" in line and "allow-unconfigured" in line), \
                f"{f.name}: the opt-out must never reach CI"


def test_a_name_that_is_not_a_variable_is_refused():
    # Given a name that is not a variable name
    r = subprocess.run(["python3", str(SCRIPT), "not-a-name"], env=_clean_env(), capture_output=True, text=True)

    # Then  it is refused before anything is probed
    assert r.returncode == 2 and "not a variable name" in r.stderr, (r.returncode, r.stderr)


# ---------------------------------------------------------------------------
# the wiring: the bot jobs run the check, the target runs the script in the image
# ---------------------------------------------------------------------------
def test_every_bot_job_proves_the_agent_shell():
    for workflow, keys in BOT_JOBS.items():
        text = (WORKFLOWS / workflow).read_text()

        # Then the job runs the check with exactly the keys that job sets
        steps = [l for l in text.splitlines() if "make agent-shell-keys-check" in l]
        assert len(steps) == 1, f"{workflow} does not prove the agent's shell exactly once: {steps}"
        want = 'AGENT_SHELL_CHECK_KEYS="' + " ".join(keys) + '"'
        assert want in steps[0], f"{workflow} proves the wrong key set: {steps[0]}"

        # And every key it proves is one the job actually sets (else the check fails on a key it lacks)
        for k in keys:
            assert re.search(rf"^\s+{k}: \$\{{\{{", text, re.M), f"{workflow} proves {k} but never sets it"


def test_the_check_is_wired_to_a_make_target_ci_runs():
    mk = (ROOT / "Makefile").read_text()

    # Then the internal target runs the script with the ONE list as its default
    assert "python3 scripts/agent_shell_keys_check.py $(AGENT_SHELL_CHECK_KEYS)" in mk
    assert "AGENT_SHELL_CHECK_KEYS ?= $(AGENT_SHELL_KEYS)" in mk

    # And the public target runs it inside the agent image, forwarding names only
    target = re.search(r"(?ms)^agent-shell-keys-check:.*?(?=^\S|\Z)", mk)
    assert target, "the public agent-shell-keys-check target is missing"
    body = target.group(0)
    assert "$(RUNTIME) run" in body and "$(AGENT_IMAGE)" in body, body
    assert "$(AGENT_SHELL_FORWARD)" in body and "$(AGENT_SHELL_FORWARD_PLAIN)" in body, body

    # And it is declared .PHONY (a name that collides with a file would silently not run)
    phony = mk[:mk.index("\n\nall:")] if "\n\nall:" in mk else mk
    assert re.search(r"(?m)^\tagent-shell-keys-check(\s|\\|$)", phony), "agent-shell-keys-check is not .PHONY"

    # And this suite is named by the unit gate (nothing dead)
    assert "tests/test_agent_shell_keys.py" in mk, "this suite is in no make target"
