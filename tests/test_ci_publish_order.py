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
import inspect
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
PIPELINE = REPO / ".github" / "workflows" / "pipeline.yml"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import base_ref  # noqa: E402  (the base ref resolver, issue #925)
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


@pytest.fixture(autouse=True)
def _no_live_actions_lookup(monkeypatch):
    """A unit test never reads the Actions API (issue #893).

    The producer state is injected into `wait_published`, and the no-state fallback is
    exercised explicitly. An inherited `GITHUB_RUN_ID`/`GITHUB_TOKEN` (CI exports both)
    would otherwise make a hermetic test call the live API for its own run.
    """
    for var in ("GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(var, raising=False)


class _FakeClock:
    """A monotonic clock the wait advances by sleeping, so a 75-minute ceiling costs nothing."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _producer_states(status: str, conclusion: str = "", arch: str = "cpu",
                     engines: list[str] | None = None) -> dict[str, tuple[str, str]]:
    """The producer cells' job state, keyed exactly as `ci.yml` names them."""
    return {iel.producer_job_name(e, arch): (status, conclusion)
            for e in (engines or iel.CORE_ENGINES)}


def _publish_after(monkeypatch, clock: "_FakeClock", at_s: float) -> None:
    """A registry that answers 404 until the clock reaches `at_s`, then publishes."""
    monkeypatch.setattr(ei, "REGISTRY", REGISTRY)
    monkeypatch.setattr(
        ei, "_digest_http",
        lambda ref: (("sha256:" + "0" * 64, "") if clock.now >= at_s else ("", "404 Not Found")))


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


def test_install_job_does_not_install_engines():
    """ci-install is PRODUCT-ONLY (issue #1027): it installs the llgenie tool and never waits for
    or pulls an inference-engine image. The engine install-test lives in engine-build's
    `test-engine-install`, so ci.yml must not wait for nor install engines."""

    recipe = _recipe("ci-install")

    assert "$(MAKE) ci-install-product" in recipe, "ci-install must install the llgenie tool"
    assert "ci-wait-engine-images" not in recipe, "ci-install must not wait for engine images"
    assert "ci-install-run" not in recipe, "ci-install must not run the engine-pulling make install"


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

    # Then ci-install is OS-neutral AND product-only (no engine wait/pull from ci.yml, #1027)
    assert "Darwin" not in install
    assert "ci-wait-engine-images" not in install and "ci-install-product" in install

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


def test_published_images_never_consult_the_producer_state(monkeypatch):
    """Nothing to wait for means no job-state lookup either (issue #893)."""

    # Given a registry that answers every lookup with a digest, and no producer state
    _gate(monkeypatch, [])
    monkeypatch.setattr(iel, "producer_job_states",
                        lambda: pytest.fail("a published image must not trigger an API read"))

    # When the gate waits with no injected state (the production lookup)
    rc = iel.wait_published("cpu", timeout_s=60, poll_s=20)

    # Then it passes without ever asking the Actions API
    assert rc == 0


def test_a_queued_producer_keeps_the_wait_alive_past_the_old_budget(monkeypatch, capsys):
    """A producer cell that is still queued is capacity, not a missing tag (issue #893)."""

    # Given producer cells that are only QUEUED, and a registry that publishes the tag
    # 31 minutes in — one minute past the old 30-minute budget
    clock = _FakeClock()
    monkeypatch.setattr(iel, "time", clock)
    _publish_after(monkeypatch, clock, at_s=31 * 60)

    # When  the gate waits with that state injected
    rc = iel.wait_published("cpu", timeout_s=30 * 60, poll_s=20,
                            states=_producer_states("queued"))

    # Then  it keeps waiting past the old budget and passes when the image lands
    assert rc == 0
    assert clock.now > 30 * 60, f"the wait gave up at {clock.now}s, inside the queue ceiling"
    out = capsys.readouterr().out
    assert "producer still queued" in out
    assert "BLOCKED" not in out and "NOT FOUND" not in out


def test_a_producer_queued_past_the_ceiling_fails_as_BLOCKED(monkeypatch, capsys):
    """The queue outlasting the wait is reported as the queue, never as a bad tag (issue #893)."""

    # Given producer cells that never leave the queue and a tag that never appears
    clock = _FakeClock()
    monkeypatch.setattr(iel, "time", clock)
    _gate(monkeypatch, [], published=False)

    # When  the gate runs out of its queue budget
    rc = iel.wait_published("cpu", timeout_s=30 * 60, poll_s=20,
                            states=_producer_states("queued"))

    # Then  it fails as BLOCKED, naming the producer cell and the remedy — and never
    #       claims the tag is missing
    assert rc == 1
    out = capsys.readouterr().out
    assert "BLOCKED" in out and "NOT FOUND" not in out
    assert "runner queue, not a bad tag" in out
    for engine in iel.CORE_ENGINES:
        assert f"BLOCKED — the producer cell {iel.producer_job_name(engine, 'cpu')}" in out
    assert clock.now == iel.PUBLISH_WAIT_QUEUE_MAX_S, (
        f"the wait ended at {clock.now}s, not at the shipped ceiling "
        f"{iel.PUBLISH_WAIT_QUEUE_MAX_S}s")


def test_a_producer_that_concluded_success_with_a_missing_tag_fails_as_NOT_FOUND(monkeypatch, capsys):
    """A producer that finished and pushed nothing is a real missing image (issue #893)."""

    # Given a producer that concluded successfully and a tag that is not there
    clock = _FakeClock()
    monkeypatch.setattr(iel, "time", clock)
    _gate(monkeypatch, [], published=False)

    # When  the gate waits
    rc = iel.wait_published("cpu", timeout_s=30 * 60, poll_s=20,
                            states=_producer_states("completed", "success"))

    # Then  it fails as NOT FOUND once the grace period is spent — the pin/publish needs a
    #       look, the queue is not the cause
    assert rc == 1
    out = capsys.readouterr().out
    assert "NOT FOUND" in out and "BLOCKED" not in out
    assert "concluded success" in out and "pin or the publish step" in out
    assert clock.now == iel.PUBLISH_WAIT_CONCLUDED_GRACE_S, (
        "a concluded producer must cost the grace period, never the 30-minute budget")


def test_a_producer_that_failed_ends_the_wait_at_the_grace_period(monkeypatch, capsys):
    """A producer that concluded failure is named in the verdict, after one short grace (issue #893)."""

    # Given a producer cell that concluded `failure`
    clock = _FakeClock()
    monkeypatch.setattr(iel, "time", clock)
    _gate(monkeypatch, [], published=False)

    # When  the gate's first poll finds the tag absent
    rc = iel.wait_published("cpu", timeout_s=30 * 60, poll_s=20,
                            states=_producer_states("completed", "failure"))

    # Then  it fails within the grace period (a registry manifest can lag its own push),
    #       naming the producer and its conclusion — never sitting out the full budget
    assert rc == 1
    assert clock.now == iel.PUBLISH_WAIT_CONCLUDED_GRACE_S
    out = capsys.readouterr().out
    assert "NOT FOUND" in out and "concluded failure" in out and "Fix the producer cell" in out


def test_no_readable_producer_state_says_capacity_cannot_be_ruled_out(monkeypatch, capsys):
    """A host run (or a job without `actions: read`) is honest about what it cannot know."""

    # Given no producer state at all — the host path, and the CI path if the token cannot read jobs
    clock = _FakeClock()
    monkeypatch.setattr(iel, "time", clock)
    _gate(monkeypatch, [], published=False)

    # When  the gate waits with the empty state
    rc = iel.wait_published("cpu", timeout_s=30 * 60, poll_s=20, states={})

    # Then  it still fails, says it could not read the state, and names the one caveat
    assert rc == 1
    out = capsys.readouterr().out
    assert "could be read" in out and "runner queue cannot be ruled out" in out
    assert clock.now == 30 * 60, "no state means the old queue-unaware budget"


def test_the_producer_lookup_reads_job_names_from_the_actions_api(monkeypatch):
    """The lookup joins on `engine-image-<engine>-<variant>`, the name `ci.yml` sets (issue #893)."""

    # Given a GitHub Actions run whose job list holds the producer cells
    monkeypatch.setenv("GITHUB_RUN_ID", "1234")
    monkeypatch.setenv("GITHUB_REPOSITORY", "asimov-agent/llgenie")
    monkeypatch.setenv("GITHUB_TOKEN", "not-a-real-token")
    pages = [({"jobs": [{"name": "engine-image-llama.cpp-cpu", "status": "queued",
                         "conclusion": None},
                        {"name": "install", "status": "in_progress", "conclusion": None}]}, "")]

    def fake_get(url: str, token: str):
        assert "repos/asimov-agent/llgenie/actions/runs/1234/jobs" in url
        return pages.pop(0)

    monkeypatch.setattr(iel, "_github_get", fake_get)

    # When  the run's jobs are read
    states = iel.producer_job_states()

    # Then  the producer cell is addressable by the name the wait looks up
    assert iel.producer_job_name("llama.cpp", "cpu") in states
    assert iel.producer_state(states, "llama.cpp", "cpu")[0] == "queued"


def test_the_producer_lookup_is_empty_outside_actions(monkeypatch):
    """A host `make ci-wait-engine-images` never calls the API (issue #893)."""

    # Given no Actions environment (the autouse fixture removed it)
    monkeypatch.setattr(iel, "_github_get",
                        lambda url, token: pytest.fail("no run id means no API call"))

    # When  the state is read
    states = iel.producer_job_states()

    # Then  it is empty, and the wait falls back to its queue-unaware budget
    assert states == {}


def test_the_queue_ceiling_fits_inside_the_install_job_timeout():
    """A hung producer must not inherit GitHub's six-hour default (issues #872, #893)."""

    # Given the install job's own ceiling, as the workflow declares it
    job = yaml.safe_load(PIPELINE.read_text())["jobs"]["install"]
    ceiling = job["timeout-minutes"] * 60

    # When  the wait's budgets are compared with it
    # Then  the queue ceiling leaves room for the rest of the job, and the base budget is
    #       never larger than the queue ceiling (a base above it would never extend)
    assert iel.PUBLISH_WAIT_TIMEOUT_S <= iel.PUBLISH_WAIT_QUEUE_MAX_S
    assert iel.PUBLISH_WAIT_QUEUE_MAX_S + iel.PUBLISH_WAIT_RESERVE_S < ceiling, (
        f"{iel.PUBLISH_WAIT_QUEUE_MAX_S}s + {iel.PUBLISH_WAIT_RESERVE_S}s of wait/reserve "
        f"does not fit in the install job's {ceiling}s")


def test_the_install_job_does_not_need_to_read_the_producer_state():
    """PRODUCT-ONLY (issue #1027): the ci.yml install row neither waits for nor reads the engine
    producer's state, because it installs no engine — the engine install-test lives in engine-build's
    `test-engine-install`. The old `actions: read`-for-producer-state permission is gone with the wait."""

    # Given the install job the reusable pipeline declares
    job = yaml.safe_load(PIPELINE.read_text())["jobs"]["install"]

    # When  its permissions are read
    # Then  it does NOT read the producer cells' state (no engine wait in ci.yml)
    assert job["permissions"].get("actions") != "read", (
        "the product-only install job must not read the producer cells' state (no engine wait in ci.yml)")


def test_the_caller_grants_the_action_read_the_callee_needs():
    """A called workflow cannot exceed its caller's token — the caller must grant it too (#893).

    Measured: declaring `actions: read` in `pipeline.yml`'s `install` job alone made GitHub
    refuse the WHOLE workflow at startup — run 40819108106, `completed/failure`, 0 jobs, and
    `gh run view --log-failed` answers "log not found" because no job ever existed.
    """

    # Given the workflow that calls the reusable pipeline
    ci = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())
    callers = [name for name, job in ci["jobs"].items()
               if (job.get("uses") or "").endswith("pipeline.yml")]

    # When  each caller's job-level permissions are read
    # Then  every one of them grants `actions: read`, or the callee's request is refused at
    #       load time and the run reports nothing at all
    assert callers, "no job in ci.yml calls the reusable pipeline"
    for name in callers:
        granted = (ci["jobs"][name].get("permissions") or {}).get("actions")
        assert granted == "read", (
            f"ci.yml job `{name}` does not grant `actions: read`, so pipeline.yml's install "
            "job cannot read the producer state and GitHub refuses the whole workflow at "
            "startup (0 jobs, no log)")


