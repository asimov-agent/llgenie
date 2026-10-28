"""The install job waits for the images it pulls (issue #169).

A bump PR builds and publishes its engine images in the parallel `engine-image-*`
jobs, but `pipeline.yml`'s `install` job needs only `ci-images` and used to pull
the brand-new tag before any job had pushed it:

    [install] FAIL llama.cpp/cpu: not published in ghcr.io/asimov-agent

`make ci-wait-engine-images` is the gate: it resolves exactly the tags `install`
pulls and polls the registry manifest until each one exists, failing loudly on a
tag that never appears. Hermetic tests drive the gate with a stubbed manifest
lookup; the last test hits the real registry with no mock.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
PIPELINE = REPO / ".github" / "workflows" / "pipeline.yml"
sys.path.insert(0, str(REPO))

import scripts.install_engine_launchers as iel  # noqa: E402

# `install_engine_launchers` imports its sibling as the top-level `engine_image`;
# patch THAT module object, or the gate keeps calling the unpatched one.
ei = iel.ei

REGISTRY = "ghcr.io/asimov-agent"


def _install_steps() -> list[str]:
    """The `run:` commands of the reusable pipeline's install job, in step order."""
    wf = yaml.safe_load(PIPELINE.read_text())
    steps = wf["jobs"]["install"]["steps"]
    return [s.get("run", "") for s in steps]


def _gate(monkeypatch, log: list[str], published: bool = True):
    """Point the gate's manifest lookup at a fake registry and log every ref it looked up."""
    monkeypatch.setattr(ei, "REGISTRY", REGISTRY)

    def fake(ref: str) -> tuple[str, str]:
        log.append(ref)
        return ("sha256:" + "0" * 64, "") if published else ("", "404 Not Found")

    monkeypatch.setattr(ei, "_digest_http", fake)


def _recipe(target: str) -> str:
    """One Makefile target's recipe, exactly as `make <target>` runs it."""
    return (REPO / "Makefile").read_text().split(f"\n{target}:", 1)[1].split("\n\n", 1)[0]


def _install_ci_targets() -> list[str]:
    """The `make ci-<job>` targets the install job runs, in step order.

    `ci-free-disk` is a disk helper, not a job target (same exclusion as
    `tests/test_ci_images.py::_make_targets`).
    """
    found: list[str] = []
    for run in _install_steps():
        found += re.findall(r"make (ci-[a-z0-9-]+)", run)
    return [t for t in found if t != "ci-free-disk"]


def test_install_job_waits_before_it_installs():
    """ci-install waits for the images it pulls before it runs make install."""

    # Given the ci-install recipe the install job runs
    recipe = _recipe("ci-install")

    # When the wait and the install are located in recipe order
    wait = recipe.find("$(MAKE) ci-wait-engine-images")
    run = recipe.find("$(MAKE) ci-install-run")

    # Then the gate is in the recipe and strictly before make install
    assert wait != -1, "ci-install has no make ci-wait-engine-images"
    assert run != -1, "ci-install has no make ci-install-run"
    assert wait < run, f"wait at {wait} must precede ci-install-run at {run}"


def test_the_install_job_runs_one_make_target():
    """The gate is a make prerequisite, so the job still runs exactly one ci-<job> target."""

    # Given the install job's run: steps
    targets = _install_ci_targets()

    # Then ci-install is the only ci target, and no ci-wait step sits beside it
    assert targets == ["ci-install"], targets
    assert "ci-wait-engine-images" not in targets


