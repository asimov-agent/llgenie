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
from scripts import unit_tests as ut
from conftest import makefiles_text  # noqa: E402  (the include-resolving Makefile reader)
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
#: The half that stays HAND-NAMED (#908): the key set each bot job PROVES through the
#: composite's `shell_keys` input. That is a claim about what the job proves, not about what a
#: leg forwards, so no recipe scan can derive it. The forwarding coverage — which job must set
#: which key for which leg call — is derived from the tree in _leg_calls(), not from this map.
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
    mk = makefiles_text()
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
    # The ONE place the check lives is the composite action (issue #798): a single step that every
    # agent leg calls, so the shell is proven exactly once per leg by calling it.
    leg = (ROOT / ".github" / "actions" / "agent-leg" / "action.yml").read_text()
    steps = [l for l in leg.splitlines()
             if "make agent-shell-keys-check" in l and not l.lstrip().startswith("#")]
    assert len(steps) == 1, f"agent-leg does not prove the agent's shell exactly once: {steps}"
    # The keys cross into the check as the step's env, never as shell text on the make line
    # (issue #2505: interpolated values are passed as env, not composed into a shell command).
    # Accept either sanctioned shape, but the value must come from `inputs.shell_keys`.
    leg_lines = leg.splitlines()
    idx = [i for i, l in enumerate(leg_lines) if l in steps][0]
    step_block = "\n".join(leg_lines[max(0, idx - 8):idx + 1])
    assert ("AGENT_SHELL_CHECK_KEYS: ${{ inputs.shell_keys }}" in step_block
            or 'AGENT_SHELL_CHECK_KEYS="${{ inputs.shell_keys }}"' in steps[0]), step_block

    for workflow, keys in BOT_JOBS.items():
        text = (WORKFLOWS / workflow).read_text()

        # Then the leg receives exactly the keys that job sets, by NAME, from the composite input
        # (the shell proof is a property of calling the leg, not of a hand-written step per job).
        want = 'shell_keys: "' + " ".join(keys) + '"'
        assert want in text, f"{workflow} proves the wrong key set: {want!r}"

        # And every key it proves is one the job actually sets (else the check fails on a key it lacks)
        for k in keys:
            assert re.search(rf"^\s+{k}: \$\{{{{", text, re.M), f"{workflow} proves {k} but never sets it"


def test_the_check_is_wired_to_a_make_target_ci_runs():
    mk = makefiles_text()

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
    mk = makefiles_text()
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


MAKE_TOKEN_RE = re.compile(r"(?:\$\((?:MAKE|make)\)|\bmake\b)(?P<rest>[^\n#]*)")


def _make_calls(text: str, names: set[str]) -> list[tuple[str, str]]:
    """(the make-run text, target) for every `make <target>` in `text` whose target is a known
    name. Tokens are matched against the KNOWN target names, so variable-assignment arguments
    (`make rebase-bot REPO=...`), quoted values, and commented-out mentions cannot masquerade
    as calls. Mentions that are NOT invocations are skipped: text after a shell/YAML `#` on the
    line, and text wrapped in backticks (docstrings and usage prose, e.g. the `make
    auto-merge-explain` mentions in scripts/auto_merge.py — auto-merge runs auto_merge.py, and
    those mentions must not masquerade as the script reaching an agent leg)."""
    out = []
    for m in MAKE_TOKEN_RE.finditer(text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.start())
        line = text[line_start: len(text) if line_end == -1 else line_end]
        off = m.start() - line_start
        if "#" in line[:off]:
            continue  # shell/YAML comment on this line
        if any(s <= off < e for s, e in (mm.span() for mm in re.finditer(r"`[^`]*`", line))):
            continue  # backtick-wrapped prose, not a command position
        for tok in re.findall(r"[a-z][a-z0-9._-]*", m.group("rest")):
            if tok in names:
                out.append((m.group(0), tok))
    return out


def _target_bodies() -> dict[str, str]:
    """{target: recipe body} from the include-resolved Makefile — no target is named here."""
    mk = makefiles_text()
    bodies: dict[str, str] = {}
    for m in re.finditer(r"(?m)^([a-z0-9][a-z0-9._-]*):.*?$", mk):
        start = m.end()
        nxt = re.search(r"(?m)^[a-z0-9][a-z0-9._-]*:", mk[start:])
        bodies.setdefault(m.group(1), mk[start:start + (nxt.start() if nxt else len(mk) - start)])
    return bodies