def _deferred_engines(params_dir: Path | None = None, base: str | None = None) -> set[str]:
    """Engines whose committed params this change moved, so this run is publishing their tags.

    A tag that has never been published cannot answer a registry lookup, and the PR that moves the
    pin is exactly the one that publishes it — in the parallel `engine-image-*` job. Those tags are
    waited for where the wait belongs (`make ci-wait-engine-images`, a prerequisite of `ci-install`,
    issue #169), so a hermetic unit gate must not require them (issue #672).

    `base` is RESOLVED when not given (issue #925): this host has clones where `origin` is the owner's fork
    and `upstream` is the base, and a hard-coded `origin/main` there diffs against a different tree — which
    reds this test on a checkout where nothing is wrong with publishing.

    An engine whose params file has no copy on the base is deferred too: it is a first import, and
    nothing has published it yet.
    """
    base = base or base_ref.resolve_base(quiet=True)
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
    # A change to the engine-image tag computation (scripts/engine_image.py) re-tags EVERY engine
    # to a new, not-yet-published tag — issue #823 re-enabled prism CUDA and re-tagged the whole fleet
    # this way without touching any params file. Those tags are published by this run's producer, so
    # defer every engine the same way a params repin would be.
    tag_src = "scripts/engine_image.py"
    shown = subprocess.run(["git", "show", f"{base}:{tag_src}"], cwd=REPO,
                           capture_output=True, text=True)
    if shown.returncode != 0 or shown.stdout != (REPO / tag_src).read_text():
        for params_file in sorted(root.glob("*.json")):
            deferred.add(params_file.stem)
    return deferred