def test_the_install_target_keeps_its_darwin_branch_for_host_use():
    """CI no longer runs macOS (#870), but `make ci-install` still works on a Mac host.

    The Darwin branch in the gate target is for a developer running the target locally, not for a CI
    row - so it stays, and with no macOS caller in `ci.yml` nothing in CI exercises it.
    """

    # Given ci-install's recipe and the gate target's recipe
    install, gate = _recipe("ci-install"), _recipe("ci-wait-engine-images")

    # Then ci-install is OS-neutral: the same targets on both OSes, no Darwin branch
    assert "Darwin" not in install
    assert "$(MAKE) ci-wait-engine-images ARCH=cpu" in install

    # And only the gate target branches on the OS, with the registry lookup on Linux
    assert "ifeq ($(HOST_OS),Darwin)" in gate
    darwin, linux = gate.split("\nelse\n", 1)
    assert "--wait-published" not in darwin
    assert "--wait-published" in linux

    # And the gate is defined AFTER `HOST_OS := $(shell uname -s)`: make evaluates ifeq
    # while it parses the file, so a conditional placed earlier sees an empty HOST_OS and
    # would take the Linux branch on macOS too
    mk = (REPO / "Makefile").read_text()
    assert mk.find("HOST_OS := $(shell uname -s)") < mk.find("\nci-wait-engine-images:")


def test_the_gate_waits_for_exactly_what_install_pulls(monkeypatch, tmp_path):
    """The gate cannot wait for an image install would not pull, nor skip one it would."""

    # Given a registry that answers every lookup as published
    refs: list[str] = []
    pulled: list[tuple[str, str]] = []
    _gate(monkeypatch, refs)
    monkeypatch.setattr(ei, "image_platform", lambda tag: "linux/amd64")

    def fake_ensure(engine: str, variant: str, build: bool) -> str:
        pulled.append((engine, variant))
        return ei.resolve(engine, None, variant)["tag"]

    monkeypatch.setattr(iel, "ensure_image", fake_ensure)

    # When the gate waits, and install resolves its images
    assert iel.wait_published("cpu", timeout_s=5, poll_s=0) == 0
    assert iel.install(tmp_path / "bin", "cpu", build=False) == 0

    # Then the gate looked up exactly the refs install pulled
    want = [f"{REGISTRY}/{ei.resolve(e, None, v)['tag']}" for e, v in pulled]
    assert refs == want, f"gate waited for {refs}, install pulled {want}"


def test_a_never_published_tag_fails_loudly(monkeypatch, capsys):
    """A tag that never appears is a named failure, never a silent skip."""

    # Given a registry that answers every lookup with a 404
    _gate(monkeypatch, [], published=False)

    # When the gate waits and its deadline passes
    rc = iel.wait_published("cpu", timeout_s=0, poll_s=0)
    out = capsys.readouterr().out

    # Then it fails and names every tag that is still missing
    assert rc == 1
    for engine in iel.CORE_ENGINES:
        tag = ei.resolve(engine, None, "cpu")["tag"]
        assert f"{REGISTRY}/{tag}" in out
        assert f"FAIL {engine}/cpu" in out


def test_published_images_need_no_wait(monkeypatch):
    """An already published image is one lookup, not a retry budget."""

    # Given a registry that answers every lookup with a digest
    refs: list[str] = []
    monkeypatch.setattr(ei, "REGISTRY", REGISTRY)

    def published(ref: str) -> tuple[str, str]:
        refs.append(ref)
        return "sha256:" + "0" * 64, ""

    monkeypatch.setattr(ei, "_digest_http", published)

    # When the gate waits
    rc = iel.wait_published("cpu", timeout_s=60, poll_s=20)

    # Then it passes after a single pass over the tags
    assert rc == 0
    assert len(refs) == len(iel.CORE_ENGINES)


def _deferred_engines(params_dir: Path | None = None, base: str = "origin/main") -> set[str]:
    """Engines whose committed params this change moved, so this run is publishing their tags.

    A tag that has never been published cannot answer a registry lookup, and the PR that moves the
    pin is exactly the one that publishes it — in the parallel `engine-image-*` job. Those tags are
    waited for where the wait belongs (`make ci-wait-engine-images`, a prerequisite of `ci-install`,
    issue #169), so a hermetic unit gate must not require them (issue #672).

    An engine whose params file has no copy on the base is deferred too: it is a first import, and
    nothing has published it yet.
    """
    root = params_dir or (REPO / "containers" / "engines" / "params")
    deferred: set[str] = set()
    for params_file in sorted(root.glob("*.json")):
        rel = f"containers/engines/params/{params_file.name}"
        try:
            shown = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=REPO,
                                   capture_output=True, text=True)
        except OSError:                     # no git on PATH: nothing to compare against
            return set()
        if shown.returncode != 0:           # no base copy — the engine is new in this change
            deferred.add(params_file.stem)
        elif shown.stdout != params_file.read_text():
            deferred.add(params_file.stem)
    return deferred


