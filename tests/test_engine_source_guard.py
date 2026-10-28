"""The source-build guard: a cell that says `prebuilt: false` must actually compile.

The dispatch sweep claims every cell is built from its own params. A cell whose install
steps only download a wheel or a release archive makes that claim false while looking
green everywhere else, so this guard reads the committed params and fails on it.
"""

from __future__ import annotations

import json
import subprocess
import sys

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import engine_source_guard as guard  # noqa: E402


def _cell(engine: str, arch: str, install: list[str], prebuilt: bool = False) -> dict:
    return {"engine": engine, "arch": arch, "prebuilt": prebuilt, "install": install}


def test_a_cmake_cell_passes():
    """llama.cpp's variant is a real source build: clone, cmake, make."""

    # Given a cell that clones a pinned sha and compiles
    row = _cell("llama.cpp", "cpu", [
        "git clone --depth 1 https://github.com/ggml-org/llama.cpp /src",
        "git -C /src checkout -q 39febd2a0",
        "cmake -B /src/build -DLLAMA_CUDA=OFF -DCMAKE_BUILD_TYPE=Release",
        "cmake --build /src/build --target llama-server",
    ])

    # When  the guard looks at it
    result = guard.findings([row])

    # Then  it has nothing to say
    assert result == []


def test_a_wheel_cell_that_claims_a_build_is_a_finding():
    """`uv pip install <name>==<ver>` installs someone else's build, not ours."""

    # Given a cell that only installs a published wheel
    row = _cell("newengine", "cpu", ["uv pip install --system --break-system-packages 'newengine[accel]' newengine==1.2.3"])

    # When  the guard looks at it
    result = guard.findings([row])

    # Then  it fails, naming the cell and no tracking issue
    assert len(result) == 1
    where, message, issue = result[0]
    assert where == "newengine/cpu" and issue == ""
    assert "run no build" in message


def test_a_release_archive_cell_is_a_finding_even_with_a_build_present():
    """Downloading a compiled tarball is a pull, whatever else the cell does."""

    # Given a cell that builds something and also downloads a release binary
    row = _cell("tensorfold", "cuda", [
        "cmake -B build", "cmake --build build",
        "curl -fsSL -o /tmp/tf.tar.gz https://example.invalid/tensorfold-1.1.6-linux-x86_64.tar.gz",
    ])

    # When  the guard looks at it
    result = guard.findings([row])

    # Then  the download is reported
    assert len(result) == 1 and "downloads a built artefact" in result[0][1]


def test_a_prebuilt_cell_is_never_a_finding():
    """A cell that says `prebuilt: true` is a deliberate pull and must not be nagged."""

    # Given a prebuilt cell with a wheel install
    row = _cell("vllm", "cuda", ["uv pip install vllm==0.11.0"], prebuilt=True)

    # When  the guard looks at it
    # Then  it is silent
    assert guard.findings([row]) == []


def test_a_tracked_exception_passes_the_gate_but_is_reported():
    """A cell tracked by its issue is printed and does not fail the run; a new one does."""

    # Given a tracked cell and an untracked one
    tracked = _cell("mlx", "cpu", ["uv pip install 'mlx[cpu]' mlx-lm==0.32.2"])
    untracked = _cell("brandnew", "cuda", ["uv pip install brandnew==1.0"])

    # When  the check runs on each alone
    ok = subprocess.run([sys.executable, str(REPO / "scripts" / "engine_source_guard.py"), "check"],
                        capture_output=True, text=True, cwd=REPO)

    # Then  the committed tree passes (its exceptions are tracked) …
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "#615" in ok.stdout
    assert any(issue for _w, _m, issue in guard.findings([tracked]))
    # … while an untracked cell with no issue would have failed it
    assert guard.findings([untracked])[0][2] == ""


def test_the_census_matches_the_committed_params():
    """17 source cells compile, 9 are prebuilt, 5 claim a build they do not have yet."""

    rows = guard.cells()

    # Given every committed cell
    # When  the census is taken
    prebuilt = [r for r in rows if r["prebuilt"]]
    source = [r for r in rows if not r["prebuilt"]]
    bad = guard.findings(rows)

    # Then  the counts are the ones the issues describe
    assert len(rows) == 31
    assert len(prebuilt) == 9
    assert len(source) == 22
    assert len(bad) == 5 and all(issue for _w, _m, issue in bad)
    assert {w for w, _m, _i in bad} == {"freetoken/cuda", "litert/cpu", "mlx/cpu", "mlx/cuda",
                                        "tensorfold/cuda"}


def test_the_manifest_of_a_converted_engine_is_a_source_build_after_generate():
    """llama.cpp's committed params — what the Dockerfile is generated from — build it."""

    # Given the committed params of the converted engine
    doc = json.loads((REPO / "containers/engines/params/llama.cpp.json").read_text())

    # When  each variant is read
    rows = [_cell("llama.cpp", arch, v["install"], bool(v.get("prebuilt")))
            for arch, v in doc["variants"].items()]

    # Then  none claims to be prebuilt and every one compiles
    assert [r["arch"] for r in rows] == ["cuda", "rocm", "vulkan", "cpu"]
    assert not any(r["prebuilt"] for r in rows)
    assert guard.findings(rows) == []


def test_an_unpinned_clone_is_a_finding():
    """A source build must land on the pinned sha/tag; cloning `main` builds whatever is there today."""

    # Given a cell that clones a branch and builds it
    row = _cell("newengine", "cpu", [
        "git clone --depth 1 https://example.invalid/newengine.git /src",
        "cmake -B /src/build && cmake --build /src/build",
    ])

    # When  the guard looks at it
    result = guard.findings([row])

    # Then  the missing pin is the finding
    assert len(result) == 1 and "unpinned reference" in result[0][1]


def test_a_pinned_clone_passes():
    """A sha or a version tag is a pin, and either one satisfies the guard."""

    # Given a cell pinned by sha, and one pinned by tag
    by_sha = _cell("a", "cpu", ["git clone https://x.invalid/a.git /s",
                                "git -C /s checkout -q 5226de53a23fd5248658559b0eb876f6fc0c249a",
                                "cmake -B /s/b && cmake --build /s/b"])
    by_tag = _cell("b", "cpu", ["git clone -b v0.1.43 --depth 1 https://x.invalid/b.git /s",
                                "cmake -B /s/b && cmake --build /s/b"])

    # When  the guard looks at them
    # Then  both build from a fixed reference and pass
    assert guard.findings([by_sha, by_tag]) == []


def test_a_cell_whose_image_is_built_from_its_own_upstream_image_is_a_finding(tmp_path, monkeypatch):
    """The llama.cpp regression: `prebuilt: false` while the Dockerfile only starts FROM its image."""

    # Given a generated Dockerfile that starts from the engine's official image
    d = tmp_path / "containers" / "engines" / "dockerfiles" / "newengine"
    d.mkdir(parents=True)
    (d / "Dockerfile.cpu").write_text("FROM ghcr.io/newengine/newengine:latest AS build\n")
    monkeypatch.setattr(guard, "REPO_ROOT", str(tmp_path))
    row = _cell("newengine", "cpu", ["cmake -B b && cmake --build b"])

    # When  the guard looks at it
    result = guard.findings([row])

    # Then  it names the upstream base
    assert len(result) == 1 and "upstream build of it" in result[0][1]

    # And a cell built on the shared llgenie base is fine
    (d / "Dockerfile.cpu").write_text("FROM llgenie/base-cpu:abcd AS build\n")
    assert guard.findings([row]) == []