def _tree_scripts() -> dict[str, str]:
    """{shell script file name: text} under scripts/ — recipes reach legs through them (the
    rebase-bot shape: `make rebase-bot` runs scripts/rebase_bot.sh, whose AGENT_CMD default
    runs the leg). Only SHELL scripts are followed: a shell script executes what it writes,
    while a `make X` inside a .py string may be a validator regex or docs prose
    (check_workflows.py carries `re.compile(r"make\\s+agent-jev-preflight\\b")` as a CHECK
    other jobs are held to, not a call it makes) — following .py would invent edges."""
    d: dict[str, str] = {}
    for p in sorted((ROOT / "scripts").glob("*.sh")):
        if p.is_file():
            d[p.name] = p.read_text()
    return d


def _keys_forwarded(body: str) -> set[str]:
    """Credential NAMEs a recipe body forwards with `-e` (knobs and the forced twins excluded)."""
    keys = {k for k in re.findall(r"-e\s+([A-Z][A-Z0-9_]*)\b", body)}
    return keys - set(NON_CREDENTIAL_ENV) - {k[len(FORCE):] for k in keys if k.startswith(FORCE)}


SCRIPT_REF_RE = re.compile(r"scripts/([A-Za-z0-9_.-]+\.(?:sh|py))")


def _legs_run_by(bodies: dict[str, str], legs: set[str], target: str,
                 scripts: dict[str, str]) -> set[str]:
    """The agent legs `target`'s recipe runs — directly, through nested make wrappers, or
    through a script the recipe executes (the rebase-bot shape: the recipe runs
    `scripts/rebase_bot.sh`, whose default AGENT_CMD is `make -f $MK_SNAPSHOT rebase-bot-agent`)."""
    out, stack, seen = set(), [target], {target}
    while stack:
        body = bodies.get(stack.pop(), "")
        called = {tok for _run, tok in _make_calls(body, set(bodies))}
        for rel in SCRIPT_REF_RE.findall(body):
            called |= {tok for _run, tok in _make_calls(scripts.get(rel, ""), set(bodies))}
        for nxt in called:
            if nxt in seen:
                continue
            seen.add(nxt)
            if nxt in legs:
                out.add(nxt)
            stack.append(nxt)
    return out


def _leg_calls(bodies: dict[str, str], workflows: dict[str, str],
               scripts: dict[str, str]) -> list[tuple[str, str, str, str]]:
    """(workflow, job, the make-run text, leg) for EVERY leg call a workflow step makes.

    #908: this names no workflow, job, or target. An agent leg is any Makefile recipe that
    starts the agent image (`$(AGENT_IMAGE)`); a workflow step counts as a leg call when its
    text runs `make <target>` and <target> is a leg — or a wrapper whose recipe (or script)
    reaches one.
    """
    legs = {t for t, b in bodies.items() if "$(AGENT_IMAGE)" in b}
    calls: set[tuple[str, str, str, str]] = set()
    for wf_name, text in workflows.items():
        for job_name, job in _jobs(text).items():
            for step in _steps(job):
                for run_text, target in _make_calls(step, set(bodies)):
                    for leg in ({target} & legs) | _legs_run_by(bodies, legs, target, scripts):
                        calls.add((wf_name, job_name, run_text, leg))
    return sorted(calls)


def _coverage_findings(bodies: dict[str, str], workflows: dict[str, str],
                       scripts: dict[str, str]) -> list[str]:
    """The #364 findings over a (possibly synthetic) tree: each is a leg call whose job does
    not set one of the keys that leg forwards."""
    findings = []
    for wf_name, job_name, trigger, leg in _leg_calls(bodies, workflows, scripts):
        job = _jobs(workflows[wf_name])[job_name]
        for key in sorted(_keys_forwarded(bodies[leg])):
            if not _step_sets_key(job, trigger, key):
                findings.append(f"{wf_name}:{job_name} runs `{trigger}` ({leg} forwards -e {key}) "
                                f"but the job never sets {key}")
    return findings