def test_a_params_file_identical_to_the_base_is_not_deferred(tmp_path):
    """An engine whose params equal the base copy is still checked against the registry (#672)."""

    # Given a scratch params dir holding one engine's committed params verbatim from origin/main
    engine = "llama.cpp"
    base = subprocess.run(["git", "show", f"origin/main:containers/engines/params/{engine}.json"],
                          cwd=REPO, capture_output=True, text=True)
    assert base.returncode == 0, base.stderr
    root = tmp_path / "params"
    root.mkdir()
    (root / f"{engine}.json").write_text(base.stdout)

    # When  the deferred set is computed
    deferred = _deferred_engines(params_dir=root, base="origin/main")

    # Then  it is empty: an unchanged engine is never exempt from the registry assertion
    assert deferred == set(), deferred


def test_an_engine_with_no_base_copy_is_deferred(tmp_path):
    """A params file the base does not carry is a first import: nothing has published it yet."""

    # Given an engine whose params file exists only in this checkout
    root = tmp_path / "params"
    root.mkdir()
    (root / "brand-new-engine.json").write_text('{"id": "brand-new-engine"}')

    # When  the deferred set is computed
    deferred = _deferred_engines(params_dir=root, base="origin/main")

    # Then  that engine is deferred, never silently required from the registry
    assert deferred == {"brand-new-engine"}, deferred


def _assert_published(deferred: set[str]) -> list[str]:
    """Check the registry for every cpu image this change did not repin; return what was checked.

    The repinned engines are named in the output instead of looked up: their tags are published by
    this run's own `engine-image-*` job, and waited for by `make ci-wait-engine-images` — the gate
    that can wait (#169, #672).
    """
    plan = [e for e in iel.install_plan("cpu") if e["variant"]]
    assert plan, "install resolves no engine image for cpu"
    checked = [e["engine"] for e in plan if e["engine"] not in deferred]
    if deferred:
        print(f"[publish-order] deferred to ci-wait-engine-images: {sorted(deferred)}")
    assert checked, "the plan names no engine this change did not repin"
    rc = iel.wait_published("cpu", only=checked, timeout_s=120, poll_s=10)
    assert rc == 0, ("an image make install pulls and this change did not repin is not published "
                     "on GHCR (issue #169)")
    return checked


def test_a_bump_defers_its_own_new_tag_and_checks_the_rest(monkeypatch, capsys):
    """A bump PR defers only the engine it repins, and still checks every other engine."""

    # Given a checkout whose llama.cpp params differ from the base
    asked: list[str] = []

    def fake_wait(arch, only=None, timeout_s=None, poll_s=None):
        asked.extend(only or [])
        return 0

    monkeypatch.setattr(iel, "wait_published", fake_wait)

    # When  the registry case runs with that engine deferred
    checked = _assert_published({"llama.cpp"})

    # Then  llama.cpp is named as deferred, never looked up, and every other engine is checked
    out = capsys.readouterr().out
    assert "llama.cpp" in out and "ci-wait-engine-images" in out
    assert "llama.cpp" not in asked
    assert asked == checked
    plan = [e["engine"] for e in iel.install_plan("cpu") if e["variant"]]
    assert checked == [e for e in plan if e != "llama.cpp"], checked


def test_every_image_install_pulls_is_published():
    """Real registry, no mock: every image `make install` pulls is on GHCR.

    An engine this change repins is deferred: its tag is published by this run's own
    `engine-image-*` job and waited for by `make ci-wait-engine-images` (issue #169), which is the
    gate that can wait. Requiring it here reddened every bump PR (issue #672).
    """

    # Given the committed engine params and the cpu backend
    # When  the deferred set is computed from the real checkout against origin/main
    deferred = _deferred_engines()

    # Then  every image this change did not repin is published in the real registry
    _assert_published(deferred)
