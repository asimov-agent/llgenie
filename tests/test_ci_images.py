"""CI images on GHCR (issue #117): the test image and the OpenSpec CLI image are tagged by a
hash of their inputs, published once per hash by the `ci-images` job and PULLED by every
other CI job. macOS runs the pipeline's make targets in three Docker jobs instead of ten.

Hermetic: a fake `docker` on PATH logs every call; no registry, no build."""
from __future__ import annotations

import importlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WF = REPO / ".github" / "workflows"
sys.path.insert(0, str(REPO / "scripts"))


def _copy_inputs(root: Path) -> Path:
    for rel in ("containers/test/Dockerfile", "tools/requirements.txt", "tools/requirements-dev.txt",
                "openspec/Dockerfile"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, root / rel)
    return root


def _fake_docker(tmp: Path, published: bool) -> tuple[dict, Path]:
    """`docker` that logs its args (and the build context's files) and answers the registry
    lookup / pull with `published`."""
    log = tmp / "docker.log"
    rc = 0 if published else 1
    script = f'''#!/bin/sh
echo "$*" >> "{log}"
case "$1 $2" in
  "buildx imagetools") exit {rc} ;;
  "buildx build") for a in "$@"; do [ -d "$a" ] && ls "$a" | tr '\\n' ' ' | sed 's/^/CTX: /' >> "{log}" && echo >> "{log}"; done; exit 0 ;;
esac
case "$1" in
  pull) exit {rc} ;;
esac
exit 0
'''
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "docker").write_text(script)
    (bindir / "docker").chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "RUNTIME": "docker",
           "LLGENIE_REGISTRY": "ghcr.io/asimov-agent"}
    return env, log


def _ci_images(env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "ci_images.py"), *args],
                          env=env, capture_output=True, text=True, timeout=60)


def _calls(log: Path) -> list[str]:
    return log.read_text().splitlines() if log.exists() else []


# ---------------------------------------------------------------------------
# the tag
# ---------------------------------------------------------------------------
def test_tag_follows_the_image_inputs(tmp_path):
    """The tag is a hash of exactly the image's inputs."""
    import ci_images

    # Given a repo copy with the test image's Dockerfile and both lockfiles
    root = _copy_inputs(tmp_path)
    test_tag, openspec_tag = ci_images.tag("test", root), ci_images.tag("openspec", root)

    # When a lockfile line is changed and the tags are computed again
    same = ci_images.tag("test", root)
    with (root / "tools/requirements-dev.txt").open("a") as f:
        f.write("pytest-timeout==2.3.1\n")
    changed = ci_images.tag("test", root)

    # Then the same inputs give the same tag
    assert same == test_tag and re.fullmatch(r"[0-9a-f]{12}", test_tag)

    # And the changed lockfile gives a different tag, while the openspec image's tag stays the same
    assert changed != test_tag
    assert ci_images.tag("openspec", root) == openspec_tag


def test_ref_names_the_registry_and_the_hash(monkeypatch):
    """OCI refs are lowercase: a fork owner with capitals still gives a valid ref."""

    # Given LLGENIE_REGISTRY=ghcr.io/Asimov-Agent
    monkeypatch.setenv("LLGENIE_REGISTRY", "ghcr.io/Asimov-Agent/")
    import ci_images
    importlib.reload(ci_images)

    # When the refs of both images are printed
    refs = {n: ci_images.ref(n) for n in ("test", "openspec")}

    # Then they are ghcr.io/asimov-agent/llgenie/<name>:<12 hex>
    assert re.fullmatch(r"ghcr\.io/asimov-agent/llgenie/test:[0-9a-f]{12}", refs["test"]), refs
    assert re.fullmatch(r"ghcr\.io/asimov-agent/llgenie/openspec:[0-9a-f]{12}", refs["openspec"]), refs


