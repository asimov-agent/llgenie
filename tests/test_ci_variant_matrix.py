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
MAC_PAIRS = {
    ("server-build-prism-cpu-mac", "prism", "cpu"),
    ("server-build-prism-metal", "prism", "metal"),
    ("server-build-upstream-cpu-mac", "upstream", "cpu"),
    ("server-build-upstream-metal", "upstream", "metal"),
}


def _workflow() -> dict:
    loaded = yaml.safe_load(CI.read_text())
    assert isinstance(loaded, dict)
    return loaded


def _cells(job: dict) -> set[tuple[str, str, str]]:
    include = job["strategy"]["matrix"]["include"]
    return {(row["name"], row["tree"], row["backend"]) for row in include}


def test_linux_prism_and_stock_pairs_are_parallel_matrix_cells():
    """prism+cpu || prism+cuda and upstream+cpu || upstream+cuda."""

    # Given the server-variants job on ubuntu-latest
    job = _workflow()["jobs"]["server-variants"]

    # When the matrix is expanded
    cells = _cells(job)

    # Then both pairs are cells of one matrix, with no needs and fail-fast off
    assert job["runs-on"] == "ubuntu-latest"
    assert job["strategy"]["fail-fast"] is False
    assert "needs" not in job
    assert cells == LINUX_PAIRS
    assert "max-parallel" not in job["strategy"]


def test_mac_prism_and_stock_pairs_are_parallel_matrix_cells():
    """prism+cpu || prism+metal and upstream+cpu || upstream+metal."""

    # Given the server-variants-mac job on macos-14
    job = _workflow()["jobs"]["server-variants-mac"]

    # When the matrix is expanded
    cells = _cells(job)

    # Then both pairs are cells of one matrix, with no needs and fail-fast off
    assert job["runs-on"] == "macos-14"
    assert job["strategy"]["fail-fast"] is False
    assert "needs" not in job
    assert cells == MAC_PAIRS
    assert "max-parallel" not in job["strategy"]


def _run_scripts(job: dict) -> str:
    return "\n".join(step.get("run") or "" for step in job["steps"])


def test_every_variant_runs_the_small_model_health_check():
    """CPU, CUDA, and Metal each answer hi with the 0.5B GGUF."""

    # Given both variant matrices
    jobs = _workflow()["jobs"]
    linux = _run_scripts(jobs["server-variants"])
    mac_steps = jobs["server-variants-mac"]["steps"]
    mac = _run_scripts(jobs["server-variants-mac"])

    # When the health-check steps are read
    venv_step = next(s for s in mac_steps if "cihealth" in (s.get("run") or ""))

    # Then every backend is tested through make test-serve-variant
    assert "make test-serve-variant" in linux
    assert "make test-serve-variant" in mac
    assert "actions/cache@v4" in (REPO / ".github" / "workflows" / "ci.yml").read_text()
    assert "llama-build:/root/repository/git" in linux
    assert "SERVER_ROOT" in mac
    assert "make build-variant" in mac
    assert 'VARIANT_BACKEND" = cpu' not in linux
    assert "--n-gpu-layers 0" not in linux
    assert "if" not in venv_step
    assert 'VARIANT_BACKEND" = cpu' not in mac


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


def test_linux_variants_compile_llama_server_against_prebuilt_cuda():
    """The toolkit is the nvidia/cuda image. llama-server is compiled in it."""

    # Given the variant image and the Linux workflow
    dockerfile = (REPO / "containers" / "ci-variant" / "Dockerfile").read_text()
    linux = _run_scripts(_workflow()["jobs"]["server-variants"])

    # When the image base and the job steps are read
    from_line = next(ln for ln in dockerfile.splitlines() if ln.startswith("FROM "))

    # Then CUDA is the prebuilt base image and llama-server is built in-container
    assert from_line.startswith("FROM nvidia/cuda:")
    assert "make test-variant-image" in linux
    assert "make install-" in linux or 'make "install-' in linux
    assert "nvidia-cuda-toolkit" not in linux
    assert "ghcr.io/ggml-org/llama.cpp" not in linux


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
    """make uninstall removes the launcher and symlinks, not the repo scripts."""

    # Given the uninstall recipe
    text = (REPO / "Makefile").read_text()
    start = text.index("uninstall:")
    recipe = text[start:text.index("\n# ---- watch-loop", start)]

    # When the removals are read
    # Then the three install paths are removed and repo source is not
    assert "$(LAUNCHER)" in recipe
    assert "$(BIN)/llgenie.py" in recipe
    assert "$(BIN)/llama-server" in recipe
    assert "rm " in recipe
    assert "MUST NOT delete repo source" in recipe
    assert "rm -f" in recipe and "scripts/" not in recipe.split("rm -f", 1)[1].split("\n", 1)[0]


def test_install_ci_runs_make_install_and_make_uninstall():
    """The install CI job executes the install chain and then uninstall."""

    # Given the test-install-ci recipe
    text = (REPO / "Makefile").read_text()
    start = text.index("test-install-ci:")
    recipe = text[start:text.index("\ntest-top-tier:", start)]

    # When the container command is read
    # Then it runs make install (build-server, venv, link, smoke) and make uninstall
    assert "make install" in recipe
    assert "make uninstall" in recipe
    assert "scripts/llama_serve.py" in recipe


def test_linux_and_mac_matrices_do_not_wait_on_each_other():
    """The two OS matrices start together."""

    # Given both variant jobs
    jobs = _workflow()["jobs"]

    # When their dependency edges are read
    linux_needs = jobs["server-variants"].get("needs")
    mac_needs = jobs["server-variants-mac"].get("needs")

    # Then neither waits on the other
    assert linux_needs is None
    assert mac_needs is None
