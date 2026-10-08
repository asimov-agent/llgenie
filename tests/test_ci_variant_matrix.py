"""The server-variant matrices run prism and stock pairs as separate jobs.

Locks the OpenSpec scenarios in
openspec/changes/feat-server-clone-build/specs/llama-server-build/spec.md
under "CI builds every tree x backend variant the runner supports, in parallel".
Run 36288948408 built the four Linux variants as steps of one job and was
cancelled during stock CUDA after the 100-minute job cap.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github" / "workflows" / "ci.yml"

LINUX_PAIRS = {
    ("server-build-prism-cpu", "prism", "cpu"),
    ("server-build-prism-cuda", "prism", "cuda"),
    ("server-build-upstream-cpu", "upstream", "cpu"),
    ("server-build-upstream-cuda", "upstream", "cuda"),
}


PIPELINE = REPO / ".github" / "workflows" / "pipeline.yml"


def _workflow() -> dict:
    loaded = yaml.safe_load(CI.read_text())
    assert isinstance(loaded, dict)
    return loaded


def _pipeline() -> dict:
    """The jobs the linux and macos pipelines both run (pipeline.yml)."""
    loaded = yaml.safe_load(PIPELINE.read_text())
    assert isinstance(loaded, dict)
    return loaded


def _cells(job: dict) -> set[tuple[str, str, str]]:
    include = job["strategy"]["matrix"]["include"]
    return {(row["name"], row["tree"], row["backend"]) for row in include}


def test_linux_prism_and_stock_variants_are_engine_image_jobs():
    """prism+cpu/cuda and upstream+cpu/cuda now run as engine images, each from its own
    base image, in parallel (the old in-container compile job is gone)."""

    import scripts.engine_image as ei

    # Given the workflow and the generated engine-image matrix
    jobs = _workflow()["jobs"]
    rows = {(r["engine"], r["variant"]) for r in ei.matrix(ci=True)}

    # When the Linux variants are looked up
    # Then each tree x backend is an engine-image job and the old job is removed
    assert "server-variants" not in jobs
    assert {("llama.cpp-prism", "cpu"), ("llama.cpp", "cpu"), ("llama.cpp", "cuda")} <= rows
    # the disabled images (issue #103) are not CI jobs
    assert not rows & set(ei.DISABLED)
    assert jobs["engine-image"]["strategy"]["fail-fast"] is False


def _run_scripts(job: dict) -> str:
    return "\n".join(step.get("run") or "" for step in job["steps"])


def test_every_variant_runs_a_test_stage_on_the_openai_api():
    """cpu images serve the 0.5B model and answer on /v1; GPU images start and run detect."""

    import scripts.engine_image as ei

    # Given the workflow and the engine-image matrix
    jobs = _workflow()["jobs"]
    image_steps = _run_scripts(jobs["engine-image"])
    rows = ei.matrix(ci=True)

    # When the test stages are read
    # Then every image job has a test (serve on cpu, detect on GPU)
    assert "make test-engine ENGINE=" in image_steps
    assert "make test-engine-image ENGINE=" in image_steps
    assert all(r["test"] in ("serve", "detect") for r in rows)
    assert {r["test"] for r in rows if r["engine"].startswith("llama.cpp") and r["variant"] == "cpu"} == {"serve"}
    assert {r["test"] for r in rows if r["variant"] in ("cuda", "rocm", "vulkan")} == {"detect"}

def test_variant_build_streams_its_log():
    """The CUDA compile is visible in CI instead of discarded."""

    # Given the Makefile build-variant recipe
    text = (REPO / "Makefile").read_text()
    start = text.index("build-variant:")
    recipe = text[start:text.index("\n# Serve an already-built", start)]

    # When the recipe is read
    # Then the build script's output is teed through, not dropped
    assert "tee /tmp/llgenie_srv_build.log" in recipe
    assert "2>/dev/null | tail" not in recipe
    script = (REPO / "scripts" / "build_llama_server.sh").read_text()
    assert "building llama-server" in script
    assert "--verbose" not in script
    assert 'parallel jobs:' in script
    assert '-j"$CPUS"' in script


def test_linux_variants_use_their_base_images():
    """Upstream llama.cpp runs FROM the official ggml-org images; Prism compiles on the
    shared CUDA base (nvidia/cuda devel) and ships on the CUDA runtime image."""

    import scripts.engine_skills as es

    # Given the generated Dockerfiles for the Linux variants
    up = es.dockerfile_path("llama.cpp", "cuda").read_text()
    prism = es.dockerfile_path("llama.cpp-prism", "cuda").read_text()
    base = (es.BASE_DIR / "Dockerfile.cuda").read_text()

    # When their bases are read
    # Then each variant runs from its own base image
    assert "FROM ghcr.io/ggml-org/llama.cpp:server-cuda@sha256:" in up
    assert f"FROM {es.base_tag('cuda')} AS build" in prism
    assert "FROM nvidia/cuda:13.0.2-runtime-ubuntu24.04" in prism
    assert base.splitlines()[3].startswith("FROM nvidia/cuda:")

def test_cuda_health_command_serves_the_model_on_cpu():
    """ubuntu-latest has no GPU, so the CUDA binary still answers on CPU."""

    # Given a CUDA-built llama-server and the 0.5B model
    import scripts.ci_health as ci_health

    # When the health check builds the launch command
    cmd = ci_health.server_command("/opt/llama-server", "/models/qwen.gguf", 8080)

    # Then the small model is loaded and --n-gpu-layers is left at llama-server's default
    assert cmd[cmd.index("-m") + 1] == "/models/qwen.gguf"
    assert "--n-gpu-layers" not in cmd


def test_metal_health_command_does_not_force_cpu_offload():
    """Metal serves the same model on the Apple GPU."""

    # Given a Metal-built llama-server and the 0.5B model
    import scripts.ci_health as ci_health

    # When the health check builds the launch command
    cmd = ci_health.server_command("/opt/llama-server", "/models/qwen.gguf", 8080)

    # Then the model is loaded and --n-gpu-layers is left unset
    assert "/models/qwen.gguf" in cmd
    assert "--n-gpu-layers" not in cmd


def test_build_script_clone_help_cuda_and_metal_contracts():
    """The shell build matches the clone, verify, and Metal scenarios."""

    # Given the build script
    script = (REPO / "scripts" / "build_llama_server.sh").read_text()

    # When its clone, verify, and metal preflight are read
    # Then a missing tree is cloned and an existing tree is fetched and reset
    assert 'git clone -b "$BRANCH"' in script
    assert 'git config --global --add safe.directory "$TREE_DIR"' in script
    assert 'git -C "$TREE_DIR" fetch origin "$BRANCH"' in script
    assert 'git -C "$TREE_DIR" checkout -B "$BRANCH"' in script
    assert '"$BINARY" --help' in script
    assert "libcudart" in script and "libcublas" in script
    assert "metal requires macOS" in script


def test_uninstall_removes_install_artifacts_and_not_repo_source():
    """make uninstall undoes make install: the launcher, llgenie.py, every engine
    start script and the llama-server shim; never repo source or other files."""

    # Given the uninstall recipe
    text = (REPO / "Makefile").read_text()
    start = text.index("\nuninstall:") + 1
    recipe = text[start:text.index("\n# ---- watch-loop", start)]

    # When the removals are read
    # Then the launcher + llgenie.py are removed, the engine files go through the
    #      installer's --uninstall, and no source tree / repo script is deleted
    assert 'rm -f "$(LAUNCHER)" "$(BIN)/llgenie.py"' in recipe
    assert "install_engine_launchers.py --bin \"$(BIN)\" --uninstall" in recipe
    assert "PURGE_IMAGES" in recipe
    assert "rm -rf" not in recipe and "SERVER_ROOT" not in recipe.split("\n\t@", 1)[1]
    assert "scripts/llama_serve" not in recipe.split("rm -f", 1)[1].split("\n", 1)[0]


def test_uninstall_removes_only_what_install_wrote(tmp_path, monkeypatch):
    """--uninstall deletes the generated start scripts + shim, keeps foreign files."""

    import importlib
    import scripts.install_engine_launchers as il
    importlib.reload(il)

    # Given an install into a temp bin dir and an unrelated file there
    monkeypatch.setattr(il.ei, "_available", lambda tag: True)
    assert il.install(tmp_path, "cpu", build=False, only=["llama.cpp", "vllm"]) == 0
    (tmp_path / "llgenie-engine-mine").write_text("#!/bin/sh\necho mine\n")
    (tmp_path / "other-tool").write_text("x")
    assert (tmp_path / "llama-server").exists()

    # When uninstall runs (no engine containers running)
    monkeypatch.setattr(il.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "", "returncode": 0})())
    assert il.uninstall(tmp_path) == 0

    # Then the generated scripts and shim are gone, foreign files stay
    left = sorted(p.name for p in tmp_path.iterdir())
    assert left == ["llgenie-engine-mine", "other-tool"]

def test_install_ci_runs_make_install_and_make_uninstall():
    """The install CI job runs, inside the python test container, the real make install
    (engine images via the host docker + start scripts),
    make test-built-engine, the install tests, a "hi" through the container
    llama-server, and make uninstall."""

    # Given the test-install-ci recipe and the CI install job
    text = (REPO / "Makefile").read_text()
    start = text.index("test-install-ci:")
    recipe = text[start:text.index("\ntest-top-tier:", start)]
    install = text[text.index("\ninstall:"):].split("\n", 2)[1]
    job = _run_scripts(_pipeline()["jobs"]["install"])

    # When they are read
    # Then make install builds/pulls the images and runs test-built-engine,
    #      and the recipe tests, says hi, and uninstalls every installed file
    assert "engine-launchers" in install and "test-built-engine" in install
    assert "$(ENGINE_TEST_RUN)" in recipe  # python test container + host docker socket
    assert "make install" in recipe and "make test-install-host" in recipe
    assert "make test-health-host" in recipe and "make uninstall" in recipe
    assert "llgenie-engine-*" in recipe and "scripts/llama_serve.py" in recipe
    assert "make test-image" in job and "make test-install-ci" in job