def test_the_leg_a_workflow_calls_gets_its_keys_from_that_job():
    """#364's defect class over the WHOLE board, derived from the tree (#908): every workflow
    call of an agent leg must set the keys that leg forwards — no hand-kept roster."""
    bodies = _target_bodies()
    workflows = {p.name: p.read_text() for p in sorted(WORKFLOWS.glob("*.yml"))}
    calls = _leg_calls(bodies, workflows, _tree_scripts())
    assert calls, ("the derived walk found NO leg call in the checkout — the Makefile or the "
                   "workflows changed shape and the rule went vacuous (#908)")

    # The four calls the old hand-kept `entries` pinned stay covered — derived, not listed
    pinned = {("fix-bot.yml", "fix-loop-image"), ("issue-bot.yml", "implement-issue"),
              ("issue-refiner.yml", "issue-refiner"),
              ("rebase-bot.yml", "rebase-bot-agent")}  # wrapper-mediated: the job runs `make rebase-bot`
    derived = {(wf, leg) for wf, _job, _run, leg in calls}
    lost = pinned - derived
    assert not lost, f"the derived walk lost cases the old entries covered: {sorted(lost)}"

    checked = 0
    for wf_name, job_name, trigger, leg in calls:
        job = _jobs(workflows[wf_name])[job_name]
        for key in sorted(_keys_forwarded(bodies[leg])):
            assert _step_sets_key(job, trigger, key), (
                f"{wf_name}:{job_name} runs `{trigger}`, and {leg} is an agent leg that forwards "
                f"-e {key}, but the job never sets {key} — the container gets an EMPTY value "
                f"that looks wired (#364, #908)")
            checked += 1
    # Measured floor (base 4f3fc1ef25a0: 23 leg calls across 9 workflows, 16 agent legs):
    # a walk this narrow is the vacuous-pass shape #908 replaces.
    assert len(calls) >= 10, f"the derived walk found only {len(calls)} leg calls — coverage collapsed"
    assert checked >= 5, f"derived coverage ran only {checked} key assertions — the rule went vacuous"


def test_the_derived_walk_catches_the_364_shape_in_a_planted_tree():
    """End-to-end proof of the derived walk (#908): plant #364's exact shape — a job calls a
    leg that forwards `-e GH_TOKEN` and sets it only in a SIBLING step's env — the walk names it."""
    bodies = {
        "sweep": ("sweep:\n\t@$(MAKE) sweep-agent\n"),
        "sweep-agent": ("sweep-agent:\n\t@$(RUNTIME) run --rm $(AGENT_IMAGE) sh -c 'scan'\n"
                        "\t\t-e NOUS_API_KEY -e GH_TOKEN $(AGENT_SHELL_FORWARD)\n"),
    }
    planted = ("jobs:\n  sweep:\n    steps:\n"
               "      - name: sweep\n        env:\n          NOUS_API_KEY: ${{ secrets.NOUS }}\n"
               "        run: make sweep\n"
               "      - name: push\n        env:\n          GH_TOKEN: ${{ secrets.BUMP_TOKEN }}\n"
               "        run: git push\n")
    calls = _leg_calls(bodies, {"planted.yml": planted}, {})
    assert len(calls) == 1 and calls[0][0] == "planted.yml" and calls[0][1] == "sweep" \
        and calls[0][3] == "sweep-agent", calls

    findings = _coverage_findings(bodies, {"planted.yml": planted}, {})
    assert findings and any("GH_TOKEN" in f for f in findings), \
        f"the derived walk missed the planted #364 shape: {findings}"
    # NOUS_API_KEY IS set by the calling step — the finding names only the missing key
    assert not any("NOUS_API_KEY" in f for f in findings), findings

    # Green after: the same job sets the key at job level → no finding
    fixed = ("jobs:\n  sweep:\n    env:\n      GH_TOKEN: ${{ secrets.BUMP_TOKEN }}\n    steps:\n"
             "      - name: sweep\n        env:\n          NOUS_API_KEY: ${{ secrets.NOUS }}\n"
             "        run: make sweep\n")
    assert _coverage_findings(bodies, {"planted.yml": fixed}, {}) == []


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
