"""Every pytest in a make recipe runs in the test image (or the dev venv) — never on a bare host python.

Issue #621: `make test-published-engine` called `python3 -m pytest tests/test_published_engine_binary.py`
as a HOST command. The GitHub runner has a `python3` and no pytest, so the step could only ever fail with
`/usr/bin/python3: No module named pytest` — and because the published matrix was empty at the time, no run
exercised it until `engine-build` (#616) re-populated the rows. Every other test stage in the repo runs
through one of two seams: `$(TEST_RUN)` (the test image in CI, the venv on a dev host) or
`$(call engine_test,…)` (the test image with the engine's env). This test keeps the next recipe honest.

No product code is involved: the Makefile is the artifact, and the assertion is on its text.
"""
from __future__ import annotations

import re

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def makefiles_text() -> str:
    """The top Makefile + every `mk/*.mk` it `include`s, joined (issue #800 split).

    The 2,083-line Makefile split its targets into `mk/{engines,gates,ci,security,bots,install}.mk`,
    so the pytest recipe lines this seam guards now live behind the includes. Read the concatenation
    the way the build resolves it — a pytest invocation that moved still has to use a seam.
    """
    top = (REPO / "Makefile").read_text()
    body = [top]
    for m in re.finditer(r"^\s*include\s+(\S+)(?:\s+#.*)?\s*$", top, re.M):
        inc = m.group(1)
        if "*" in inc:
            for p in sorted(pp for pp in REPO.glob(inc) if pp.is_file()):
                body.append(p.read_text())
        else:
            p = REPO / inc
            if p.is_file():
                body.append(p.read_text())
    return "\n\n".join(body)


MAKEFILE_TEXT = makefiles_text()

#: The seams a test command may run through. `$(TEST_RUN)` and `$(ENGINE_TEST_RUN)` resolve to the test
#: image in CI and to the venv on a dev host; `$(call engine_test,…)` builds the same container command with
#: the engine's env; the literal image name catches a hand-written `docker run … llgenie/test:latest`.
SEAMS = ("$(TEST_RUN)", "$(ENGINE_TEST_RUN)", "$(call engine_test,", "llgenie/test:latest",
         # the host-side seams: `$(PY)` / `$(VENV_GUARD)` / `$(NATIVE_GUARD)` are the gguf venv's interpreter,
         # which carries pytest — the venv IS the seam on a dev host (and on the macOS native-engine targets,
         # which never run in CI's Linux test image)
         "$(PY)", "$(VENV_GUARD)", "$(NATIVE_GUARD)")

#: A target header, e.g. `test-published-engine:` (not a variable assignment, not a `.PHONY` list).
_TARGET = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*):")


def _logical_recipe_lines(text: str) -> list[tuple[str, str]]:
    """(target, the command) for every recipe line, with `\\` continuations joined.

    Comments are skipped — a recipe's `#` line is documentation, and this rule is about commands.
    """
    out: list[tuple[str, str]] = []
    target = ""
    pending = ""
    for raw in text.splitlines():
        if _TARGET.match(raw) and not raw.startswith("\t"):
            target = _TARGET.match(raw).group(1)  # type: ignore[union-attr]
            pending = ""
            continue
        if not raw.startswith("\t"):
            continue
        line = raw.strip()
        if line.startswith("#"):
            continue
        pending = f"{pending} {line}".strip() if pending else line
        if pending.endswith("\\"):
            pending = pending[:-1].strip()
            continue
        out.append((target, pending))
        pending = ""
    if pending:
        out.append((target, pending))
    return out


#: A pytest invocation in a RECIPE: `python3 -m pytest`, `python -m pytest`, or a bare `pytest …` command.
#: A venv interpreter (`.../bin/python -m pytest`) carries pytest itself, so it is a seam in its own right.
_PYTEST = re.compile(r"(?:\bpython3? -m pytest\b)|(?:^pytest\b)|(?:\bpytest \S)")
_VENV_PY = re.compile(r"/bin/python3?[\"']?\s+-m pytest\b")


def offenders(text: str) -> list[tuple[str, str]]:
    """(target, command) for every recipe line that runs pytest without a seam that provides it.

    Exposed so the rule can be proved on a synthetic Makefile, not only on today's file (a Makefile that
    happens to be clean says nothing about whether the rule works).
    """
    bad: list[tuple[str, str]] = []
    for target, command in _logical_recipe_lines(text):
        if not _PYTEST.search(command):
            continue
        if any(seam in command for seam in SEAMS) or _VENV_PY.search(command):
            continue
        bad.append((target, command))
    return bad


def test_every_pytest_in_a_make_recipe_runs_through_the_test_seam():
    """A recipe that needs pytest must get it from the test image (or the venv), never from the host."""

    # Given every recipe line in the makefiles, continuations joined
    recipes = _logical_recipe_lines(MAKEFILE_TEXT)

    # When  the lines that run pytest are read
    pytest_lines = [(t, c) for t, c in recipes if _PYTEST.search(c)]

    # Then  there is more than one (the suite is driven from several targets) …
    assert pytest_lines, "no pytest invocation found in the makefiles: the parser or the targets changed"

    # And  every single one runs through a seam that provides pytest
    bad = offenders(MAKEFILE_TEXT)
    assert not bad, (
        "a make recipe runs pytest on a bare host python (issue #621 — the runner has no pytest):\n"
        + "\n".join(f"  {t}: {c}" for t, c in bad)
    )

    # And  the target that failed, specifically, is the one that carries the published-image env
    published = [c for t, c in recipes if t == "test-published-engine" and "pytest" in c]
    assert published, "test-published-engine no longer runs its pytest"
    assert any("$(call engine_test," in c and "LLGENIE_PUBLISHED_PULLED=1" in c for c in published), \
        f"test-published-engine must pass its env into the test image, got: {published}"


def test_a_bare_pytest_line_is_caught_and_a_venv_interpreter_is_not():
    """The rule itself, on a synthetic Makefile: a bare `pytest` fails, a venv python passes.

    Today's Makefile is clean, which proves nothing about the rule — this pins both directions, including
    the `pytest tests/…` spelling that has no `python -m` in it at all.
    """

    # Given a Makefile with one bare `pytest` recipe and one that uses the venv's python
    sample = (
        "host-call:\n"
        "\tpytest -q tests/test_thing.py\n"
        "\n"
        "container-call:\n"
        "\t$(TEST_RUN) python3 -m pytest -q tests/test_thing.py\n"
        "\n"
        "venv-call:\n"
        "\t\"$(AGENTS_READ_VENV)/bin/python\" -m pytest tests/test_agents_read.py -q\n"
    )

    # When  the rule reads it
    bad = offenders(sample)

    # Then  only the bare host call is reported, and it is reported with its target
    assert [t for t, _ in bad] == ["host-call"], bad
    assert "pytest -q tests/test_thing.py" in bad[0][1]