# ---------------------------------------------------------------------------
# publish (CI job ci-images)
# ---------------------------------------------------------------------------
def test_publish_skips_a_published_hash(tmp_path):
    """An unchanged image costs one registry lookup, no build."""

    # Given a registry that already has the test image's hash tag
    env, log = _fake_docker(tmp_path, published=True)

    # When ci_images.py publish test runs
    r = _ci_images(env, "publish", "test")

    # Then it only looks the tag up and builds nothing
    assert r.returncode == 0, r.stdout + r.stderr
    calls = _calls(log)
    assert len(calls) == 1 and calls[0].startswith("buildx imagetools inspect ghcr.io/asimov-agent/llgenie/test:")
    assert "already published" in r.stdout


def test_publish_builds_both_arches_and_pushes_a_new_hash(tmp_path):
    """A new hash is built once, for both arches, with the registry layer cache, and pushed."""

    # Given a registry without the test image's hash tag
    env, log = _fake_docker(tmp_path, published=False)

    # When ci_images.py publish test runs
    r = _ci_images(env, "publish", "test")

    # Then one two-arch buildx build pushes it with --cache-from/--cache-to on the registry
    assert r.returncode == 0, r.stdout + r.stderr
    builds = [c for c in _calls(log) if c.startswith("buildx build")]
    assert len(builds) == 1, _calls(log)
    b = builds[0]
    assert "--platform linux/amd64,linux/arm64" in b and "--push" in b
    assert "--cache-from type=registry,ref=ghcr.io/asimov-agent/llgenie/test:buildcache" in b
    assert "--cache-to type=registry,ref=ghcr.io/asimov-agent/llgenie/test:buildcache,mode=max" in b
    assert "org.opencontainers.image.source=https://github.com/" in b

    # And its context holds the Dockerfile and both lockfiles
    ctx = next(c for c in _calls(log) if c.startswith("CTX: "))
    assert set(ctx[5:].split()) == {"Dockerfile", "requirements.txt", "requirements-dev.txt"}


# ---------------------------------------------------------------------------
# pull (every CI job) and ensure (a dev host)
# ---------------------------------------------------------------------------
def test_ci_pull_fails_loudly_and_never_builds(tmp_path):
    """A CI job never builds a CI image: a missing tag fails the job."""

    # Given a registry without the test image's hash tag
    env, log = _fake_docker(tmp_path, published=False)

    # When ci_images.py pull test runs
    r = _ci_images(env, "pull", "test")

    # Then it exits non-zero, names the missing ref and never builds
    assert r.returncode == 1
    assert "ghcr.io/asimov-agent/llgenie/test:" in r.stderr and "never build" in r.stderr
    assert not [c for c in _calls(log) if c.startswith(("build", "buildx build"))]


def test_ci_pull_tags_the_local_name(tmp_path):
    """The pulled image gets the local name every make target runs (TEST_IMG)."""

    # Given a registry with the test image's hash tag
    env, log = _fake_docker(tmp_path, published=True)

    # When ci_images.py pull test runs
    r = _ci_images(env, "pull", "test")

    # Then the hash ref is pulled and tagged llgenie/test:latest
    assert r.returncode == 0, r.stdout + r.stderr
    calls = _calls(log)
    ref = calls[0].split()[1]
    assert calls == [f"pull {ref}", f"tag {ref} llgenie/test:latest"]
    assert "TEST_IMG := llgenie/test:latest" in (REPO / "Makefile").read_text()


def test_local_image_is_pulled_when_published(tmp_path):
    """make test-image on a dev host pulls the published image of the current inputs."""

    # Given a registry with the test image's hash tag
    env, log = _fake_docker(tmp_path, published=True)

    # When ci_images.py ensure test runs
    r = _ci_images(env, "ensure", "test")

    # Then it pulls and tags llgenie/test:latest without a build
    assert r.returncode == 0, r.stdout + r.stderr
    calls = _calls(log)
    assert [c.split()[0] for c in calls] == ["pull", "tag"] and calls[1].endswith(" llgenie/test:latest")
    assert "pulled, not built" in r.stdout


