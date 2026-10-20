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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import unit_tests as ut  # noqa: E402  (the unit-suite aggregator, issue #393)
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
    # the fetch leg's inputs (#362): a URL, an output path and a byte budget — knobs, not secrets
    "URL", "OUT", "BUDGET",
}
#: The bot jobs that start the agent image: (workflow, the keys that job actually sets).
BOT_JOBS = {
    "fix-bot.yml": ("NOUS_API_KEY", "GH_TOKEN", "TYPESAFE_API_KEY"),
    "issue-bot.yml": ("NOUS_API_KEY", "GH_TOKEN", "TYPESAFE_API_KEY"),  # #364: the leg forwards it, so the job must set it
    "issue-refiner.yml": ("NOUS_API_KEY", "TYPESAFE_API_KEY", "FIRECRAWL_API_KEY"),  # #380: the leg pre-fetches, so the job must set it
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

        # Then the job runs the check with exactly the keys that job sets. Only STEP lines count:
        # a comment naming the target is not a second check, and the dispatch-form guard REQUIRES a
        # workflow's `Flow:` header to name the targets its run takes (`make check-dispatch-forms`),
        # so prose would otherwise trip this count. The repo's other guards strip comments the same
        # way (check_wiring, check_secret_output) — read the decision, not the prose.
        steps = [l for l in text.splitlines()
                 if "make agent-shell-keys-check" in l and not l.lstrip().startswith("#")]
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

    # And this suite is in the discovered unit suite (issue #393), so it runs in the gate
    assert "tests/test_agent_shell_keys.py" in ut.select(ROOT), "this suite is in no gate"


# ---------------------------------------------------------------------------
# every key a leg forwards is SET by the job that calls it (#364)
# ---------------------------------------------------------------------------
def _jobs(text: str) -> dict[str, str]:
    """{job name: job source} for a workflow — a job starts at a two-space key under `jobs:`."""
    body = text.split("\njobs:\n", 1)[1] if "\njobs:\n" in text else text
    jobs, name, buf = {}, None, []
    for line in body.splitlines():
        m = re.match(r"^  ([a-z0-9_-]+):\s*$", line)
        if m:
            if name:
                jobs[name] = "\n".join(buf)
            name, buf = m.group(1), [line]
        elif name:
            buf.append(line)
    if name:
        jobs[name] = "\n".join(buf)
    return jobs


def _leg_keys(target: str) -> set[str]:
    """The credential NAMEs a make target forwards with `-e` (the forced twins excluded)."""
    mk = (ROOT / "Makefile").read_text()
    body = _agent_legs_body(mk, target)
    keys = {k for k in re.findall(r"-e\s+([A-Z][A-Z0-9_]*)\b", body)}
    return keys - set(NON_CREDENTIAL_ENV) - {k[len(FORCE):] for k in keys if k.startswith(FORCE)}


def _agent_legs_body(mk: str, target: str) -> str:
    i = mk.index("\n" + target + ":") + 1
    head_end = mk.index("\n", i) + 1          # start of the recipe, past the target header
    nxt = re.search(r"(?m)^[a-z0-9][a-z0-9._-]*:", mk[head_end:])
    return mk[head_end:head_end + (nxt.start() if nxt else len(mk) - head_end)]


def _steps(job_text: str) -> list[str]:
    """The step blocks of a job (a step starts at `      - `)."""
    out, buf = [], []
    for line in job_text.splitlines():
        if re.match(r"^      - ", line):
            if buf:
                out.append("\n".join(buf))
            buf = [line]
        elif buf is not None:
            buf.append(line)
    if buf:
        out.append("\n".join(buf))
    return out


def _job_env(job_text: str) -> str:
    """The job-level `env:` block only — a SIBLING step's env does not apply to this step."""
    head = job_text.split("    steps:", 1)[0]
    m = re.search(r"(?ms)^    env:\n(.*)", head)
    return m.group(1) if m else ""


def _step_sets_key(job_text: str, trigger: str, name: str) -> bool:
    """True when the step that runs `trigger` sees `name` — job env or that step's own env.

    A different step's env does NOT count: that was exactly the #364 defect (the push step exported
    `GH_TOKEN: secrets.BUMP_TOKEN`, the implement step exported nothing, and the leg's `-e GH_TOKEN`
    forwarded an empty value).
    """
    pat = re.compile(rf"(?m)^\s+{name}:\s*\$\{{\{{")
    if pat.search(_job_env(job_text)):
        return True
    for step in _steps(job_text):
        if trigger in step and pat.search(step):
            return True
    return False


def test_the_leg_a_workflow_calls_gets_its_keys_from_that_job():
    """The #364 defect: `-e GH_TOKEN` was forwarded into a job that never set GH_TOKEN."""
    checked = 0
    # (workflow, what the workflow actually runs, the leg whose keys that run needs)
    entries = (("fix-bot.yml", "make fix-loop-image", "fix-loop-image"),
               ("issue-bot.yml", "make implement-issue", "implement-issue"),
               ("issue-refiner.yml", "make issue-refiner", "issue-refiner"),
               # the rebase job runs the script, which invokes `make rebase-bot-agent` on the host
               ("rebase-bot.yml", "make rebase-bot ", "rebase-bot-agent"))
    for workflow, trigger, leg in entries:
        text = (WORKFLOWS / workflow).read_text()
        jobs = _jobs(text)
        calling = {n: b for n, b in jobs.items() if trigger in b}
        assert calling, f"{workflow} no longer runs `{trigger.strip()}`"
        for job_name, job in calling.items():
            for key in _leg_keys(leg):
                assert _step_sets_key(job, trigger, key), (
                    f"{workflow}:{job_name} runs `make {leg}`, which forwards -e {key}, but the job "
                    f"never sets {key} — the container gets an EMPTY value that looks wired (#364)")
                checked += 1
    assert checked >= 5, f"expected the bot jobs to be checked, got {checked}"


def test_the_detector_actually_detects():
    """A sibling step's env must NOT count as this step's credential (#364's exact shape)."""
    sibling = ("  implement:\n    steps:\n"
               "      - run: make implement-issue\n"
               "      - name: push\n        env:\n          GH_TOKEN: ${{ secrets.BUMP_TOKEN }}\n"
               "        run: git push\n")
    assert not _step_sets_key(sibling, "make implement-issue", "GH_TOKEN")
    same = ("  implement:\n    steps:\n      - run: make implement-issue\n"
            "        env:\n          GH_TOKEN: ${{ github.token }}\n")
    assert _step_sets_key(same, "make implement-issue", "GH_TOKEN")
    job_env = ("  implement:\n    env:\n      GH_TOKEN: ${{ github.token }}\n    steps:\n"
               "      - run: make implement-issue\n")
    assert _step_sets_key(job_env, "make implement-issue", "GH_TOKEN")
