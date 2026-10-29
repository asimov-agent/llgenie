"""CI images on GHCR (issue #117): the test image and the OpenSpec CLI image are tagged by a
hash of their inputs, published once per hash by the `ci-images` job and PULLED by every
other CI job. macOS runs the pipeline's make targets in three Docker jobs instead of ten.

Hermetic: a fake `docker` on PATH logs every call; no registry, no build."""
from __future__ import annotations

import base64
import http.server
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
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


def _fake_docker(tmp: Path, published: bool, cache_published: bool = True) -> tuple[dict, Path]:
    """`docker` that logs its args (and the build context's files) and answers the registry
    lookup / pull with `published`."""
    log = tmp / "docker.log"
    rc = 0 if published else 1
    # The registry cache ref is probed separately: a NEW image's first publish has no cache
    # yet, and buildx fails to configure the importer then (so publish omits --cache-from).
    cache_rc = 0 if cache_published else 1
    script = f'''#!/bin/sh
echo "$*" >> "{log}"
case "$1 $2" in
  "buildx imagetools")
    case "$*" in *buildcache*) exit {cache_rc} ;; esac
    exit {rc} ;;
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


def test_a_first_publish_omits_cache_from_but_keeps_cache_to(tmp_path):
    """A brand-new image reads no registry cache: buildx fails on a missing cache importer.

    This is the llgenie/agent case: the image did not exist yet, so
    `--cache-from ...:buildcache` made the build die with
    "failed to configure registry cache importer: ...:buildcache: not found", and the
    publish never happened. The write side (`--cache-to`) still seeds the cache.
    """

    # Given neither the image tag nor its cache ref on the registry (a first publish)
    env, log = _fake_docker(tmp_path, published=False, cache_published=False)

    # When publish runs
    r = _ci_images(env, "publish", "test")

    # Then it builds and pushes without --cache-from, and still writes the cache
    assert r.returncode == 0, r.stdout + r.stderr
    b = next(c for c in _calls(log) if c.startswith("buildx build"))
    assert "--cache-from" not in b, "a missing cache ref must not be probed as a source"
    assert "--cache-to type=registry,ref=ghcr.io/asimov-agent/llgenie/test:buildcache,mode=max" in b
    assert "--push" in b


def test_publish_agent_pins_the_test_image_it_builds_from(tmp_path):
    """The agent (Hermes) image is built FROM the test image's published hash tag, so a
    rebuilt base must produce a new agent tag and the build passes --build-arg TEST_IMAGE=."""

    # Given a registry without the agent image's hash tag
    env, log = _fake_docker(tmp_path, published=False)

    # When ci_images.py publish agent runs
    r = _ci_images(env, "publish", "agent")

    # Then one amd64 buildx build pushes it, pinning the exact test image ref (the agent image
    # publishes amd64 only: it builds Hermes at build time, which times out under arm64 emulation)
    assert r.returncode == 0, r.stdout + r.stderr
    builds = [c for c in _calls(log) if c.startswith("buildx build")]
    assert len(builds) == 1, _calls(log)
    b = builds[0]
    assert "--platform linux/amd64" in b and "--push" in b
    assert "arm64" not in b
    assert re.search(r"-t ghcr\.io/asimov-agent/llgenie/agent:[0-9a-f]{12}", b), b
    assert "-t ghcr.io/asimov-agent/llgenie/agent:latest" in b, b
    assert re.search(r"--build-arg TEST_IMAGE=ghcr\.io/asimov-agent/llgenie/test:[0-9a-f]{12}", b), b

    # And its context holds the agent Dockerfile and EVERY script it COPYs. Read from the
    # registry's own input list rather than a literal set: a new COPY that is not a hash input
    # (or vice versa) is exactly the drift this assertion exists to catch.
    import ci_images as _ci
    ctx = next(c for c in _calls(log) if c.startswith("CTX: "))
    expected = {"Dockerfile", *(Path(rel).name for rel in _ci.IMAGES["agent"][1])}
    assert set(ctx[5:].split()) == expected, ctx


def test_agent_tag_changes_when_the_test_image_tag_changes(tmp_path):
    """The agent tag folds in the test image's tag, so a rebuilt base re-tags the agent."""

    import ci_images

    root = _copy_inputs(tmp_path)
    # the agent image's own inputs (its Dockerfile + every script it COPYs) must exist in the
    # copy — read from the registry's input list, so adding a script cannot leave this behind
    for rel in ("containers/agent/Dockerfile", *ci_images.IMAGES["agent"][1]):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, root / rel)

    before = ci_images.tag("agent", root)
    # a change to the test image's lockfile changes the test tag, hence the agent tag
    with (root / "tools/requirements-dev.txt").open("a") as f:
        f.write("pytest-timeout==2.3.1\n")
    after = ci_images.tag("agent", root)
    assert before != after and re.fullmatch(r"[0-9a-f]{12}", before)


def test_publish_agent_moves_latest_when_the_hash_is_already_published(tmp_path):
    """An already-published agent hash is not rebuilt, and :latest still moves onto it.

    The hash `74d0fa987227` was pushed with no :latest tag. A publish that returned
    after the inspect would leave every pull of :latest with nothing to fetch.
    """

    # Given a registry that already has the agent image's hash tag
    env, log = _fake_docker(tmp_path, published=True)

    # When ci_images.py publish agent runs
    r = _ci_images(env, "publish", "agent")

    # Then it does not build, and imagetools points :latest at the hash
    assert r.returncode == 0, r.stdout + r.stderr
    calls = _calls(log)
    assert not [c for c in calls if c.startswith("buildx build")], calls
    create = [c for c in calls if c.startswith("buildx imagetools create")]
    assert len(create) == 1, calls
    assert "ghcr.io/asimov-agent/llgenie/agent:latest" in create[0], create[0]
    assert re.search(r"ghcr\.io/asimov-agent/llgenie/agent:[0-9a-f]{12}", create[0]), create[0]
    assert "now points at it" in r.stdout


def test_agent_pull_uses_latest(tmp_path):
    """Agent pulls fetch GHCR :latest. The content hash is not the pull ref."""

    # Given a registry that answers the pull
    env, log = _fake_docker(tmp_path, published=True)

    # When ci_images.py pull agent runs
    r = _ci_images(env, "pull", "agent")

    # Then the only pull is :latest, retagged to the local name
    assert r.returncode == 0, r.stdout + r.stderr
    latest = "ghcr.io/asimov-agent/llgenie/agent:latest"
    assert _calls(log) == [f"pull {latest}", f"tag {latest} llgenie/agent:latest"]


def test_agent_ensure_pulls_latest(tmp_path):
    """make agent-image pulls GHCR :latest and does not build when that tag exists."""

    # Given a registry that answers the pull
    env, log = _fake_docker(tmp_path, published=True)

    # When ci_images.py ensure agent runs
    r = _ci_images(env, "ensure", "agent")

    # Then it pulls :latest and does not build
    assert r.returncode == 0, r.stdout + r.stderr
    assert _calls(log)[0] == "pull ghcr.io/asimov-agent/llgenie/agent:latest"
    assert "pulled, not built" in r.stdout
    assert not [c for c in _calls(log) if c.startswith("build ")]


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
    assert re.fullmatch(r"ghcr\.io/asimov-agent/llgenie/test:[0-9a-f]{12}", ref), ref
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
    callers = {"pipeline": ("linux",),
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


def test_only_linux_calls_the_pipeline_file_and_no_macos_runner_is_requested():
    """CI is Linux-only (#870): the macOS group is GONE, not conditionally skipped.

    `pipeline.yml` keeps its `runner` input, so macOS coverage can be restored by adding a caller
    back - but while no caller passes a macOS label, no check on this repository exercises macOS.
    """

    # Given ci.yml and the shared pipeline
    ci, linux = _jobs("ci.yml"), _jobs("pipeline.yml")

    # When the callers of the pipeline are read
    callers = {n: j for n, j in ci.items() if j.get("uses") == "./.github/workflows/pipeline.yml"}

    # Then  exactly one caller remains, on ubuntu-latest, carrying the row selection (#859: the
    #       guard's decision, so the top-tier row follows the `ci:slow` label while every other row
    #       of the same call is unchanged) ...
    assert set(callers) == {"linux"}, callers
    assert callers["linux"]["with"] == {"runner": "ubuntu-latest",
                                        "top_tier_rows": "${{ needs.guard.outputs.top_tier_rows }}"}
    # ... no macOS job survived in any form, and no macOS label is named anywhere in the workflow
    assert not [n for n in ci if "macos" in n.lower()], list(ci)
    assert "macos-15-intel" not in (REPO / ".github/workflows/ci.yml").read_text()
    # ... and the shared file was not forked into a Linux-only copy
    assert not (REPO / ".github" / "workflows" / "pipeline-macos.yml").exists()

    # And each job runs one target, once (no combined job, nothing runs twice)
    targets = sorted(t for j in linux.values() for t in _make_targets(j) if t != "ci-free-disk")
    assert len(linux) == 7 and len(set(targets)) == len(targets) == 7

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
    assert "$(MAKE) ci-wait-engine-images ARCH=cpu" in recipe.split("$(MAKE) ci-install-run")[0]
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

    # And the install job also exercises the INSTALLED launcher's argument surface in dry
    # run (issue #236): bare --dry is not the whole CLI, and every grid dry run in the unit
    # stage goes through scripts/llgenie_serve.py, never the wrapper a user runs.
    assert "$(MAKE) ci-install-dry-args" in recipe
    args = mk.split("\nci-install-dry-args:", 1)[1].split("\n\n", 1)[0]
    assert "tests/test_cli_dry_run_matrix.py" in args
    assert "$(ENGINE_TEST_RUN)" in args.split("else", 1)[1]      # Linux: the same HOME make install wrote
    assert "$(TEST_RUN)" in args.split("else", 1)[0]             # macOS: the 3.11 venv, no container
    assert "ci-install-dry-args" in mk.split("\n.PHONY:", 1)[1].split("\n\n", 1)[0]


# Job-level if: forms that do not skip a job in a normal push run with engines
# to build. A PR that changes no engine params still emits one `none` row:
# GitHub fails a workflow whose matrix include list is empty BEFORE the job if:
# is evaluated (run 38105450418). The none row is skipped; it builds nothing.
_PUSH_WAIT = (
    "${{!cancelled()&&github.event_name=='push'}}",
    "${{!cancelled()&&github.event_name=='push'&&needs.engine-matrix.result=='success'}}",
    "${{!cancelled()&&github.event_name=='push'&&needs.engine-published-test.result=='success'}}",
    # linux-published must run on a PR too: a skipped uses: job never reports
    # the required install-published-* check names (PR #126).
    "${{!cancelled()&&(github.event_name=='pull_request'||needs.engine-image.result=='success')}}",
)


def _job_if_allowed(cond):
    """A job if: may only wait for its needs, skip the none row, or scope the auto-merge job to a PR."""

    flat = cond.replace(" ", "")
    if flat in _PUSH_WAIT:
        return True
    # engine-image: the none placeholder builds nothing
    if flat == "${{matrix.engine!='none'}}":
        return True
    # engine-published-test: push + the image job succeeded (the none row is a step if:)
    if (flat.startswith("${{!cancelled()&&github.event_name=='push'")
            and "needs.engine-image.result=='success'" in flat):
        return True
    # auto-merge is no longer a job in ci.yml (issue #493): a `pull_request` run from a fork receives no
    # repository secrets, so the job reported green while merging nothing (#481). It is a `workflow_run`
    # workflow now (`.github/workflows/auto-merge.yml`), and no job here is scenario-scoped any more.
    return False


def test_no_ci_step_or_job_is_skipped():
    """No job or step in ci.yml / the pipelines / published.yml carries a condition that
    skips it in a normal push run with engines to build: OS- or matrix-specific work is
    decided inside make. A PR that changes no engine params emits one `none` row
    (issue #107, run 38105450418): GitHub fails a workflow whose include list is
    empty before the job if: is evaluated. That row is skipped and builds nothing."""

    # Given every workflow
    files = ("ci.yml", "pipeline.yml", "published.yml")
    wf = {f: _jobs(f) for f in files}

    # When every job-level and step-level if: is collected
    job_ifs = {(f, n): j["if"] for f, jobs in wf.items() for n, j in jobs.items() if "if" in j}
    step_ifs = {(f, n, st.get("name") or st.get("uses")): st["if"]
                for f, jobs in wf.items() for n, j in jobs.items() for st in j.get("steps", []) if "if" in st}

    # Then a job only waits for its needs, or skips the none placeholder row
    for key, cond in job_ifs.items():
        assert _job_if_allowed(cond), (key, cond)

    # And a step only runs after a failed one, is Linux-only Docker, is the macOS
    # openspec CLI, or skips the none placeholder row (matrix is illegal in a job if:)
    for key, cond in step_ifs.items():
        # `matrix.backend != 'none'` is the published family's placeholder row (#844): the exact twin of
        # `matrix.engine != 'none'` that #828 gave the engine family. It skips a ROW, never a job, so
        # every check name still reports and the row's own first step prints why it installed nothing.
        # The `row` conditions are the same shape for `pipeline.yml`'s top-tier stage (#859): its ONE
        # matrix axis comes from `make ci-slow-rows`, so a row a pull request does not schedule runs no
        # make target — and, combined with the OS condition, the docker step stays Linux-only on a row
        # that did run (`matrix.row != 'none' && always()` is its container prune).
        assert cond in ("${{ !cancelled() }}", "always()", "runner.os == 'Linux'", "runner.os == 'macOS'",
                        "${{ matrix.engine != 'none' }}", "${{ matrix.backend != 'none' }}",
                        "matrix.row != 'none'",
                        "matrix.row != 'none' && runner.os == 'Linux'",
                        "matrix.row != 'none' && always()"), key

    # And the OS / matrix decisions live in make: ci-free-disk and test-engine-stage
    mk = (REPO / "Makefile").read_text()
    assert re.search(r"^ci-free-disk:", mk, re.M) and re.search(r"^test-engine-stage:", mk, re.M)
    stage = mk.split("\ntest-engine-stage:", 1)[1].split("\n\n", 1)[0]
    assert "serve)  $(MAKE) test-engine-image " in stage and "detect) $(MAKE) test-engine-image " in stage
    assert "$(MAKE) test-engine ENGINE=" in stage


def test_the_agent_image_publishes_amd64_only(tmp_path):
    """The agent image builds Hermes at build time; under arm64 emulation that took >900s and the
    multi-arch publish died mid-install. The bots run on amd64 runners, so it publishes amd64."""
    import ci_images as ci
    assert ci.platforms("agent") == "linux/amd64"
    assert ci.platforms("test") == ci.PLATFORMS, "every other image keeps both platforms"
    assert ci.platforms("openspec") == ci.PLATFORMS

    env, log = _fake_docker(tmp_path, published=False, cache_published=True)
    r = _ci_images(env, "publish", "agent")
    assert r.returncode == 0, r.stdout + r.stderr
    b = next(c for c in _calls(log) if c.startswith("buildx build"))
    assert "--platform linux/amd64" in b, b
    assert "linux/arm64" not in b, "no arm64 consumer exists for the agent image"


def test_a_normal_image_still_publishes_both_platforms(tmp_path):
    """The override must not leak: the test image still publishes both arches."""
    env, log = _fake_docker(tmp_path, published=False, cache_published=True)
    r = _ci_images(env, "publish", "test")
    assert r.returncode == 0, r.stdout + r.stderr
    b = next(c for c in _calls(log) if c.startswith("buildx build"))
    assert "--platform linux/amd64,linux/arm64" in b, b


# ---------------------------------------------------------------------------
# pushcheck (publish-agent-image.yml, BEFORE the build — issue #335)
# ---------------------------------------------------------------------------
_DENIED = '{"errors":[{"code":"DENIED","message":"denied: requested access to the resource is denied"}]}'


def _stub_registry(token_status: int = 200,
                   upload_status: int = 202) -> tuple[str, list, http.server.ThreadingHTTPServer]:
    """A stand-in GHCR. Records (method, path, authorization) for every request it answers.

    The pre-flight makes exactly two: the push-scoped token exchange, then the empty blob upload.
    """
    seen: list[tuple[str, str, str]] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:   # keep pytest's output clean
            pass

        def _answer(self, status: int, payload) -> None:
            raw = (payload if isinstance(payload, str) else json.dumps(payload)).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            seen.append((self.command, self.path, self.headers.get("Authorization", "")))
            self._answer(token_status, {"token": "stub-token"} if token_status == 200 else _DENIED)

        def do_POST(self):
            seen.append((self.command, self.path, self.headers.get("Authorization", "")))
            self._answer(upload_status, "" if upload_status < 300 else _DENIED)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}", seen, srv


def _pushcheck(env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "ci_images.py"), "pushcheck", *args],
                          env=env, capture_output=True, text=True, timeout=60)


def test_pushcheck_asks_for_a_push_token_then_does_an_empty_upload():
    """The shape the pre-flight must have: a push-scoped token for the package the publish writes,
    then the cheapest real write there is — an empty blob upload, carrying no data."""

    # Given a stub registry that accepts the token exchange and the upload
    base, seen, srv = _stub_registry()
    try:
        env = {**os.environ, "LLGENIE_REGISTRY": base, "GHCR_TOKEN": "s3cret",
               "GHCR_USER": "asimov-agent"}

        # When the pre-flight runs for the agent package
        r = _pushcheck(env, "agent")

        # Then it exits 0 and asked for a token scoped to push exactly that package
        assert r.returncode == 0, r.stdout + r.stderr
        method, path, auth = seen[0]
        assert method == "GET" and path.startswith("/token?")
        assert "service=127.0.0.1" in path and "scope=repository:llgenie/agent:push" in path
        assert base64.b64decode(auth.split()[1]).decode() == "asimov-agent:s3cret"
        assert "may push" in r.stdout

        # And the write it initiated is the EMPTY upload, with the token it was just given
        assert seen[1] == ("POST", "/v2/llgenie/agent/blobs/uploads/", "Bearer stub-token")
    finally:
        srv.shutdown()


def test_pushcheck_fails_when_the_credential_may_not_push():
    """A denial is the whole point: it must exit non-zero and surface the registry's own message,
    not be swallowed into a green step that then burns the build."""

    # Given a registry that grants the token but refuses the upload
    base, seen, srv = _stub_registry(upload_status=403)
    try:
        env = {**os.environ, "LLGENIE_REGISTRY": base, "GHCR_TOKEN": "s3cret"}

        # When the pre-flight runs
        r = _pushcheck(env, "agent")

        # Then it fails loudly, quoting the registry, and never reports success
        assert r.returncode == 1
        assert "CANNOT push" in r.stderr and "denied:" in r.stderr
        assert "may push" not in r.stdout
        assert len(seen) == 2, seen
    finally:
        srv.shutdown()


def test_pushcheck_reports_a_refused_token():
    """A credential the registry will not even issue a push token for is the same verdict, one step
    earlier — and no upload may be attempted without the token."""

    # Given a registry that refuses the token exchange
    base, seen, srv = _stub_registry(token_status=403)
    try:
        env = {**os.environ, "LLGENIE_REGISTRY": base, "GHCR_TOKEN": "s3cret"}

        # When the pre-flight runs
        r = _pushcheck(env, "agent")

        # Then it names the refusal and stops
        assert r.returncode == 1
        assert "refused a push-scoped token" in r.stderr and "denied:" in r.stderr
        assert len(seen) == 1, "no upload is attempted without a token"
    finally:
        srv.shutdown()


def test_pushcheck_without_a_credential_fails_before_any_request():
    """A run with no credential must say so — not discover it at the push, after the build."""

    # Given no token in the environment
    env = {k: v for k, v in os.environ.items() if k not in ("GHCR_TOKEN", "GITHUB_TOKEN")}
    env["LLGENIE_REGISTRY"] = "http://127.0.0.1:1"     # nothing listens: any request would error

    # When the pre-flight runs
    r = _pushcheck(env, "agent")

    # Then it fails with the reason, and the registry is never contacted
    assert r.returncode == 1
    assert "no credential" in r.stderr


def test_pushcheck_fails_with_a_sentence_when_the_registry_is_unreachable():
    """A network failure is a failure too — and it must read as one, not as a traceback that hides
    which registry the step could not reach."""

    # Given a registry address nothing is listening on
    env = {**os.environ, "LLGENIE_REGISTRY": "http://127.0.0.1:1", "GHCR_TOKEN": "s3cret"}

    # When the pre-flight runs
    r = _pushcheck(env, "agent")

    # Then it fails with a sentence naming what it could not reach
    assert r.returncode == 1
    assert "could not reach" in r.stderr and "http://127.0.0.1:1" in r.stderr
    assert "Traceback" not in r.stderr


def test_the_push_check_targets_the_package_the_publish_writes(monkeypatch):
    """<registry>/llgenie/<name> — the owner in the registry is part of the package path, and GHCR
    carries no scheme of its own."""
    import ci_images

    monkeypatch.setenv("LLGENIE_REGISTRY", "ghcr.io/asimov-agent")
    assert ci_images.package("agent") == ("https://ghcr.io", "asimov-agent/llgenie/agent")


def test_pushcheck_defaults_to_the_registry_owner_and_targets_its_package():
    """With no GHCR_USER, the Basic user is the registry's owner segment — the account the workflow's
    own `docker login -u ${{ github.repository_owner }}` uses — and the owner is part of the package
    path the upload targets."""

    # Given a registry that names an owner and no GHCR_USER in the environment
    base, seen, srv = _stub_registry()
    try:
        env = {k: v for k, v in os.environ.items() if k not in ("GHCR_USER", "GITHUB_ACTOR")}
        env.update({"LLGENIE_REGISTRY": f"{base}/asimov-agent", "GHCR_TOKEN": "s3cret"})

        # When the pre-flight runs
        r = _pushcheck(env, "agent")

        # Then it pushes as the owner, against the owner's package
        assert r.returncode == 0, r.stdout + r.stderr
        assert base64.b64decode(seen[0][2].split()[1]).decode() == "asimov-agent:s3cret"
        assert seen[1][1] == "/v2/asimov-agent/llgenie/agent/blobs/uploads/"
    finally:
        srv.shutdown()


def test_the_publish_job_proves_the_push_before_it_builds():
    """The pre-flight is a step of publish-agent-image.yml, before the publish it protects, wired to
    the target and handed the credential the job logs in with."""

    # Given the publish job's steps and the Makefile
    steps = _jobs("publish-agent-image.yml")["publish"]["steps"]
    mk = (REPO / "Makefile").read_text()

    # When the pre-flight step and the publish step are located
    runs = [st.get("run", "") or "" for st in steps]
    i_check = next(i for i, r in enumerate(runs) if "make agent-image-push-check" in r)
    i_publish = next(i for i, r in enumerate(runs) if "make publish-agent-image" in r)

    # Then the check precedes the build and is handed the credential the login step uses
    assert i_check < i_publish, "the pre-flight must run BEFORE the expensive build"
    assert "GHCR_TOKEN" in yaml.safe_dump(steps[i_check]), "the step must pass the credential"

    # And the target exists, is .PHONY, and drives the pushcheck sub-command
    assert re.search(r"^agent-image-push-check:", mk, re.M)
    assert "agent-image-push-check" in mk.split("\n.PHONY:", 1)[1].split("\n\n", 1)[0]
    assert re.search(r"^agent-image-push-check:.*\n.*\n\tpython3 scripts/ci_images\.py pushcheck agent",
                     mk, re.M)


def test_the_agent_publish_logs_in_with_the_credential_its_push_check_proves():
    """One credential, named once (issue #413).

    `publish-agent-image.yml` used to log in with `secrets.BUMP_TOKEN` while proving the push with the
    same PAT — and that PAT carries no `write:packages`, so the job's own pre-flight refused it
    (`403 DENIED … does not match expected scopes`, run 39420414201). The sibling path that DOES publish
    (`ci.yml::ci-images` → `llgenie/test`) logs in with `secrets.GITHUB_TOKEN` and `packages: write`.

    This locks the pair: whatever secret the login step names, the push-check step is handed the same
    one, and it is the credential the working publish path uses — never the owner PAT.
    """

    # Given the publish workflow's login and pre-flight steps
    steps = _jobs("publish-agent-image.yml")["publish"]["steps"]
    login = next(st for st in steps if "docker login ghcr.io" in (st.get("run", "") or ""))
    check = next(st for st in steps if "make agent-image-push-check" in (st.get("run", "") or ""))

    # When  the secret each one names is read
    login_secret = re.search(r"secrets\.([A-Z_]+)", login["run"]).group(1)
    check_secret = re.search(r"\$\{\{\s*secrets\.([A-Z_]+)\s*\}\}", check["env"]["GHCR_TOKEN"]).group(1)

    # Then  the login and the check agree, and it is GITHUB_TOKEN (the credential ci.yml publishes with)
    assert login_secret == check_secret, (
        f"the job logs in with secrets.{login_secret} but proves secrets.{check_secret}"
    )
    assert login_secret == "GITHUB_TOKEN", (
        "the owner PAT has no write:packages; ci.yml publishes llgenie/test with GITHUB_TOKEN"
    )
    assert "github.actor" in login["run"], "log in as the account the token belongs to (ci.yml's shape)"

    # And the job declares the permission that credential needs
    workflow = yaml.safe_load((WF / "publish-agent-image.yml").read_text())
    assert workflow["permissions"]["packages"] == "write"