def test_local_image_is_built_when_not_published_yet(tmp_path):
    """An edited Dockerfile/lockfile has no published hash yet: the dev host builds it."""

    # Given a registry without the test image's hash tag (an edited lockfile)
    env, log = _fake_docker(tmp_path, published=False)

    # When ci_images.py ensure test runs
    r = _ci_images(env, "ensure", "test")

    # Then it builds llgenie/test:latest from the Dockerfile and both lockfiles and says why
    assert r.returncode == 0, r.stdout + r.stderr
    builds = [c for c in _calls(log) if c.startswith("build ")]
    assert len(builds) == 1 and builds[0].startswith("build -t llgenie/test:latest "), _calls(log)
    ctx = Path(builds[0].split()[-1])
    assert not ctx.exists()  # the temp context is removed after the build
    assert "is not published" in r.stdout


# ---------------------------------------------------------------------------
# workflows
# ---------------------------------------------------------------------------
def _jobs(name: str) -> dict:
    return yaml.safe_load((WF / name).read_text())["jobs"]


def _runs(job: dict) -> list[str]:
    return [st.get("run", "") or "" for st in job.get("steps", [])]


def test_no_ci_job_builds_a_ci_image():
    """Only ci-images builds a CI image; every other job pulls it and needs ci-images."""

    # Given every workflow in .github/workflows
    ci = _jobs("ci.yml")
    pipeline, published = _jobs("pipeline.yml"), _jobs("published.yml")
    every = {**{f"ci/{k}": v for k, v in ci.items()}, **{f"pipeline/{k}": v for k, v in pipeline.items()},
             **{f"published/{k}": v for k, v in published.items()}}

    # When their run: steps are read
    runs = {name: "\n".join(_runs(job)) for name, job in every.items()}

    # Then none runs make test-image or make openspec-image, only ci-images runs make publish-ci-images
    for name, text in runs.items():
        assert not re.search(r"make (test-image|openspec-image)(\s|$)", text), name
        assert ("make publish-ci-images" in text) == (name == "ci/ci-images"), name

    # And every job that pulls a CI image needs ci-images, directly or through its caller
    pulls = {n for n, t in runs.items() if "make test-image-pull" in t or "make test-env" in t or "make openspec-image-pull" in t}
    assert pulls, "no job pulls the CI images"
    callers = {"pipeline": ("linux", "macos"),
               "published": ("linux-published",)}
    for name in pulls:
        wf, job = name.split("/", 1)
        if wf == "ci":
            assert "ci-images" in ci[job]["needs"], name
        else:
            for caller in callers[wf]:
                needs = ci[caller]["needs"]
                # published.yml runs after engine-published-test, which needs ci-images
                chain = needs if "ci-images" in needs else ci[needs[0]]["needs"]
                assert "ci-images" in chain, (name, caller)

    # And ci-images publishes with a write token and the multi-arch builder
    img = ci["ci-images"]
    assert img["permissions"]["packages"] == "write"
    uses = [st.get("uses", "").split("@")[0] for st in img["steps"]]
    assert "docker/setup-qemu-action" in uses and "docker/setup-buildx-action" in uses


def _make_targets(job: dict) -> list[str]:
    return [m for r in _runs(job) for m in re.findall(r"make (ci-[a-z0-9-]+)", r)]


def test_macos_runs_the_linux_pipeline_file_job_for_job():
    """macOS runs the SAME pipeline file as Linux (issue #120: no combined jobs), so every
    job, make ci-<job> target and assert is identical; only the runner label differs."""

    # Given ci.yml and the shared pipeline
    ci, linux = _jobs("ci.yml"), _jobs("pipeline.yml")

    # When the callers of the pipeline are read
    callers = {n: j for n, j in ci.items() if j.get("uses") == "./.github/workflows/pipeline.yml"}

    # Then linux and macos call the one file, with only the runner (and optional) different
    assert set(callers) == {"linux", "macos"}
    assert callers["linux"]["with"] == {"runner": "ubuntu-latest"}
    assert callers["macos"]["with"]["runner"] == "macos-15-intel"
    assert not (REPO / ".github" / "workflows" / "pipeline-macos.yml").exists()

    # And each job runs one target, once (no combined job, nothing runs twice)
    targets = sorted(t for j in linux.values() for t in _make_targets(j) if t != "ci-free-disk")
    assert len(linux) == 10 and len(set(targets)) == len(targets) == 10

    # And no job has an if: (nothing shows as skipped on either OS)
    assert not [n for n, j in linux.items() if "if" in j]


