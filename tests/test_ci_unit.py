"""#800: the `ci-unit` gate sequence is a tested module, not 49 inline `$(MAKE)` lines.

The old recipe was the project's longest gate — 49 `$(MAKE) <target>` lines that decided what the
whole hermetic unit gate runs, unreachable by any unit test. `scripts/ci_unit.py` names the SAME
sequence in order and runs each step exactly like the recipe did, stopping at the FIRST failure and
exiting with that step's status. These tests prove the module's behaviour and that the recipe is
wired to it (each <= 3 lines, its logic in the tested module).
"""

from __future__ import annotations

import os
from pathlib import Path

import scripts.ci_unit as ci_unit  # noqa: E402  (same import seam as a sibling hermetic test)


def _stub_make(root: Path, fail_at: str | None) -> Path:
    """Write a fake `make` onto PATH that records the steps it is asked to run.

    Each invocation appends the requested target (first token — a step may carry extra args like
    `skills-validate REGISTRY=...`) to `root/called.txt`, then exits 1 when the target equals
    `fail_at` and 0 otherwise. This lets the test observe order and stop-at-failure precisely.
    """
    body = (
        "#!/usr/bin/env bash\n"
        "set -u\n"
        f'echo "$1" >> {root}/called.txt\n'
        f'if [ "$1" = "{fail_at}" ]; then exit 1; fi\n'
        "exit 0\n"
    )
    stub = root / "bin" / "make"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(body)
    stub.chmod(0o755)
    return root / "bin"


def _patched_env(bindir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env.get('PATH', '')}"
    return env


def test_ci_unit_runs_every_step_in_recipe_order(tmp_path):
    """Every step in the module's STEPS list is invoked, in order, via `make`."""

    # Given a stub make that records each requested target in order
    bindir = _stub_make(tmp_path, fail_at=None)

    # When the ci-unit sequence runs
    rc = ci_unit.run(root=tmp_path, env=_patched_env(bindir))

    # Then it returns 0 and every step was invoked, first token of each equals the target name
    assert rc == 0
    called = (tmp_path / "called.txt").read_text().splitlines()
    expected = [s.split()[0] for s in ci_unit.STEPS]
    assert called == expected


def test_ci_unit_stops_at_the_first_failure_and_returns_its_status(tmp_path):
    """A failing step aborts the sequence with that step's exit code (the old recipe's contract)."""

    # Given a stub make that fails when asked to run `check-registry`
    fail_step = "check-registry"
    bindir = _stub_make(tmp_path, fail_at=fail_step)

    # When the sequence runs past the failing step
    rc = ci_unit.run(root=tmp_path, env=_patched_env(bindir))

    # Then it stops at the first failure (returns its code 1) and never reaches later steps
    assert rc == 1
    called = (tmp_path / "called.txt").read_text().splitlines()
    expected = [s.split()[0] for s in ci_unit.STEPS]
    assert called == expected[: expected.index(fail_step) + 1]


def test_ci_unit_recipe_is_wired_and_three_lines_max():
    """The `ci-unit` recipe is `python3 scripts/ci_unit.py`, not 49 inline `$(MAKE)`s."""

    # Given the committed recipe text in mk/ci.mk
    mk_ci = Path(__file__).resolve().parent.parent / "mk" / "ci.mk"
    lines = mk_ci.read_text().splitlines()
    idx = next(i for i, l in enumerate(lines) if l.startswith("ci-unit:"))
    recipe = []
    for l in lines[idx + 1 :]:
        if l.startswith("\t"):
            recipe.append(l.strip())
        else:
            break

    # When we measure it
    # Then it is at most 3 recipe lines, names the script entry point, and carries no inline $(MAKE)
    assert len(recipe) <= 3
    assert any("scripts/ci_unit.py" in line for line in recipe)
    assert not any("$(MAKE)" in line for line in recipe)