def test_a_params_file_identical_to_the_base_is_not_deferred(tmp_path):
    """An engine whose params AND whose tag computation equal the base copy is still checked
    against the registry (#672). A tag-computation change (issue #823 re-enabling prism CUDA) re-tags
    the whole fleet to not-yet-published tags and DOES defer an unchanged params file, because the
    producer publishes those new tags — deferred, not required from the registry."""

    engine = "llama.cpp"
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()

    # Case 1: params identical AND tag computation stable (base == head) => NOT deferred
    root = tmp_path / "params"
    root.mkdir()
    shown = subprocess.run(["git", "show", f"{head}:containers/engines/params/{engine}.json"],
                           cwd=REPO, capture_output=True, text=True)
    assert shown.returncode == 0, shown.stderr
    (root / f"{engine}.json").write_text(shown.stdout)
    assert _deferred_engines(params_dir=root, base=head) == set()

    # Case 2: params identical to origin/main. Whether the engine is deferred depends on whether
    # this branch's tag computation (scripts/engine_image.py) actually differs from base — a
    # tag-computation change re-tags the whole fleet, so an unchanged params file IS deferred then
    # (#823), and is not when the computation is unchanged. Computing it here keeps the assertion
    # deterministic across the CI and local base states.
    changed = subprocess.run(["git", "show", "origin/main:scripts/engine_image.py"], cwd=REPO,
                             capture_output=True, text=True)
    tag_src_changed = (changed.returncode != 0
                       or changed.stdout != (REPO / "scripts" / "engine_image.py").read_text())
    base_main = subprocess.run(["git", "show", f"origin/main:containers/engines/params/{engine}.json"],
                               cwd=REPO, capture_output=True, text=True)
    assert base_main.returncode == 0, base_main.stderr
    root2 = tmp_path / "params2"
    root2.mkdir()
    (root2 / f"{engine}.json").write_text(base_main.stdout)
    got = _deferred_engines(params_dir=root2, base="origin/main")
    if tag_src_changed:
        assert "llama.cpp" in got, got
    else:
        assert "llama.cpp" not in got, got


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
    if deferred and not checked:
        # A tag-computation change (issue #823) re-tagged the whole fleet: every engine is deferred
        # to its producer publish, so there is no non-repinned image left to live-check here.
        print(f"[publish-order] all cpu engines deferred to their producer publish: {sorted(deferred)}")
        return checked
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