def test_every_pipeline_job_runs_one_ci_make_target():
    """Each Linux pipeline job is ONE make ci-<job> target, so both OSes run the same commands."""

    # Given pipeline.yml and the Makefile
    jobs = _jobs("pipeline.yml")
    mk = (REPO / "Makefile").read_text()

    # When each job's steps are read
    targets = {n: [t for t in _make_targets(j) if t != "ci-free-disk"] for n, j in jobs.items()}

    # Then it runs exactly one make ci-<job>, which exists in the Makefile
    for name, ts in targets.items():
        assert ts == [f"ci-{name}"], (name, ts)
        assert re.search(rf"^ci-{name}:", mk, re.M), name

    # And ci-install only prepares the environment, then runs make install, the
    # installed llgenie dry run, and make uninstall as separate make targets.
    # macOS never runs those inside a container.
    recipe = mk.split("\nci-install:", 1)[1].split("\n\n", 1)[0]
    assert "$(MAKE) test-env" in recipe
    assert "$(MAKE) ci-install-run" in recipe and "$(MAKE) ci-install-dry" in recipe
    assert "$(MAKE) ci-install-uninstall" in recipe and "test-install-ci" not in recipe
    run = mk.split("\nci-install-run:", 1)[1].split("\n\n", 1)[0]
    assert "ifeq ($(HOST_OS),Darwin)" in run and "$(MAKE) install" in run
    assert "$(ENGINE_TEST_RUN)" in run.split("else", 1)[1]
    dry = mk.split("\nci-install-dry:", 1)[1].split("\n\n", 1)[0]
    assert '"$(BIN)/llgenie" --dry' in dry
    assert "$$HOME/bin/llgenie --dry" in dry.split("else", 1)[1]
    undo = mk.split("\nci-install-uninstall:", 1)[1].split("\n\n", 1)[0]
    assert "$(MAKE) uninstall" in undo and "Darwin" in undo


def test_no_ci_step_or_job_is_skipped():
    """No job or step in ci.yml / the pipelines / published.yml carries a condition that
    skips it in a normal push run: OS- or matrix-specific work is decided inside make."""

    # Given every workflow
    files = ("ci.yml", "pipeline.yml", "published.yml")
    wf = {f: _jobs(f) for f in files}

    # When every job-level and step-level if: is collected
    job_ifs = {(f, n): j["if"] for f, jobs in wf.items() for n, j in jobs.items() if "if" in j}
    step_ifs = {(f, n, st.get("name") or st.get("uses")): st["if"]
                for f, jobs in wf.items() for n, j in jobs.items() for st in j.get("steps", []) if "if" in st}

    # Then a job only waits for its needs (!cancelled(), push runs: ci.yml runs on push only)
    for key, cond in job_ifs.items():
        assert cond.replace(" ", "") in ("${{!cancelled()&&github.event_name=='push'}}",
                                         "${{!cancelled()&&github.event_name=='push'&&needs.engine-matrix.result=='success'}}"), key

    # And a step only runs after a failed one, is Linux-only Docker, or is the macOS openspec CLI
    for key, cond in step_ifs.items():
        assert cond in ("${{ !cancelled() }}", "always()", "runner.os == 'Linux'", "runner.os == 'macOS'"), key

    # And the OS / matrix decisions live in make: ci-free-disk and test-engine-stage
    mk = (REPO / "Makefile").read_text()
    assert re.search(r"^ci-free-disk:", mk, re.M) and re.search(r"^test-engine-stage:", mk, re.M)
    stage = mk.split("\ntest-engine-stage:", 1)[1].split("\n\n", 1)[0]
    assert "serve)  $(MAKE) test-engine " in stage and "detect) $(MAKE) test-engine-image " in stage
