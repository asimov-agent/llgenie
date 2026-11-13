#!/usr/bin/env python3
"""The compile inputs state the versions the repository runs, and the scan's floors are compiled (issue #754).

The daily security scan (run 40537601445) exits 1 because `certifi`, `filelock` and `urllib3` were
compiled at versions an advisory names as vulnerable, and nothing in the repository could move them:
they reach `tools/requirements*.txt` transitively, and `tools/requirements.in` stated no version at
all for `numpy` / `huggingface_hub[cli]`. This suite locks the shape that fixes it:

* every DIRECT runtime dependency in `tools/requirements.in` is pinned exactly (`==`), so the version
  that runs is the repository's choice, not a resolver side effect;
* every package the scan reports carries its report `fixed` version as a `>=` floor, annotated with
  the advisory identifier, in both compile inputs;
* no compiled pin sits below a stated floor — in the runtime file and in the dev file, which the
  test image installs alongside it;
* the compiled files keep the generator's header (they are generated, never hand-edited).

Hermetic: it reads the four files, so `make test-unit` needs no venv, no network and no scanner.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"
RUNTIME_IN = TOOLS / "requirements.in"
DEV_IN = TOOLS / "requirements-dev.in"
RUNTIME_TXT = TOOLS / "requirements.txt"
DEV_TXT = TOOLS / "requirements-dev.txt"

#: The advisories run 40537601445 reported, with the `fixed` version its own report names.
SCANNED_FLOORS = {
    "certifi": ("2026.10.18", ("GHSA-6q48-6c7w-9gw2",)),
    "filelock": ("4.2.1", ("CVE-2026-112940",)),
    "urllib3": ("2.8.0", ("CVE-2026-97687", "CVE-2026-97689")),
}

_LINE = re.compile(r"^\s*(?P<name>[A-Za-z0-9_.-]+)(?P<extras>\[[^\]]+\])?\s*(?P<spec>[<>=!~][^#\s]*)?\s*(?:#\s*(?P<comment>.*))?$")


def _requirements(path: Path) -> list[dict[str, str]]:
    """Every requirement line in a `.in`/`.txt` file, comments and options skipped."""

    out: list[dict[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = _LINE.match(line)
        if match:
            out.append(
                {
                    "name": match.group("name").lower(),
                    "spec": (match.group("spec") or "").strip(),
                    "comment": (match.group("comment") or "").strip(),
                    "raw": line,
                }
            )
    return out


def _pins(path: Path) -> dict[str, str]:
    """`{package: version}` for a compiled file's `==` pins."""

    pins: dict[str, str] = {}
    for item in _requirements(path):
        if item["spec"].startswith("=="):
            pins[item["name"]] = item["spec"][2:]
    return pins


def _version_key(text: str) -> tuple:
    def part(token: str) -> tuple[int, int, str]:
        return (1, int(token), "") if token.isdigit() else (0, 0, token.lower())

    return tuple(part(p) for p in re.split(r"[.\-_+]", str(text)) if p)


def test_every_direct_runtime_dependency_is_pinned_exactly() -> None:
    """A version the resolver chose is not a version the repository states."""

    # Given the runtime compile input
    items = _requirements(RUNTIME_IN)

    # When  its direct requirement lines are read
    # Then  each is either an exact `==` pin, or a floor that names the advisory demanding it
    assert items, "tools/requirements.in states no requirement"
    for item in items:
        if item["spec"].startswith("=="):
            continue
        assert item["spec"].startswith(">=") and re.search(r"(GHSA|CVE)-\S+", item["comment"]), (
            f"unpinned direct dependency with no advisory floor: {item['raw']}"
        )

    # And   the three the repository actually imports are named exactly
    pinned = {item["name"]: item["spec"] for item in items}
    assert pinned["numpy"] == "==2.4.6"
    assert pinned["gguf"] == "==0.19.0"
    assert pinned["huggingface_hub"] == "==1.30.0"