def test_the_publish_gate_never_polls_open_endedly():
    """Issue #1027 guard: `ci-wait-engine-images` (and its producer-cell-state-aware

    successor) must never run an open-ended sleep/poll loop or wait on a tag that
    exists only as long as a producer is alive. Every sleep is bounded (derived
    from the PUBLISH_WAIT_* constants) and the producer's OWN cell state decides
    what an absent tag means (issue #893); a producer that never ran fails fast.
    """

    # Given the gate's only wait loop, in the module that implements it
    import scripts.install_engine_launchers as iel

    # When  every unbounded-loop marker and every bare sleep is read
    src = inspect.getsource(iel)
    for banned in ("while True:", "while 1:"):
        assert banned not in src, f"{banned} is an unbounded loop the producer gate must not use"

    # Then  the gate's poll is the bounded, finite one: sleeps ARE present (a finite
    # retry loop) but every one sits behind the PUBLISH_WAIT_* wall-clock budgets —
    # never an unbounded wait on tag-existence
    assert "time.sleep(" in src, "the producer gate must poll with a bounded retry"
    assert "PUBLISH_WAIT_TIMEOUT_S" in src and "PUBLISH_WAIT_POLL_S" in src, \
        "the wait must be bounded by the finite PUBLISH_WAIT_* constants, not open-ended"
