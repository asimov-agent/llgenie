#!/usr/bin/env python3
"""Every bot leg refuses to start on a missing credential, before it spends the runner (issue #363).

`make hermes-smoke` was the ONLY leg that guarded on its key; the other six forwarded
`-e NOUS_API_KEY` / `-e TYPESAFE_API_KEY` and only failed **inside** the container, after an image
pull and a container start, on a job with a 120-180 minute timeout. This suite locks the guard at
both ends, with sentinels only:

* `scripts/require_env.py` — a missing or empty key is exit 2, the variable is named, no value is
  printed; a bad name is refused; a present key passes;
* the Makefile — every target that starts the agent image runs the guard **before**
  `scripts/ci_images.py ensure agent`, and the roster is derived from the file (a hand-maintained
  list is the defect this repo has already filed twice: #349, #301);
* the old ad-hoc bash guard is gone, so there is ONE code path.

NO-SKIP POLICY: every case asserts something real; none is skipped.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "require_env.py"
MAKEFILE = REPO / "Makefile"
from scripts import unit_tests as ut

# secret-output: test value — a sentinel, never a credential.
SENTINEL = "SENTINELvalue0123456789abcdef"


def _run(env: dict, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=60)


def _clean_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("NOUS_API_KEY", "TYPESAFE_API_KEY", "GH_TOKEN", "HF_TOKEN")}
    env.update(extra)
    return env


def _recipes() -> dict[str, str]:
    """(target, recipe body) for every make target — derived from the file, never a roster."""
    mk = MAKEFILE.read_text()
    out = {}
    for m in re.finditer(r"(?m)^([a-z0-9][a-z0-9._-]*):.*?$", mk):
        start = m.end()
        nxt = re.search(r"(?m)^[a-z0-9][a-z0-9._-]*:", mk[start:])
        out[m.group(1)] = mk[start:start + (nxt.start() if nxt else len(mk) - start)]
    return out


# ---------------------------------------------------------------------------
# the guard itself
# ---------------------------------------------------------------------------
def test_a_missing_key_exits_2_and_names_the_variable():
    # Given no key in the environment
    r = _run(_clean_env(), "NOUS_API_KEY")

    # Then  it is a loud failure that names the variable and prints no value
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "NOUS_API_KEY" in r.stderr and "FATAL" in r.stderr, r.stderr
    assert SENTINEL not in (r.stdout + r.stderr)


def test_an_empty_key_is_treated_as_missing():
    # Given a key that is set but empty
    r = _run(_clean_env(NOUS_API_KEY=""), "NOUS_API_KEY")

    # Then  it is refused the same way (an empty secret is the failure this guards)
    assert r.returncode == 2 and "NOUS_API_KEY" in r.stderr, (r.returncode, r.stderr)


def test_a_present_key_passes_and_is_never_printed():
    # Given the key set to a sentinel
    r = _run(_clean_env(NOUS_API_KEY=SENTINEL), "NOUS_API_KEY")

    # Then  it passes, names the variable, and the value appears nowhere
    assert r.returncode == 0, r.stderr
    assert "NOUS_API_KEY" in r.stdout
    assert SENTINEL not in (r.stdout + r.stderr), "the guard printed the value"


def test_only_the_first_missing_key_is_reported_by_name():
    # Given one of two keys missing
    r = _run(_clean_env(NOUS_API_KEY=SENTINEL), "NOUS_API_KEY", "TYPESAFE_API_KEY")

    # Then  the missing one is named (and the present one is not reported as missing)
    assert r.returncode == 2 and "TYPESAFE_API_KEY" in r.stderr, r.stderr
    assert "NOUS_API_KEY is missing" not in r.stderr


def test_a_name_that_is_not_a_variable_is_refused():
    r = _run(_clean_env(), "not-a-name")
    assert r.returncode == 2 and "not a variable name" in r.stderr, r.stderr


# ---------------------------------------------------------------------------
# the wiring: every agent leg, guard before the image pull
# ---------------------------------------------------------------------------
def test_every_agent_leg_guards_before_it_pulls_the_image():
    recipes = _recipes()

    # Given every target that starts the agent image
    legs = {t: b for t, b in recipes.items() if "$(AGENT_IMAGE)" in b}
    assert legs, "no make target starts the agent image — the Makefile changed shape"

    # Then  each runs the ONE guard, and it runs before the image is ensured
    for target, body in legs.items():
        assert "python3 scripts/require_env.py" in body, f"{target} spends the runner before it checks its key"
        guard_at = body.index("python3 scripts/require_env.py")
        pull_at = body.find("scripts/ci_images.py ensure agent")
        if pull_at != -1:
            assert guard_at < pull_at, f"{target} pulls the image before it checks its key"

    # And the guard is a real make target too (a human runs the same code path)
    assert re.search(r"(?m)^require-env:", MAKEFILE.read_text())


def test_the_guard_is_one_code_path():
    mk = MAKEFILE.read_text()

    # Then the old ad-hoc bash test is gone from both hermes-smoke recipes
    assert 'test -n "$$NOUS_API_KEY"' not in mk, "a second guard survived"
    assert mk.count("python3 scripts/require_env.py") >= 7, "fewer guards than agent legs"

    # And this suite is in the discovered unit suite (issue #393), so it runs in the gate
    assert "tests/test_require_env.py" in ut.select(REPO)