def test_scanned_packages_carry_an_annotated_floor() -> None:
    """Each advisory's own `fixed` version is a floored, annotated requirement."""

    # Given the scan's findings (its report's `fixed` value per package)
    for source in (RUNTIME_IN, DEV_IN):
        items = {item["name"]: item for item in _requirements(source)}

        # When  the compile input is read for the scanned packages
        for package, (floor, advisories) in SCANNED_FLOORS.items():
            item = items.get(package)

            # Then  the floor is stated, at exactly the report's version, and names its advisory
            assert item is not None, f"{source.name}: {package} states no floor"
            assert item["spec"] == f">={floor}", f"{source.name}: {package} is {item['spec']!r}, want >={floor}"
            for advisory in advisories:
                assert advisory in item["comment"], (
                    f"{source.name}: {package} floor does not name {advisory} in its comment"
                )


def test_compiled_pins_are_at_or_above_every_floor() -> None:
    """Both compiled files resolve at or above the floor the scanner demands."""

    # Given the two compiled files the test image installs together
    for compiled in (RUNTIME_TXT, DEV_TXT):
        pins = _pins(compiled)

        # When  each floored package's compiled pin is compared with its floor
        for package, (floor, advisories) in SCANNED_FLOORS.items():
            held = pins.get(package)

            # Then  no compiled pin sits below it
            assert held is not None, f"{compiled.name}: {package} is not compiled at all"
            assert _version_key(held) >= _version_key(floor), (
                f"{compiled.name}: {package}=={held} is below the floor {floor} "
                f"({', '.join(advisories)})"
            )


def test_compiled_files_keep_the_generator_header() -> None:
    """A compiled pin arrives through pip-compile, never a hand edit."""

    # Given the two committed compiled files
    for compiled in (RUNTIME_TXT, DEV_TXT):
        text = compiled.read_text(encoding="utf-8")

        # When  the file's own header is read
        # Then  it says pip-compile generated it
        assert "autogenerated by pip-compile" in text, f"{compiled.name} lost the generator header"


def test_the_ci_hf_downloader_installs_the_pinned_spec_through_make() -> None:
    """engine-build provisions `hf` from the lock via a make target, never a floating inline install (issue #2380).

    Run 42558839616: `uv tool install "huggingface_hub[cli]>=0.30"` resolved 2.4.0, whose `cli`
    extra was removed — the step silently provisioned a downloader the lock does not name.
    """

    # Given the workflow and the Makefile that must now share one pin source
    workflow = (REPO_ROOT / ".github" / "workflows" / "engine-build.yml").read_text(encoding="utf-8")
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    # When  the hf provisioning step is read
    parts = workflow.split('- name: "hf CLI (tiny test model)', 1)
    assert len(parts) == 2, "engine-build.yml lost its hf CLI step"
    step_body = parts[1].split("- name:", 1)[0]

    # Then  the step routes through the make target and no inline uv install survives
    assert "run: make hf-cli-install" in step_body, f"hf CLI step bypasses the make target: {step_body!r}"
    assert "uv tool install" not in workflow, "engine-build.yml installs a Python tool inline again"

    # And   the target reads the exact pinned spec out of the compile input
    recipe_parts = makefile.split("hf-cli-install:", 1)
    assert len(recipe_parts) == 2, "the hf-cli-install target is gone from the Makefile"
    recipe = recipe_parts[1].split("\n\n", 1)[0]
    assert "grep '^huggingface_hub==[0-9]' tools/requirements.in" in recipe, (
        "hf-cli-install does not resolve the spec from tools/requirements.in"
    )
    assert 'uv tool install "$$spec"' in recipe, "hf-cli-install does not install the resolved spec"

    # And   the stale `[cli]` extra is gone from the compile inputs: current
    # huggingface_hub ships `hf` in the base package and the extra only warns
    req_lines = [
        line for line in RUNTIME_IN.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert not any("[cli]" in line for line in req_lines), (
        "requirements.in still requests the dropped cli extra on a requirement line"
    )
    assert "[cli]" not in RUNTIME_TXT.read_text(encoding="utf-8"), "requirements.txt still carries the dropped cli extra"
