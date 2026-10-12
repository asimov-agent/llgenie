"""Daily engine pin bump (issue #107, feat-engine-bump-daily).

Locks openspec/changes/feat-engine-bump-daily/specs/engine-bump-daily/spec.md.
Hermetic: fixture git repos are REAL git repos created in the test (not mocked
subprocess calls), so plan/derive run against real git. No network, no skips.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml

import scripts.engine_bump as eb
import scripts.engine_deps as engine_deps
import scripts.engine_params_derive as epd
import scripts.engine_skills as es

REPO = Path(__file__).resolve().parent.parent


def _git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    assert p.returncode == 0, f"git {' '.join(args)} failed: {p.stderr}"
    return p.stdout.strip()


def _make_repo(tmp_path: Path, name: str, files: dict[str, str]) -> Path:
    """Create a real git repo with the given files at HEAD."""
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    for path, content in files.items():
        p = repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def _commit(repo: Path, files: dict[str, str], msg: str = "change") -> str:
    for path, content in files.items():
        p = repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", msg)
    return _git(repo, "rev-parse", "HEAD")


def _skill(tmp_path: Path, repo_url: str, ref: str, ref_kind: str, pinned: str,
           sid: str = "testengine", **extra) -> dict:
    """Write a minimal SKILL.md into a temp skills dir and load it."""
    d = tmp_path / "skills" / "engines" / sid
    d.mkdir(parents=True)
    lines = [
        "---",
        f"name: engine-{sid}",
        f"engine: {sid}",
        f"id: {sid}",
        f"repo: {repo_url}",
        f"ref: {ref}",
        f"ref_kind: {ref_kind}",
        f"pinned: {pinned}",
        'verified: "2026-10-05"',
        "license: MIT",
        "servable: true",
        "backends: [cuda, rocm, vulkan, metal, cpu]",
        "os: [linux, darwin]",
        "formats: [gguf]",
        "upstream_watch: [CMakeLists.txt]",
    ]
    lines += _yaml_lines(extra, 0)
    lines.append("---")
    lines.append("# body")
    (d / "SKILL.md").write_text("\n".join(lines) + "\n")
    return es.load_skill(d / "SKILL.md")


def _yaml_lines(data, indent: int) -> list[str]:
    """Render a nested dict/list as the strict YAML subset the parser accepts."""
    pad = "  " * indent
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                out.append(f"{pad}{k}:")
                out += _yaml_lines(v, indent + 1)
            else:
                val = f'"{v}"' if isinstance(v, str) and v.startswith("{") else v
                out.append(f"{pad}{k}: {val}")
    elif isinstance(data, list):
        for v in data:
            if isinstance(v, (dict, list)):
                out.append(f"{pad}-")
                out += _yaml_lines(v, indent + 1)
            else:
                out.append(f"{pad}- {v}")
    return out


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

def test_plan_branch_resolves_head_sha(tmp_path):
    """A branch skill resolves the head sha and is in the plan only when moved."""
    repo = _make_repo(tmp_path, "up", {"CMakeLists.txt": "option(GGML_X ON)"})
    head = _git(repo, "rev-parse", "HEAD")
    skill = _skill(tmp_path, str(repo), "master", "branch", "a" * 40)
    # monkeypatch load_skills to return our skill
    orig = es.load_skills
    es.load_skills = lambda: {"testengine": skill}
    try:
        rows = eb.plan("testengine")
    finally:
        es.load_skills = orig
    assert len(rows) == 1
    assert rows[0]["new_sha"] == head
    assert rows[0]["new_ref"] == "master"
    assert rows[0]["status"] == "bump"


def test_plan_tag_picks_highest_stable_same_shape(tmp_path):
    """Tag skill picks the highest stable vX.Y.Z, no -rc, peeled sha.

    The pin must be older than that tag: plan() never moves backwards, so a
    pin of v0.40.3 against a highest tag of v0.40.0 is an empty plan, not a bump.
    """

    # Given an upstream whose highest stable tag is v0.40.0, and a pin behind it
    repo = _make_repo(tmp_path, "up", {"f": "x"})
    for tag in ("v0.9.7-rc1", "v0.10.0", "v0.9.10", "v0.40.0"):
        _git(repo, "tag", tag)
    skill = _skill(tmp_path, str(repo), "v0.9.0", "tag", "a" * 40)

    # When plan runs
    orig = es.load_skills
    es.load_skills = lambda: {"testengine": skill}
    try:
        rows = eb.plan("testengine")
    finally:
        es.load_skills = orig

    # Then the highest stable tag wins, the rc is ignored, and the sha is peeled
    assert rows[0]["new_ref"] == "v0.40.0"
    assert rows[0]["new_sha"]  # peeled sha present


def test_plan_never_moves_backwards(tmp_path):
    """A pin newer than the highest upstream tag is skipped."""
    repo = _make_repo(tmp_path, "up", {"f": "x"})
    _git(repo, "tag", "v0.10.0")
    skill = _skill(tmp_path, str(repo), "v0.40.3", "tag", "a" * 40)
    orig = es.load_skills
    es.load_skills = lambda: {"testengine": skill}
    try:
        rows = eb.plan("testengine")
    finally:
        es.load_skills = orig
    assert rows == []


def test_plan_lookup_failure_continues(tmp_path):
    """A failing ls-remote is reported; other engines still in the plan."""
    good = _make_repo(tmp_path, "good", {"f": "x"})
    head = _git(good, "rev-parse", "HEAD")
    s1 = _skill(tmp_path, str(good), "master", "branch", "a" * 40)
    s2 = _skill(tmp_path, str(good), "master", "branch", "a" * 40, sid="badengine")
    s2["repo"] = "https://nonexistent.invalid/repo.git"
    orig = es.load_skills
    es.load_skills = lambda: {"testengine": s1, "badengine": s2}
    try:
        rows = eb.plan()
    finally:
        es.load_skills = orig
    by_id = {r["id"]: r for r in rows}
    assert by_id["badengine"]["status"] == "lookup failed"
    assert by_id["testengine"]["new_sha"] == head


# ---------------------------------------------------------------------------
# Pin
# ---------------------------------------------------------------------------

def test_pin_edit_is_surgical(tmp_path):
    """Only pinned/ref/version/verified change; every other byte identical."""
    sid = "testengine"
    d = tmp_path / "skills" / "engines" / sid
    d.mkdir(parents=True)
    path = d / "SKILL.md"
    path.write_text(
        "---\n"
        "name: engine-testengine\n"
        "id: testengine\n"
        "ref: v0.40.3\n"
        "ref_kind: tag\n"
        "version: v0.40.3\n"
        f"pinned: {'0' * 40}\n"
        'verified: "2026-10-05"\n'
        "license: MIT\n"
        "---\n"
        "# body\n"
    )
    orig = es.SKILLS_DIR
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    try:
        new_text = eb.pin(sid, "v0.40.0", "1" * 40, dry=True)
    finally:
        es.SKILLS_DIR = orig
    assert f"pinned: {'1' * 40}" in new_text
    assert "ref: v0.40.0" in new_text
    assert "version: v0.40.0" in new_text
    assert 'verified: "' in new_text
    # body and other keys untouched
    assert "# body" in new_text
    assert "license: MIT" in new_text
    assert "name: engine-testengine" in new_text


# ---------------------------------------------------------------------------
# Derive
# ---------------------------------------------------------------------------

def test_derive_deterministic(tmp_path):
    """Same sha -> byte-identical findings."""
    repo = _make_repo(tmp_path, "up", {"CMakeLists.txt": "option(GGML_X ON)"})
    skill = _skill(tmp_path, str(repo), "master", "branch", "a" * 40,
                   derive={"cmake": {"options_from": ["CMakeLists.txt"]}})
    sha = _git(repo, "rev-parse", "HEAD")
    a = json.dumps(epd.derive(skill, sha, repo_dir=repo), sort_keys=True)
    b = json.dumps(epd.derive(skill, sha, repo_dir=repo), sort_keys=True)
    assert a == b


def test_e2_rename_auto_applied(tmp_path):
    """llama_option_depr(OLD NEW) -> skill -DOLD becomes -DNEW."""
    repo = _make_repo(tmp_path, "up", {
        "CMakeLists.txt": "option(GGML_CUDA ON)\nllama_option_depr(FATAL_ERROR LLAMA_CUBLAS GGML_CUDA)\n"})
    skill = _skill(tmp_path, str(repo), "master", "branch", "a" * 40,
                   cmake_flags={"cuda": "-DLLAMA_CUBLAS=ON"},
                   derive={"cmake": {"options_from": ["CMakeLists.txt"],
                                     "renames_from": "CMakeLists.txt"}})
    sha = _git(repo, "rev-parse", "HEAD")
    f = epd.derive(skill, sha, repo_dir=repo)
    assert f["auto"]["renamed_flags"]["LLAMA_CUBLAS"] == "GGML_CUDA"


def test_e3_removed_option_hard_fails(tmp_path):
    """An option present at the old sha and gone at the new sha hard-fails."""
    repo = _make_repo(tmp_path, "up", {"CMakeLists.txt": "option(GGML_X ON)"})
    old = _git(repo, "rev-parse", "HEAD")
    new = _commit(repo, {"CMakeLists.txt": "option(GGML_Y ON)"})
    skill = _skill(tmp_path, str(repo), "master", "branch", old,
                   cmake_flags={"cuda": "-DGGML_X=ON"},
                   derive={"cmake": {"options_from": ["CMakeLists.txt"]}})
    with pytest.raises(epd.HardFail, match="GGML_X"):
        epd.derive(skill, new, repo_dir=repo, old_sha=old)


def test_bump_still_pins_on_hard_fail(tmp_path):
    """A derive hard-fail is recorded, not fatal: the pin still moves."""
    repo = _make_repo(tmp_path, "up", {"CMakeLists.txt": "option(GGML_X ON)"})
    old = _git(repo, "rev-parse", "HEAD")
    new = _commit(repo, {"CMakeLists.txt": "option(GGML_Y ON)"})
    skill = _skill(tmp_path, str(repo), "master", "branch", old,
                   cmake_flags={"cuda": "-DGGML_X=ON"},
                   derive={"cmake": {"options_from": ["CMakeLists.txt"]}})
    orig_load = es.load_skills
    orig_skills_dir = es.SKILLS_DIR
    es.load_skills = lambda: {"testengine": skill}
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    orig_regen = eb._regen_guard
    eb._regen_guard = lambda sid: []
    try:
        rows = eb.bump("testengine")
    finally:
        es.load_skills = orig_load
        es.SKILLS_DIR = orig_skills_dir
        eb._regen_guard = orig_regen
    assert len(rows) == 1
    assert rows[0]["hard_fail"]  # recorded, not fatal
    # the pin moved in the skill file
    text = (tmp_path / "skills" / "engines" / "testengine" / "SKILL.md").read_text()
    assert f"pinned: {new}" in text


def test_bump_rewrites_hardcoded_pin_asserts(tmp_path, monkeypatch):
    """A bump rewrites the same pin literals the unit suite asserts (issue #144).

    The failing shapes are the full sha, its 8-char image-tag prefix, the tag
    (`v0.40.3`) and the tag with the leading v stripped (`0.40.3-rocm`). A
    historical record and another engine's pin must be left alone.
    """

    # Given a skill whose pin the unit suite hardcodes, and a newer upstream tag
    repo = _make_repo(tmp_path, "up", {"CMakeLists.txt": "option(GGML_X ON)"})
    old = "a" * 40
    new = _git(repo, "rev-parse", "HEAD")
    skill = _skill(tmp_path, str(repo), "v0.40.3", "tag", old, version="v0.40.3")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_pins.py").write_text(
        'assert "releases/download/v0.40.3/ollama.tar.zst" in steps\n'
        'assert "FROM ollama/ollama:0.40.3-rocm" in df("ollama", "rocm")\n'
        f'assert tag.startswith("llgenie/ollama:{old[:8]}-")\n'
        f'assert pinned == "{old}"\n'
        'assert "v0.31.0" in other  # another engine, must survive\n'
    )
    (tmp_path / "README.md").write_text(f"tag `llgenie/ollama:{old[:8]}-<hash>-cuda`\n")
    record = tmp_path / "openspec" / "changes" / "old"
    record.mkdir(parents=True)
    (record / "spec.md").write_text("pinned at v0.40.3\n")

    # When the bump runs (sha moved, tag string did not)
    monkeypatch.setattr(eb, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(es, "load_skills", lambda: {"testengine": skill})
    monkeypatch.setattr(es, "SKILLS_DIR", tmp_path / "skills" / "engines")
    monkeypatch.setattr(eb, "_regen_guard", lambda sid: [])
    monkeypatch.setattr(eb, "plan", lambda eid: [{
        "id": eid, "old_sha": old, "new_sha": new, "old_ref": "v0.40.3",
        "new_ref": "v0.41.0", "status": "moved"}])
    eb.bump("testengine")

    # Then every shape of this engine's pin moved, and nothing else did
    got = (tests / "test_pins.py").read_text()
    assert "v0.41.0" in got and "v0.40.3" not in got
    assert "0.41.0-rocm" in got and "0.40.3-rocm" not in got
    assert f"llgenie/ollama:{new[:8]}-" in got
    assert f'pinned == "{new}"' in got
    assert "v0.31.0" in got
    assert f"llgenie/ollama:{new[:8]}-" in (tmp_path / "README.md").read_text()
    assert (record / "spec.md").read_text() == "pinned at v0.40.3\n"


def test_e4_recipe_flag_mirrored(tmp_path):
    """A mirrored recipe flag is auto-added; non-mirrored is report-only."""
    repo = _make_repo(tmp_path, "up", {
        "CMakeLists.txt": "option(GGML_BACKEND_DL OFF)\noption(GGML_EXTRA OFF)\n",
        ".devops/cuda.Dockerfile": "RUN cmake -B build -S . -DGGML_BACKEND_DL=ON -DGGML_EXTRA=ON\n"})
    skill = _skill(tmp_path, str(repo), "master", "branch", "a" * 40,
                   derive={"cmake": {"options_from": ["CMakeLists.txt"],
                                     "recipe": {"cuda": ".devops/cuda.Dockerfile"},
                                     "mirror": ["GGML_BACKEND_DL"]}})
    sha = _git(repo, "rev-parse", "HEAD")
    f = epd.derive(skill, sha, repo_dir=repo)
    assert f["auto"]["mirrored_flags"]["GGML_BACKEND_DL"] == "ON"
    assert "GGML_EXTRA" in f["report"]["recipe_flags"]["cuda"]


def test_e5_toolchain_bump(tmp_path):
    """ARG CUDA_VERSION -> toolchain.cuda."""
    repo = _make_repo(tmp_path, "up", {
        "CMakeLists.txt": "option(GGML_CUDA ON)",
        ".devops/cuda.Dockerfile": "ARG CUDA_VERSION=13.0.3\n"})
    skill = _skill(tmp_path, str(repo), "master", "branch", "a" * 40,
                   derive={"cmake": {"options_from": ["CMakeLists.txt"]},
                           "toolchain": {"cuda": {"file": ".devops/cuda.Dockerfile",
                                                  "arg": "CUDA_VERSION"}}})
    sha = _git(repo, "rev-parse", "HEAD")
    f = epd.derive(skill, sha, repo_dir=repo)
    assert f["auto"]["toolchain"]["cuda"] == "13.0.3"


def test_e6_gpu_targets_var_renamed(tmp_path):
    """HIP CMakeLists reading GPU_TARGETS -> hw_flags uses GPU_TARGETS."""
    repo = _make_repo(tmp_path, "up", {
        "CMakeLists.txt": "option(GGML_HIP ON)",
        "ggml/src/ggml-hip/CMakeLists.txt": "set(GPU_TARGETS ...)\n"})
    skill = _skill(tmp_path, str(repo), "master", "branch", "a" * 40,
                   derive={"cmake": {"options_from": ["CMakeLists.txt"]},
                           "gpu_targets_var": {"file": "ggml/src/ggml-hip/CMakeLists.txt",
                                               "candidates": ["GPU_TARGETS", "AMDGPU_TARGETS"]}})
    sha = _git(repo, "rev-parse", "HEAD")
    f = epd.derive(skill, sha, repo_dir=repo)
    assert f["auto"]["gpu_targets_var"] == "GPU_TARGETS"


def test_e7_torch_backend_updated(tmp_path):
    """torch==2.9.0+cu128 -> cu130 -> torch_backend updated."""
    repo = _make_repo(tmp_path, "up", {
        "pyproject.toml": 'requires-python = ">=3.10"\ntorch==2.9.0+cu130\n'})
    skill = _skill(tmp_path, str(repo), "master", "branch", "a" * 40,
                   derive={"python": {"pyproject": "pyproject.toml"}})
    sha = _git(repo, "rev-parse", "HEAD")
    f = epd.derive(skill, sha, repo_dir=repo)
    assert f["auto"]["torch_backend"] == "cu130"


def test_e8_removed_launch_flag_hard_fails(tmp_path):
    """A launch flag absent from flags_from hard-fails."""
    repo = _make_repo(tmp_path, "up", {"common/arg.cpp": "--alias\n--jinja\n"})
    skill = _skill(tmp_path, str(repo), "master", "branch", "a" * 40,
                   launch="{binary} --alias --gone",
                   derive={"launch": {"flags_from": "common/arg.cpp"}})
    sha = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(epd.HardFail, match="--gone"):
        epd.derive(skill, sha, repo_dir=repo)


def test_e9_watch_diff_maps_backends(tmp_path):
    """Only ggml-cuda changed -> report lists cuda only."""
    repo = _make_repo(tmp_path, "up", {
        "CMakeLists.txt": "option(GGML_X ON)",
        "ggml/src/ggml-cuda/CMakeLists.txt": "set(X 1)\n"})
    old = _git(repo, "rev-parse", "HEAD")
    new = _commit(repo, {"ggml/src/ggml-cuda/CMakeLists.txt": "set(X 2)\n"})
    skill = _skill(tmp_path, str(repo), "master", "branch", old,
                   upstream_watch=["ggml/src/ggml-cuda/CMakeLists.txt"])
    f = epd.derive(skill, new, repo_dir=repo, old_sha=old)
    assert f["report"]["watch_backends"] == ["cuda"]


def test_unparseable_recipe_hard_fails(tmp_path):
    """A recipe Dockerfile with no cmake line hard-fails naming the path."""
    repo = _make_repo(tmp_path, "up", {
        "CMakeLists.txt": "option(GGML_X ON)",
        ".devops/cuda.Dockerfile": "RUN echo hi\n"})
    skill = _skill(tmp_path, str(repo), "master", "branch", "a" * 40,
                   derive={"cmake": {"options_from": ["CMakeLists.txt"],
                                     "recipe": {"cuda": ".devops/cuda.Dockerfile"}}})
    sha = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(epd.HardFail, match="cuda.Dockerfile"):
        epd.derive(skill, sha, repo_dir=repo)


# ---------------------------------------------------------------------------
# Regen guard + changed-engines scoping
# ---------------------------------------------------------------------------

def test_regen_guard_isolates_engine(tmp_path, monkeypatch):
    """A bump of A that changes B's params fails the job."""

    # Given make succeeds and git status shows another engine's params
    def fake_run(cmd, **kw):
        out = " M containers/engines/params/other.json\n" if cmd[:2] == ["git", "status"] else ""
        return type("P", (), {"returncode": 0, "stdout": out, "stderr": ""})()

    # When the guard runs for testengine
    monkeypatch.setattr(eb, "_run", fake_run)

    # Then it fails naming the other engine
    with pytest.raises(SystemExit, match="outside testengine"):
        eb._regen_guard("testengine")


def test_regen_guard_rejects_another_engines_skill(tmp_path, monkeypatch):
    """Another engine's SKILL.md is not this bump."""

    # Given git status shows a different engine's skill
    def fake_run(cmd, **kw):
        out = " M skills/engines/other/SKILL.md\n" if cmd[:2] == ["git", "status"] else ""
        return type("P", (), {"returncode": 0, "stdout": out, "stderr": ""})()

    # When the guard runs for testengine
    monkeypatch.setattr(eb, "_run", fake_run)

    # Then it fails naming the other skill
    with pytest.raises(SystemExit, match="outside testengine"):
        eb._regen_guard("testengine")


def test_regen_guard_ignores_make_directory_lines(tmp_path, monkeypatch):
    """make's Entering-directory line is not a changed file (run 38109392303).

    The regen is scoped to the bumped engine: rewriting every engine's params
    would fail this guard, and the bump job would never open a PR."""

    # Given make prints a directory line and git status shows only this engine
    seen = []

    def fake_run(cmd, **kw):
        seen.append(cmd)
        if cmd[:1] == ["make"]:
            return type("P", (), {"returncode": 0,
                                  "stdout": "make[1]: Entering directory '/work/llgenie'\n",
                                  "stderr": ""})()
        return type("P", (), {"returncode": 0,
                              "stdout": " M containers/engines/params/testengine.json\n",
                              "stderr": ""})()

    # When the guard runs
    monkeypatch.setattr(eb, "_run", fake_run)
    changed = eb._regen_guard("testengine")

    # Then only the bumped engine's params file is reported, and regen was scoped
    assert changed == ["containers/engines/params/testengine.json"]
    assert ["make", "generate-engine-params", "ENGINE=testengine"] in seen


def test_regen_guard_allows_the_bumped_skill(tmp_path, monkeypatch):
    """The pin edit of the bumped engine's SKILL.md is the bump, not a stray file.

    Run 38110707179 failed every bump job on skills/engines/<id>/SKILL.md."""

    # Given git status shows the pin edit plus this engine's params
    def fake_run(cmd, **kw):
        if cmd[:1] == ["make"]:
            return type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        return type("P", (), {"returncode": 0, "stdout": (
            " M skills/engines/testengine/SKILL.md\n"
            " M containers/engines/params/testengine.json\n"
            " M containers/engines/dockerfiles/testengine/Dockerfile.cpu\n"), "stderr": ""})()

    # When the guard runs
    monkeypatch.setattr(eb, "_run", fake_run)
    changed = eb._regen_guard("testengine")

    # Then the skill, params and dockerfile are allowed
    assert changed == [
        "skills/engines/testengine/SKILL.md",
        "containers/engines/params/testengine.json",
        "containers/engines/dockerfiles/testengine/Dockerfile.cpu",
    ]


def test_changed_engines_scopes_matrix(tmp_path):
    """An unchanged tree is the placeholder row. A bump PR is not unchanged.

    Comparing this checkout to origin/main failed linux / unit on every
    engine-bump PR from that run: #165 tensorfold, #166 llama.cpp-prism,
    #167 strata, #168 llama.cpp. Each pin move changes that engine's image
    tag, so the matrix lists the engine. That is the scope those PRs want.
    The unchanged case is this commit against itself. A moved pin is
    test_engine_image_matrix.py::test_matrix_keeps_only_the_engine_whose_pin_changed.
    """
    import scripts.engine_image as ei
    # HEAD against HEAD: one placeholder row, never an empty include
    # (GitHub fails a workflow whose matrix include list is empty)
    rows = ei.matrix(ci=True, changed="HEAD")
    assert rows == [{"engine": "none", "backend": "cpu", "variant": "none",
                     "smoke": False, "test": "detect", "chat": ""}]
    # full matrix is non-empty and has no placeholder
    full = ei.matrix(ci=True)
    assert len(full) > 1
    assert all(r["engine"] != "none" for r in full)


def test_bump_daily_dry_no_push(tmp_path):
    """bump-daily --dry prints the plan and creates no branch/PR."""
    repo = _make_repo(tmp_path, "up", {"CMakeLists.txt": "option(GGML_X ON)"})
    skill = _skill(tmp_path, str(repo), "master", "branch", "a" * 40)
    orig = es.load_skills
    es.load_skills = lambda: {"testengine": skill}
    try:
        rc = eb.bump_daily(dry=True)
    finally:
        es.load_skills = orig
    assert rc == 0


# ---------------------------------------------------------------------------
# Apply: derived params are written into the skill (the "new args added" proof)
# ---------------------------------------------------------------------------

def _write_skill(tmp_path, text: str) -> Path:
    d = tmp_path / "skills" / "engines" / "testengine"
    d.mkdir(parents=True)
    p = d / "SKILL.md"
    p.write_text(text)
    return p


def test_apply_renames_flag_in_cmake_flags(tmp_path):
    """E2: a renamed -DOLD becomes -DNEW in cmake_flags."""
    p = _write_skill(tmp_path, (
        "---\n"
        "id: testengine\n"
        "cmake_flags:\n"
        '  cuda: "-DLLAMA_CUBLAS=ON -DGGML_METAL=OFF"\n'
        "---\n"
        "# body\n"))
    orig = es.SKILLS_DIR
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    try:
        changed = eb._apply_findings("testengine",
                                     {"auto": {"renamed_flags": {"LLAMA_CUBLAS": "GGML_CUDA"}}})
    finally:
        es.SKILLS_DIR = orig
    assert any("rename" in c for c in changed)
    text = p.read_text()
    assert "-DGGML_CUDA=ON" in text
    assert "-DLLAMA_CUBLAS" not in text


def test_apply_mirrors_recipe_flag(tmp_path):
    """E4: a mirrored recipe flag is added to cmake_flags.cuda."""
    p = _write_skill(tmp_path, (
        "---\n"
        "id: testengine\n"
        "cmake_flags:\n"
        '  cuda: "-DGGML_CUDA=ON"\n'
        "---\n"
        "# body\n"))
    orig = es.SKILLS_DIR
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    try:
        changed = eb._apply_findings("testengine",
                                     {"auto": {"mirrored_flags": {"GGML_BACKEND_DL": "ON"}}})
    finally:
        es.SKILLS_DIR = orig
    assert any("mirror" in c for c in changed)
    assert "-DGGML_BACKEND_DL=ON" in p.read_text()


def test_apply_toolchain_and_gpu_targets(tmp_path):
    """E5/E6: toolchain version and the GPU targets var are updated."""
    p = _write_skill(tmp_path, (
        "---\n"
        "id: testengine\n"
        "toolchain:\n"
        "  cuda: 12.8.1\n"
        "hw_flags:\n"
        "  rocm:\n"
        "    gpu_targets: \"'-DAMDGPU_TARGETS={gpu_targets}'\"\n"
        "---\n"
        "# body\n"))
    orig = es.SKILLS_DIR
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    try:
        changed = eb._apply_findings("testengine", {"auto": {
            "toolchain": {"cuda": "13.0.3"},
            "gpu_targets_var": "GPU_TARGETS"}})
    finally:
        es.SKILLS_DIR = orig
    text = p.read_text()
    assert "cuda: 13.0.3" in text
    assert "GPU_TARGETS" in text
    assert "AMDGPU_TARGETS" not in text


def test_apply_hard_fail_applies_nothing(tmp_path):
    """A hard-fail finding is not applied — nothing is guessed."""
    p = _write_skill(tmp_path, (
        "---\n"
        "id: testengine\n"
        "cmake_flags:\n"
        '  cuda: "-DGGML_X=ON"\n'
        "---\n"
        "# body\n"))
    orig = es.SKILLS_DIR
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    try:
        changed = eb._apply_findings("testengine", {"hard_fail": "cmake option GGML_X gone"})
    finally:
        es.SKILLS_DIR = orig
    assert changed == []
    assert "-DGGML_X=ON" in p.read_text()  # untouched


def test_full_bump_lands_new_flag_in_params(tmp_path):
    """Happy path, empty arg list -> bump -> new args land in the params JSON
    that `make build-engine` reads, for every arch the engine supports.

    The skill starts with NO cmake flags. The new upstream commit's recipe adds
    `-DGGML_BACKEND_DL=ON` (E4 mirror). The bump must pick it up and write it into
    the generated params for each arch, so the docker build uses the new args.
    """
    # fixture upstream: old sha has no recipe; new sha's cuda+rocm recipes add a flag
    repo = _make_repo(tmp_path, "up", {
        "CMakeLists.txt": "option(GGML_BACKEND_DL OFF)\n",
        ".devops/cuda.Dockerfile": "RUN cmake -B build -S . -DGGML_BACKEND_DL=ON\n",
        ".devops/rocm.Dockerfile": "RUN cmake -B build -S . -DGGML_BACKEND_DL=ON\n"})
    old = _git(repo, "rev-parse", "HEAD")
    new = _commit(repo, {
        ".devops/cuda.Dockerfile": "RUN cmake -B build -S . -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON\n",
        ".devops/rocm.Dockerfile": "RUN cmake -B build -S . -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON\n"})
    # empty arg list: no cmake_flags at all
    skill = _skill(tmp_path, str(repo), "master", "branch", old,
                   derive={"cmake": {"options_from": ["CMakeLists.txt"],
                                     "recipe": {"cuda": ".devops/cuda.Dockerfile",
                                                "rocm": ".devops/rocm.Dockerfile"},
                                     "mirror": ["GGML_BACKEND_DL", "GGML_CPU_ALL_VARIANTS"]}})
    orig_load = es.load_skills
    orig_skills_dir = es.SKILLS_DIR
    es.load_skills = lambda: {"testengine": skill}
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    orig_regen = eb._regen_guard
    # capture the params the regen would write, without touching the real repo
    captured = {}
    def fake_regen(sid):
        # re-read the skill from disk (as `make generate-engine-params` does)
        from scripts.engine_skills import load_skill
        skill_path = tmp_path / "skills" / "engines" / sid / "SKILL.md"
        params = es.generate_params(load_skill(skill_path))
        captured["params"] = params
        return []
    eb._regen_guard = fake_regen
    try:
        rows = eb.bump("testengine")
    finally:
        es.load_skills = orig_load
        es.SKILLS_DIR = orig_skills_dir
        eb._regen_guard = orig_regen
    assert len(rows) == 1
    assert rows[0]["hard_fail"] is None
    # the skill file now carries the mirrored flag
    text = (tmp_path / "skills" / "engines" / "testengine" / "SKILL.md").read_text()
    assert "-DGGML_BACKEND_DL=ON" in text
    # the regenerated params (what make build-engine reads) carry the new args
    params = captured["params"]
    assert params["pinned"] == new
    for backend in ("cuda", "rocm"):
        native = params["native"][backend]["cmake_flags"]
        assert "-DGGML_BACKEND_DL=ON" in native, f"{backend} missing new flag: {native}"
        assert "-DGGML_CPU_ALL_VARIANTS=ON" in native, f"{backend} missing new flag: {native}"


def _pr_step(workflow: str, job: str) -> str:
    """The checkout and the PR-opening step of one job."""
    doc = yaml.safe_load((REPO / ".github" / "workflows" / workflow).read_text())
    steps = doc["jobs"][job]["steps"]
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
    opening = next(s for s in steps if "pr create" in s.get("run", ""))
    return yaml.dump({"checkout": checkout, "open": opening})


def test_bump_pr_uses_owner_pat():
    """The bump job checks out, pushes and opens the PR as the token owner.

    A github-actions[bot] PR holds CI for approval (run 38113858713)."""

    # Given the bump workflow
    text = _pr_step("engine-bump.yml", "bump")

    # When the job checks out and opens the PR
    # Then those steps use the owner PAT and the commit is not the bot's
    assert "secrets.BUMP_TOKEN" in text
    assert "secrets.GITHUB_TOKEN" not in text
    assert "github-actions[bot]" not in text
    assert "gh api user" in text


def test_sync_pr_uses_owner_pat():
    """The sync job checks out, pushes and opens the PR as the token owner."""

    # Given the registry-sync workflow
    text = _pr_step("registry-sync.yml", "sync")

    # When the job checks out and opens the PR
    # Then those steps use the owner PAT and the commit is not the bot's
    assert "secrets.BUMP_TOKEN" in text
    assert "secrets.GITHUB_TOKEN" not in text
    assert "github-actions[bot]" not in text
    assert "gh api user" in text


def test_guard_keeps_default_token():
    """The collaborator guard job still uses GITHUB_TOKEN, and neither workflow merges.

    The file header names BUMP_TOKEN (issue #136). Splitting on the next job key
    includes that header, so the assert reads the guard job, not the preamble.
    """

    # Given both workflows
    for name in ("engine-bump.yml", "registry-sync.yml"):
        doc = yaml.safe_load((REPO / ".github" / "workflows" / name).read_text())
        text = (REPO / ".github" / "workflows" / name).read_text()

        # When the guard job checks the actor
        guard = yaml.dump(doc["jobs"]["guard"])

        # Then that job uses the default token, and nothing merges a PR
        assert "secrets.GITHUB_TOKEN" in guard
        assert "secrets.BUMP_TOKEN" not in guard
        assert "gh pr merge" not in text


def test_apply_toolchain_does_not_clobber_prereqs(tmp_path):
    """Toolchain and the GPU-targets rename stay in their own block.

    A whole-file rewrite put `12.8.1` on `prereqs.cuda` and dropped
    `AMDGPU_TARGETS` from `derive.gpu_targets_var.candidates` (PR #149).
    """

    # Given a skill whose prereqs and derive candidates share those names
    p = _write_skill(tmp_path, (
        "---\n"
        "id: testengine\n"
        "prereqs:\n"
        "  cuda: [nvcc]\n"
        "  rocm: [hipconfig]\n"
        "toolchain:\n"
        "  cuda: 12.8.1\n"
        "hw_flags:\n"
        "  rocm:\n"
        "    gpu_targets: \"'-DAMDGPU_TARGETS={gpu_targets}'\"\n"
        "derive:\n"
        "  gpu_targets_var:\n"
        "    candidates: [GPU_TARGETS, AMDGPU_TARGETS]\n"
        "---\n"
        "# AMDGPU_TARGETS is a legacy alias for GPU_TARGETS.\n"))
    orig = es.SKILLS_DIR
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    try:
        # When the bump applies a toolchain bump and a GPU-targets rename
        eb._apply_findings("testengine", {"auto": {
            "toolchain": {"cuda": "13.0.3", "rocm": "7.2.1"},
            "gpu_targets_var": "GPU_TARGETS"}})
    finally:
        es.SKILLS_DIR = orig
    text = p.read_text()

    # Then only the toolchain block and hw_flags moved
    assert "  cuda: 13.0.3" in text
    assert "  cuda: [nvcc]" in text
    assert "  rocm: [hipconfig]" in text
    assert "candidates: [GPU_TARGETS, AMDGPU_TARGETS]" in text
    assert "'-DGPU_TARGETS={gpu_targets}'" in text
    assert "GPU_TARGETS is a legacy alias for GPU_TARGETS." in text


def test_apply_release_archive_replaces_pip_install(tmp_path):
    """A release of native archives replaces a git+ pip install."""

    # Given a skill that pip-installs the engine from git, and a release whose
    # assets are checksummed native archives
    p = _write_skill(tmp_path, (
        "---\n"
        "id: testengine\n"
        "repo: https://github.com/example/engine\n"
        "ref: v1.0.5\n"
        "version: v1.0.5\n"
        "backends: [cuda, metal]\n"
        "install:\n"
        "  metal:\n"
        "    - \"uv tool install --force 'engine @ git+{repo}.git@v{version}'\"\n"
        "  cuda:\n"
        "    - \"uv pip install --system 'engine @ git+{repo}.git@v{version}'\"\n"
        "binary: \"engine\"\n"
        "---\n"
        "# body\n"))
    assets = [{"name": n} for n in (
        "engine-1.0.5-linux-x86_64.tar.gz", "engine-1.0.5-linux-x86_64.tar.gz.sha256",
        "engine-1.0.5-macos-arm64.tar.gz", "engine-1.0.5-macos-arm64.tar.gz.sha256")]
    orig = es.SKILLS_DIR
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    try:
        # When the bump applies that release
        changed = eb._apply_findings("testengine", {"auto": {"release_assets": assets}})
    finally:
        es.SKILLS_DIR = orig
    text = p.read_text()

    # Then both backends download, checksum and unpack the archive, and the
    # skill points at the unpacked executable rather than the pip package
    assert "install=release-archive" in changed
    assert "git+" not in text
    assert "uv " not in text
    assert "engine-{version}-linux-x86_64.tar.gz" in text
    assert "engine-{version}-macos-arm64.tar.gz" in text
    assert "sha256sum -c" in text
    assert "shasum -a 256 -c" in text
    assert "--strip-components=1" in text
    assert "ln -sfn" in text
    skill = es.load_skill(p)
    assert skill["install"]["cuda"][0].startswith("mkdir -p")
    assert skill["install"]["cuda"][-1].startswith("exe=$(find ")
    assert skill["binary"] == "{prefix}/{version}/bin/{id}"
    assert skill["detect"] == "{binary} --version"


# A bump's only stand-ins are files for the two external systems: a local git
# remote (git insteadOf, so plan/clone speak the skill's GitHub URL) and one
# JSON file per release tag (urllib.request.urlopen). plan, derive, pin, apply,
# the pin rewrite and the regen guard all run. Versions are the shape of the
# bump PRs (vX.Y.Z, branch names) and are not the live pins: v0.6.5 and v0.1.43
# are hardcoded in this checkout, and the fixture repo is the only tree the
# rewrite is allowed to touch.
_MAKEFILE = (
    "generate-engine-params:\n"
    "\t@true\n"
    "\n"
    "sync-strata-models:\n"
    "\tmkdir -p data\n"
    "\tprintf '%s\\n' '{}' > data/strata_models.json\n"
)


class _ReleaseFile(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


def _github(slug: str) -> str:
    return f"https://github.com/fixture/{slug}"


def _archive_body(name: str, version: str, targets=("linux-x86_64", "macos-arm64"),
                  checksum: bool = True) -> dict:
    assets = []
    for target in targets:
        asset = f"{name}-{version}-{target}.tar.gz"
        assets.append({"name": asset})
        if checksum:
            assets.append({"name": asset + ".sha256"})
    return {"assets": assets}


def _write_release(releases: Path, slug: str, tag: str, body: dict) -> None:
    path = releases / "fixture" / slug / f"{tag}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body))


def _skill_text(*, sid: str, engine: str, repo: str, ref: str, ref_kind: str,
                pinned: str, backends: list[str], install: list[tuple[str, list[str]]],
                binary: str, detect: list[str], version: str = "") -> str:
    lines = [
        "---",
        f"name: engine-{sid}",
        f"engine: {engine}",
        f"id: {sid}",
        f"repo: {repo}",
        f"ref: {ref}",
        f"ref_kind: {ref_kind}",
    ]
    if version:
        lines.append(f"version: {version}")
    lines += [
        f"pinned: {pinned}",
        'verified: "2026-10-05"',
        "license: MIT",
        "servable: true",
        "backends: [" + ", ".join(backends) + "]",
        "install:",
    ]
    for backend, steps in install:
        lines.append(f"  {backend}:")
        for step in steps:
            lines.append('    - "' + step.replace("\\", "\\\\").replace('"', '\\"') + '"')
    lines.append(f'binary: "{binary}"')
    lines.extend(detect)
    lines += ["---", "# body"]
    return "\n".join(lines) + "\n"


def _moved_tag(tmp_path: Path, old_tag: str, new_tag: str, extra: str = "") -> tuple[Path, str, str]:
    """Two lightweight tags on different commits. The new sha does not contain the old prefix."""
    repo = _make_repo(tmp_path, "up", {"README.md": "old\n"})
    old = _git(repo, "rev-parse", "HEAD")
    _git(repo, "tag", old_tag)
    new = old
    for n in range(1, 9):
        new = _commit(repo, {"README.md": f"new {n}\n"})
        if old[:8] not in new and new[:8] not in old:
            break
    _git(repo, "tag", new_tag)
    if extra:
        _commit(repo, {"README.md": "extra\n"})
        _git(repo, "tag", extra)
    return repo, old, new


def _moved_branch(tmp_path: Path, branch: str) -> tuple[Path, str, str]:
    repo = _make_repo(tmp_path, "up", {"README.md": "old\n"})
    old = _git(repo, "rev-parse", "HEAD")
    new = old
    for n in range(1, 9):
        new = _commit(repo, {"README.md": f"new {n}\n"})
        if old[:8] not in new and new[:8] not in old:
            break
    if branch != "master":
        _git(repo, "branch", branch)
    return repo, old, new


def _checkout(tmp_path: Path, sid: str, skill: str, old: str, ref: str) -> tuple[Path, Path]:
    """A real llgenie git repo whose regen Makefile and pin asserts are files."""
    root = tmp_path / "llgenie"
    (root / "skills" / "engines" / sid).mkdir(parents=True)
    (root / "tests").mkdir()
    marker = f"{old}\n{old[:8]}\n{ref}\n"
    path = root / "skills" / "engines" / sid / "SKILL.md"
    path.write_text(skill)
    (root / "tests" / "test_pins.py").write_text(marker)
    (root / "README.md").write_text(marker)
    (root / "Makefile").write_text(_MAKEFILE)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "fixture")
    return root, path


def _bind_files(monkeypatch, checkout: Path, upstream: Path, github: str, releases: Path) -> list[str]:
    """GitHub URL -> local repo. Release URL -> JSON file. Nothing else is stubbed."""
    monkeypatch.setattr(es, "SKILLS_DIR", checkout / "skills" / "engines")
    monkeypatch.setattr(eb, "REPO_ROOT", checkout)
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    remote = github if github.endswith(".git") else github + ".git"
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{upstream.resolve()}/.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", remote)
    seen: list[str] = []

    def urlopen(req, timeout=None, *args, **kwargs):
        url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
        seen.append(url)
        match = re.search(r"https://api\.github\.com/repos/([^/]+/[^/]+)/releases/tags/([^/?#]+)$", url)
        if not match:
            raise urllib.error.URLError(url)
        path = releases / match.group(1) / f"{match.group(2)}.json"
        if not path.is_file():
            raise urllib.error.URLError(f"no release file {path}")
        return _ReleaseFile(path.read_bytes())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return seen


def _assert_pins_rewritten(checkout: Path, old: str, new: str, old_ref: str, new_ref: str) -> None:
    for rel in ("tests/test_pins.py", "README.md"):
        text = (checkout / rel).read_text()
        assert new in text
        assert new[:8] in text
        assert new_ref in text
        assert old not in text
        if old_ref != new_ref:
            assert old_ref not in text


def _pip_engine(sid: str, engine: str, github: str, ref: str, pinned: str,
                backends: list[str], install: list[tuple[str, list[str]]],
                binary: str, version: str = "") -> str:
    detect = [
        "detect:",
        "  cuda: \"python3 -c 'import importlib.metadata as m; print(m.version(\\\"" + sid + "\\\"))'\"",
    ]
    return _skill_text(sid=sid, engine=engine, repo=github, ref=ref, ref_kind="tag",
                       pinned=pinned, backends=backends, install=install, binary=binary,
                       detect=detect, version=version)


def _bump_tag(tmp_path, monkeypatch, *, sid, engine, slug, old_tag, new_tag,
              install, binary, backends=("cuda", "metal"), releases=None,
              extra_tag="", skill_ref="", skill_pin=""):
    """Real bump. `releases` maps a tag to a GitHub release JSON body."""
    upstream, old, new = _moved_tag(tmp_path, old_tag, new_tag, extra_tag)
    ref = skill_ref or old_tag
    pinned = skill_pin or old
    github = _github(slug)
    text = _pip_engine(sid, engine, github, ref, pinned, list(backends), install, binary,
                       version=ref)
    checkout, path = _checkout(tmp_path, sid, text, pinned, ref)
    seen = _bind_files(monkeypatch, checkout, upstream, github, tmp_path / "releases")
    for tag, body in (releases or {}).items():
        _write_release(tmp_path / "releases", slug, tag, body)
    rows = eb.bump(sid)
    return checkout, path, seen, old, new, rows


_TENSORFOLD_INSTALL = [
    ("metal", ["uv tool install --force 'tensorfold @ git+{repo}.git@v{version}'"]),
    ("cuda", ["uv pip install --system 'tensorfold @ git+{repo}.git@v{version}'"]),
]


def test_bump_reads_the_destination_release(tmp_path, monkeypatch):
    """A bump rewrites pip from the tag it moves to, while the skill still names the old one.

    derive() runs before pin(). The old tag's release file is absent. The
    destination tag's file has checksummed native archives. v9.1.0 -> v9.2.0
    is the vX.Y.Z shape of TensorFold v0.6.5 -> v1.0.7.
    """

    # Given a git+ skill on v9.1.0 and archives only in the v9.2.0 release file
    checkout, path, seen, old, new, rows = _bump_tag(
        tmp_path, monkeypatch, sid="tensorfold", engine="TensorFold", slug="tensorfold",
        old_tag="v9.1.0", new_tag="v9.2.0", install=_TENSORFOLD_INSTALL, binary="tensorfold",
        releases={"v9.2.0": _archive_body("tensorfold", "9.2.0")})

    # Then plan found v9.2.0, the only release read is that tag, and the install
    # is the unpacked executable. The fixture's pin asserts moved with it.
    assert rows[0]["new_ref"] == "v9.2.0"
    assert rows[0]["new_sha"] == new
    assert seen == ["https://api.github.com/repos/fixture/tensorfold/releases/tags/v9.2.0"]
    text = path.read_text()
    assert "git+" not in text
    assert "importlib" not in text
    assert "tensorfold-{version}-linux-x86_64.tar.gz" in text
    assert "tensorfold-{version}-macos-arm64.tar.gz" in text
    assert f"pinned: {new}" in text
    assert "ref: v9.2.0" in text
    got = es.load_skill(path)
    assert got["binary"] == "{prefix}/{version}/bin/{id}"
    assert got["detect"] == "{binary} --version"
    assert "sha256sum -c" in got["install"]["cuda"][3]
    assert "shasum -a 256 -c" in got["install"]["metal"][3]
    link = got["install"]["cuda"][-1]
    assert link.startswith("exe=$(find ")
    assert "{prefix}/{version}/bin/{id}" in link
    assert "|" not in link
    _assert_pins_rewritten(checkout, old, new, "v9.1.0", "v9.2.0")
    assert not (checkout / "data" / "strata_models.json").exists()


def test_derive_release_lookup_uses_the_passed_tag(tmp_path, monkeypatch):
    """E10 reads `ref` when derive runs before the skill file is updated.

    With no `ref`, it reads the tag still written in the skill. An empty
    release file leaves `auto` without archives. The release body is a JSON
    file. derive clones the local repo behind the skill's GitHub URL.
    """

    # Given a skill whose file still says v9.1.0, and archives only in v9.2.0.json
    upstream, _old, new = _moved_tag(tmp_path, "v9.1.0", "v9.2.0")
    github = _github("tensorfold")
    skill = _skill(tmp_path, github, "v9.1.0", "tag", _old,
                   backends=["cuda", "metal"],
                   install={"cuda": ["uv pip install 'engine @ git+{repo}.git@v{version}'"],
                            "metal": ["uv tool install 'engine @ git+{repo}.git@v{version}'"]})
    releases = tmp_path / "releases"
    _write_release(releases, "tensorfold", "v9.2.0", _archive_body("tensorfold", "9.2.0"))
    _write_release(releases, "tensorfold", "v9.1.0", {"assets": []})
    checkout, _path = _checkout(tmp_path, "unused", "---\nid: unused\nref: v9.1.0\n---\n", _old, "v9.1.0")
    seen = _bind_files(monkeypatch, checkout, upstream, github, releases)

    # When derive is told the destination tag and clones the upstream itself
    found = epd.derive(skill, new, ref="v9.2.0")

    # Then that tag is the one requested, and its archives are the finding
    assert seen == ["https://api.github.com/repos/fixture/tensorfold/releases/tags/v9.2.0"]
    names = {a["name"] for a in found["auto"]["release_assets"]}
    assert "tensorfold-9.2.0-linux-x86_64.tar.gz" in names
    assert "tensorfold-9.2.0-macos-arm64.tar.gz" in names

    # And with no destination tag, the skill's own tag is what gets asked
    again = epd.derive(skill, new)
    assert seen[-1].endswith("/releases/tags/v9.1.0")
    assert "release_assets" not in again["auto"]


def test_bump_leaves_pip_when_destination_release_has_no_archives(tmp_path, monkeypatch):
    """A destination tag with no native archives still moves the pin and keeps pip."""

    # Given a git+ skill and a destination release file with an empty asset list
    checkout, path, seen, old, new, rows = _bump_tag(
        tmp_path, monkeypatch, sid="tensorfold", engine="TensorFold", slug="tensorfold",
        old_tag="v9.1.0", new_tag="v9.2.0", install=_TENSORFOLD_INSTALL, binary="tensorfold",
        releases={"v9.2.0": {"assets": []}})

    # Then the pin moved, the release read was the new tag, and pip stayed
    assert rows[0]["new_ref"] == "v9.2.0"
    assert seen == ["https://api.github.com/repos/fixture/tensorfold/releases/tags/v9.2.0"]
    text = path.read_text()
    assert "git+" in text
    assert "ln -sfn" not in text
    assert "releases/download" not in text
    assert f"pinned: {new}" in text
    assert "ref: v9.2.0" in text
    assert es.load_skill(path)["binary"] == "tensorfold"
    _assert_pins_rewritten(checkout, old, new, "v9.1.0", "v9.2.0")


def test_bump_branch_does_not_query_a_release(tmp_path, monkeypatch):
    """A branch bump does not ask GitHub for a release."""

    # Given a branch skill that pip-installs from git, one commit behind master
    upstream, old, new = _moved_branch(tmp_path, "master")
    github = _github("branchengine")
    text = _skill_text(
        sid="branchengine", engine="branchengine", repo=github, ref="master", ref_kind="branch",
        pinned=old, backends=["cuda"], binary="engine", version="",
        install=[("cuda", ["uv pip install --system 'engine @ git+{repo}.git@master'"])],
        detect=['detect: "engine --version"'])
    checkout, path = _checkout(tmp_path, "branchengine", text, old, "master")
    seen = _bind_files(monkeypatch, checkout, upstream, github, tmp_path / "releases")
    _write_release(tmp_path / "releases", "branchengine", "master", _archive_body("engine", "9.2.0"))

    # When the bump runs
    rows = eb.bump("branchengine")

    # Then no release was requested, the pip line stayed, and the pin moved
    assert rows[0]["new_sha"] == new
    assert seen == []
    assert "git+" in path.read_text()
    assert f"pinned: {new}" in path.read_text()
    assert "ref: master" in path.read_text()
    _assert_pins_rewritten(checkout, old, new, "master", "master")


@pytest.mark.parametrize("engine", [
    "tensorfold",
    "strata",
    "llama.cpp",
    "llama.cpp-prism",
])
def test_each_failed_bump_engine_keeps_its_install_kind(tmp_path, monkeypatch, engine):
    """The four red bump PRs do not repeat.

    The versions are the shape of those PRs, not the live pins. tensorfold is
    v9.1.0 -> v9.2.0, the v0.6.5 -> v1.0.7 git+ bump. strata is v8.1.0 ->
    v8.2.0, the v0.1.43 -> v0.1.43 clone and cmake bump. llama.cpp stays on
    master and llama.cpp-prism stays on prism.

    Each case runs plan, derive, pin and apply. The GitHub remote is a local
    repo. The release body is a JSON file.
    """

    # Given that engine's install, still on the pin the bump started from
    if engine == "tensorfold":
        checkout, path, seen, old, new, rows = _bump_tag(
            tmp_path, monkeypatch, sid="tensorfold", engine="TensorFold", slug="tensorfold",
            old_tag="v9.1.0", new_tag="v9.2.0", install=_TENSORFOLD_INSTALL, binary="tensorfold",
            releases={"v9.2.0": _archive_body("tensorfold", "9.2.0")})
        assert rows[0]["new_ref"] == "v9.2.0"
        assert seen == ["https://api.github.com/repos/fixture/tensorfold/releases/tags/v9.2.0"]
        text = path.read_text()
        assert "git+" not in text
        assert "importlib" not in text
        assert "ref: v9.2.0" in text
        assert f"pinned: {new}" in text
        got = es.load_skill(path)
        assert got["binary"] == "{prefix}/{version}/bin/{id}"
        assert got["detect"] == "{binary} --version"
        assert "tensorfold-{version}-linux-x86_64.tar.gz" in text
        assert "tensorfold-{version}-macos-arm64.tar.gz" in text
        _assert_pins_rewritten(checkout, old, new, "v9.1.0", "v9.2.0")
        return

    if engine == "strata":
        upstream, old, new = _moved_tag(tmp_path, "v8.1.0", "v8.2.0")
        github = _github("strata")
        install = [
            ("common", [
                "test -d {src}/.git || git clone -b v{version} --depth 1 {repo}.git {src}",
                "python3 -m venv {src}/py && {src}/py/bin/pip install --no-cache-dir -r {src}/requirements.txt",
            ]),
            ("cuda", ["cd {src} && py/bin/python -c 'import setup; setup.cmake_build'"]),
            ("rocm", ["cd {src} && py/bin/python -c 'import setup; setup.cmake_build'"]),
        ]
        text = _skill_text(
            sid="strata", engine="Strata", repo=github, ref="v8.1.0", ref_kind="tag",
            pinned=old, backends=["cuda", "rocm"], install=install,
            binary="{src}/engine/strata", version="v8.1.0",
            detect=['detect: "{binary} --help"'])
        checkout, path = _checkout(tmp_path, "strata", text, old, "v8.1.0")
        # The real tree tracks this file, so a regen shows a modification of
        # data/strata_models.json. An untracked data/ is `?? data/`, which the
        # guard rejects.
        seeded = checkout / "data" / "strata_models.json"
        seeded.parent.mkdir()
        seeded.write_text('{"old": true}\n')
        _git(checkout, "add", "-A")
        _git(checkout, "commit", "-qm", "seed strata models")
        seen = _bind_files(monkeypatch, checkout, upstream, github, tmp_path / "releases")
        _write_release(tmp_path / "releases", "strata", "v8.2.0",
                       _archive_body("strata", "8.2.0", targets=("linux-x86_64",)))
        rows = eb.bump("strata")
        assert rows[0]["new_ref"] == "v8.2.0"
        assert seen == ["https://api.github.com/repos/fixture/strata/releases/tags/v8.2.0"]
        body = path.read_text()
        assert "git clone -b v{version}" in body
        assert "pip install --no-cache-dir -r" in body
        assert "setup.cmake_build" in body
        assert "ln -sfn" not in body
        assert "releases/download" not in body
        assert "ref: v8.2.0" in body
        assert f"pinned: {new}" in body
        assert es.load_skill(path)["binary"] == "{src}/engine/strata"
        assert (checkout / "data" / "strata_models.json").read_text() == "{}\n"
        _assert_pins_rewritten(checkout, old, new, "v8.1.0", "v8.2.0")
        return

    ref = "prism" if engine == "llama.cpp-prism" else "master"
    slug = "llamacpp-prism" if engine == "llama.cpp-prism" else "llamacpp"
    upstream, old, new = _moved_branch(tmp_path, ref)
    github = _github(slug)
    install = [
        ("common", [
            "test -d {src}/.git || git clone -b {ref} {repo}.git {src}",
            "cmake -S {src} -B {build} -DCMAKE_BUILD_TYPE=Release {cmake_flags}",
            "cmake --build {build} --config Release -j{jobs} --target llama-server",
        ]),
    ]
    text = _skill_text(
        sid=engine, engine=engine, repo=github, ref=ref, ref_kind="branch",
        pinned=old, backends=["cuda", "cpu"], install=install,
        binary="{build}/bin/llama-server", detect=['detect: "{binary} --version"'])
    checkout, path = _checkout(tmp_path, engine, text, old, ref)
    seen = _bind_files(monkeypatch, checkout, upstream, github, tmp_path / "releases")
    _write_release(tmp_path / "releases", slug, ref, _archive_body("llama", "9.2.0"))
    rows = eb.bump(engine)
    assert rows[0]["new_sha"] == new
    assert rows[0]["new_ref"] == ref
    assert seen == []
    body = path.read_text()
    assert "cmake --build {build}" in body
    assert "git clone -b {ref}" in body
    assert "ln -sfn" not in body
    assert f"pinned: {new}" in body
    assert f"ref: {ref}" in body
    got = es.load_skill(path)
    assert got["binary"] == "{build}/bin/llama-server"
    assert got["detect"] == "{binary} --version"
    _assert_pins_rewritten(checkout, old, new, ref, ref)
    assert not (checkout / "data" / "strata_models.json").exists()


def test_bump_ignores_archives_published_only_on_the_old_tag(tmp_path, monkeypatch):
    """Archives on the tag still written in the skill must not win.

    This is the v0.6.5 -> v1.0.7 failure: derive used to read the old tag.
    The old release file has checksummed archives. The destination file is empty.
    """

    # Given archives on v9.1.0 and an empty v9.2.0 release
    _checkout_path, path, seen, _old, new, rows = _bump_tag(
        tmp_path, monkeypatch, sid="tensorfold", engine="TensorFold", slug="tensorfold",
        old_tag="v9.1.0", new_tag="v9.2.0", install=_TENSORFOLD_INSTALL, binary="tensorfold",
        releases={
            "v9.1.0": _archive_body("tensorfold", "9.1.0"),
            "v9.2.0": {"assets": []},
        })

    # Then the only request is the destination tag, and the git+ install stays
    assert rows[0]["new_ref"] == "v9.2.0"
    assert seen == ["https://api.github.com/repos/fixture/tensorfold/releases/tags/v9.2.0"]
    text = path.read_text()
    assert "git+" in text
    assert "ln -sfn" not in text
    assert "releases/download" not in text
    assert f"pinned: {new}" in text
    assert "ref: v9.2.0" in text


def test_bump_keeps_pip_when_archive_has_no_checksum(tmp_path, monkeypatch):
    """A tar.gz with no sibling .sha256 is not a native archive."""

    # Given destination archives that ship no checksum file
    _checkout_path, path, seen, _old, new, _rows = _bump_tag(
        tmp_path, monkeypatch, sid="tensorfold", engine="TensorFold", slug="tensorfold",
        old_tag="v9.1.0", new_tag="v9.2.0", install=_TENSORFOLD_INSTALL, binary="tensorfold",
        releases={"v9.2.0": _archive_body("tensorfold", "9.2.0", checksum=False)})

    # Then the pin moves and the pip install stays
    assert seen == ["https://api.github.com/repos/fixture/tensorfold/releases/tags/v9.2.0"]
    text = path.read_text()
    assert "git+" in text
    assert "ln -sfn" not in text
    assert f"pinned: {new}" in text
    assert es.load_skill(path)["binary"] == "tensorfold"


def test_bump_keeps_pip_when_a_backend_has_no_archive(tmp_path, monkeypatch):
    """One missing backend archive keeps the pip install for every backend."""

    # Given a linux archive and no macos archive, with both cuda and metal
    _checkout_path, path, seen, _old, new, _rows = _bump_tag(
        tmp_path, monkeypatch, sid="tensorfold", engine="TensorFold", slug="tensorfold",
        old_tag="v9.1.0", new_tag="v9.2.0", install=_TENSORFOLD_INSTALL, binary="tensorfold",
        releases={"v9.2.0": _archive_body("tensorfold", "9.2.0", targets=("linux-x86_64",))})

    # Then nothing is rewritten: a partial archive set is not applied
    assert seen == ["https://api.github.com/repos/fixture/tensorfold/releases/tags/v9.2.0"]
    text = path.read_text()
    assert "git+" in text
    assert "ln -sfn" not in text
    assert "uv tool install" in text
    assert f"pinned: {new}" in text
    assert "ref: v9.2.0" in text


def test_bump_already_at_latest_tag_does_nothing(tmp_path, monkeypatch):
    """A skill already on the highest stable tag is not rewritten."""

    # Given the pin sha and the only tag are the same commit
    upstream = _make_repo(tmp_path, "up", {"README.md": "tip\n"})
    sha = _git(upstream, "rev-parse", "HEAD")
    _git(upstream, "tag", "v9.2.0")
    github = _github("tensorfold")
    text = _pip_engine("tensorfold", "TensorFold", github, "v9.2.0", sha,
                       ["cuda", "metal"], _TENSORFOLD_INSTALL, "tensorfold", version="v9.2.0")
    checkout, path = _checkout(tmp_path, "tensorfold", text, sha, "v9.2.0")
    before = path.read_text()
    pins = (checkout / "tests" / "test_pins.py").read_text()
    seen = _bind_files(monkeypatch, checkout, upstream, github, tmp_path / "releases")
    _write_release(tmp_path / "releases", "tensorfold", "v9.2.0", _archive_body("tensorfold", "9.2.0"))

    # When the bump runs
    assert eb.bump("tensorfold") == []

    # Then the skill is untouched and no release was read
    assert path.read_text() == before
    assert (checkout / "tests" / "test_pins.py").read_text() == pins
    assert seen == []


def test_bump_ignores_a_newer_prerelease_tag(tmp_path, monkeypatch):
    """A newer rc tag does not beat the highest stable tag of the same shape."""

    # Given v9.3.0-rc1 ahead of v9.2.0, and archives only on the stable tag
    checkout, path, seen, old, new, rows = _bump_tag(
        tmp_path, monkeypatch, sid="tensorfold", engine="TensorFold", slug="tensorfold",
        old_tag="v9.1.0", new_tag="v9.2.0", extra_tag="v9.3.0-rc1",
        install=_TENSORFOLD_INSTALL, binary="tensorfold",
        releases={"v9.2.0": _archive_body("tensorfold", "9.2.0")})

    # Then the bump lands on v9.2.0 and installs that archive
    assert rows[0]["new_ref"] == "v9.2.0"
    assert rows[0]["new_sha"] == new
    assert seen == ["https://api.github.com/repos/fixture/tensorfold/releases/tags/v9.2.0"]
    text = path.read_text()
    assert "v9.3.0" not in text
    assert "git+" not in text
    assert "ref: v9.2.0" in text
    _assert_pins_rewritten(checkout, old, new, "v9.1.0", "v9.2.0")


def test_bump_does_not_move_to_an_older_tag(tmp_path, monkeypatch):
    """A pin newer than every upstream tag stays where it is."""

    # Given upstream stopped at v9.2.0 and the skill is already on v9.3.0
    upstream = _make_repo(tmp_path, "up", {"README.md": "old\n"})
    _git(upstream, "tag", "v9.2.0")
    github = _github("tensorfold")
    pinned = "ab" * 20
    text = _pip_engine("tensorfold", "TensorFold", github, "v9.3.0", pinned,
                       ["cuda", "metal"], _TENSORFOLD_INSTALL, "tensorfold", version="v9.3.0")
    checkout, path = _checkout(tmp_path, "tensorfold", text, pinned, "v9.3.0")
    before = path.read_text()
    seen = _bind_files(monkeypatch, checkout, upstream, github, tmp_path / "releases")
    _write_release(tmp_path / "releases", "tensorfold", "v9.2.0", _archive_body("tensorfold", "9.2.0"))

    # When the bump runs
    assert eb.bump("tensorfold") == []

    # Then the file is unchanged and the older release was not read
    assert path.read_text() == before
    assert "ref: v9.3.0" in before
    assert seen == []


def test_bump_branch_already_at_tip_does_nothing(tmp_path, monkeypatch):
    """A branch pin already at the remote head is not a bump."""

    # Given master and the skill pin are the same commit
    upstream = _make_repo(tmp_path, "up", {"README.md": "tip\n"})
    sha = _git(upstream, "rev-parse", "HEAD")
    github = _github("llamacpp")
    text = _skill_text(
        sid="llama.cpp", engine="llama.cpp", repo=github, ref="master", ref_kind="branch",
        pinned=sha, backends=["cuda"], binary="{build}/bin/llama-server",
        install=[("cuda", ["cmake --build {build} --target llama-server"])],
        detect=['detect: "{binary} --version"'])
    checkout, path = _checkout(tmp_path, "llama.cpp", text, sha, "master")
    before = path.read_text()
    seen = _bind_files(monkeypatch, checkout, upstream, github, tmp_path / "releases")

    # When the bump runs
    assert eb.bump("llama.cpp") == []

    # Then the pin is unchanged and no release was requested
    assert path.read_text() == before
    assert seen == []


def test_bump_tag_lookup_failure_leaves_the_pin(tmp_path, monkeypatch):
    """No tags is a failed lookup. The pin does not move."""

    # Given a tag skill whose upstream has commits and no tags
    upstream = _make_repo(tmp_path, "up", {"README.md": "bare\n"})
    sha = _git(upstream, "rev-parse", "HEAD")
    github = _github("tensorfold")
    text = _pip_engine("tensorfold", "TensorFold", github, "v9.1.0", sha,
                       ["cuda", "metal"], _TENSORFOLD_INSTALL, "tensorfold", version="v9.1.0")
    checkout, path = _checkout(tmp_path, "tensorfold", text, sha, "v9.1.0")
    before = path.read_text()
    seen = _bind_files(monkeypatch, checkout, upstream, github, tmp_path / "releases")

    # When the bump runs
    with pytest.raises(SystemExit, match="lookup failed"):
        eb.bump("tensorfold")

    # Then the skill is unchanged and no release was requested
    assert path.read_text() == before
    assert "ref: v9.1.0" in before
    assert seen == []

def test_apply_release_archive_ignores_wheels(tmp_path):
    """A release of wheels is not an install-kind change."""

    # Given a pip-installed skill and a release that ships only wheels
    p = _write_skill(tmp_path, (
        "---\n"
        "id: testengine\n"
        "repo: https://github.com/example/engine\n"
        "backends: [cpu]\n"
        "install:\n"
        "  cpu:\n"
        "    - \"uv pip install --system 'engine @ git+{repo}.git@v{version}'\"\n"
        "---\n"))
    orig = es.SKILLS_DIR
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    try:
        # When the bump applies
        changed = eb._apply_findings("testengine", {"auto": {"release_assets": [
            {"name": "engine-1.0.5-py3-none-any.whl"}]}})
    finally:
        es.SKILLS_DIR = orig

    # Then the install line is untouched
    assert changed == []
    assert "git+" in p.read_text()


def _denied(url: str, code: int) -> urllib.error.HTTPError:
    from email.message import Message
    return urllib.error.HTTPError(url, code, "denied", Message(), io.BytesIO(b""))


def _bind_release(monkeypatch, handler) -> None:
    """The real lookup runs. urlopen is the external stand-in and records the request."""
    monkeypatch.setattr(urllib.request, "urlopen", handler)


def test_workflows_export_the_github_token():
    """Workflows that can start a test container export the Actions GitHub token."""

    # Given the workflows that already export HF_TOKEN
    names = ("ci.yml", "pipeline.yml", "published.yml", "engine-bump.yml", "registry-sync.yml")

    # When their workflow env is read
    # Then each sets GITHUB_TOKEN from the Actions secret
    for name in names:
        doc = yaml.safe_load((REPO / ".github" / "workflows" / name).read_text())
        assert doc["env"]["GITHUB_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}", name


def test_linux_test_containers_forward_the_github_token():
    """Linux test containers receive the GitHub token by name, like HF_TOKEN.

    docker -e NAME copies the value from the environment. Assigning it on the
    command line would publish it in the process list.
    """

    # Given the two Linux container runners
    text = (REPO / "Makefile").read_text()
    opts = text.split("TEST_OPTS :=", 1)[1].split("\n", 1)[0]
    engine = text.split("ENGINE_TEST_ARGS :=", 1)[1].split("\nendif", 1)[0]

    # When their container environment flags are read
    # Then each forwards the token names and not a value
    for block in (opts, engine):
        assert "-e GITHUB_TOKEN" in block
        assert "-e GH_TOKEN" in block
        assert "GITHUB_TOKEN=" not in block
        assert "GH_TOKEN=" not in block


def test_release_lookup_sends_the_github_token(monkeypatch):
    """GITHUB_TOKEN wins when both token variables are set."""

    # Given both tokens, and a release body standing in for the GitHub API
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_actions")
    monkeypatch.setenv("GH_TOKEN", "ghp_other")
    seen = {}

    def urlopen(req, timeout=None, *args, **kwargs):
        seen["auth"] = req.get_header("Authorization")
        return _ReleaseFile(b'{"assets":[{"name":"engine-1.0.5-linux-x86_64.tar.gz"}]}')

    _bind_release(monkeypatch, urlopen)

    # When the release lookup runs
    assets = eb._release_assets("https://github.com/ashhart/TensorFold", "v1.0.5")

    # Then the request carries GITHUB_TOKEN and the assets come back
    assert seen["auth"] == "Bearer ghp_actions"
    assert assets == [{"name": "engine-1.0.5-linux-x86_64.tar.gz"}]


def test_release_lookup_uses_gh_token_when_github_token_is_empty(monkeypatch):
    """GH_TOKEN is the token when GITHUB_TOKEN is unset."""

    # Given only GH_TOKEN
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "ghp_cli")
    seen = {}

    def urlopen(req, timeout=None, *args, **kwargs):
        seen["auth"] = req.get_header("Authorization")
        return _ReleaseFile(b'{"assets":[{"name":"a.tar.gz"}]}')

    _bind_release(monkeypatch, urlopen)

    # When the release lookup runs
    assets = eb._release_assets("https://github.com/ashhart/TensorFold", "v1.0.5")

    # Then the request carries GH_TOKEN
    assert seen["auth"] == "Bearer ghp_cli"
    assert assets == [{"name": "a.tar.gz"}]


def test_release_lookup_without_a_token_sends_no_authorization(monkeypatch):
    """No token means no Authorization header."""

    # Given neither token
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    seen = {}

    def urlopen(req, timeout=None, *args, **kwargs):
        seen["auth"] = req.get_header("Authorization")
        return _ReleaseFile(b'{"assets":[]}')

    _bind_release(monkeypatch, urlopen)

    # When the release lookup runs
    assets = eb._release_assets("https://github.com/ashhart/TensorFold", "v1.0.5")

    # Then the request is anonymous and an empty asset list is empty
    assert seen["auth"] is None
    assert assets == []


def test_release_lookup_retries_a_foreign_repo_denial_without_the_token(monkeypatch):
    """A repo-scoped token is denied on another public repo. Read it once more, anonymously."""

    # Given a token GitHub refuses for this release
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_installation")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    seen = []

    def urlopen(req, timeout=None, *args, **kwargs):
        auth = req.get_header("Authorization")
        seen.append(auth)
        if auth:
            raise _denied(req.full_url, 403)
        return _ReleaseFile(b'{"assets":[{"name":"tensorfold-1.0.5-linux-x86_64.tar.gz"}]}')

    _bind_release(monkeypatch, urlopen)

    # When the release lookup runs
    assets = eb._release_assets("https://github.com/ashhart/TensorFold", "v1.0.5")

    # Then the denial is followed by one anonymous read, and those assets are kept
    assert seen == ["Bearer ghs_installation", None]
    assert assets == [{"name": "tensorfold-1.0.5-linux-x86_64.tar.gz"}]


def test_release_lookup_does_not_retry_a_missing_release(monkeypatch):
    """A 404 is a missing release, not a token denial."""

    # Given a token and a release GitHub does not have
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_actions")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    seen = []

    def urlopen(req, timeout=None, *args, **kwargs):
        seen.append(req.get_header("Authorization"))
        raise _denied(req.full_url, 404)

    _bind_release(monkeypatch, urlopen)

    # When the release lookup runs
    assets = eb._release_assets("https://github.com/ashhart/TensorFold", "v9.9.9")

    # Then there is no second request and no assets
    assert seen == ["Bearer ghp_actions"]
    assert assets == []


def test_derive_reports_the_live_release_archives(tmp_path):
    """E10 lives in derive, not only in apply.

    `derive` must put the published release's archives on `auto.release_assets`
    for a tag pin, and must not for a branch pin. Reads the live GitHub release
    and a real local git repo for the rest of the extractors.
    """

    # Given a tag-pinned skill whose repo is a real local git repo, and the
    # published TensorFold v1.0.5 release standing in for its own
    repo = _make_repo(tmp_path, "up", {"README.md": "native binary\n"})
    sha = _git(repo, "rev-parse", "HEAD")
    skill = _skill(tmp_path, "https://github.com/ashhart/TensorFold", "v1.0.5", "tag", sha)
    skill["backends"] = ["cuda", "metal"]
    skill["install"] = {"cuda": ["uv pip install 'engine @ git+{repo}.git@v{version}'"],
                        "metal": ["uv tool install 'engine @ git+{repo}.git@v{version}'"]}

    # When derive runs at that pin
    findings = epd.derive(skill, sha, repo_dir=repo)

    # Then the live release's archives are on the finding, ready for apply
    names = {a["name"] for a in findings["auto"]["release_assets"]}
    assert "tensorfold-1.0.5-linux-x86_64.tar.gz" in names
    assert "tensorfold-1.0.5-linux-x86_64.tar.gz.sha256" in names
    assert "tensorfold-1.0.5-macos-arm64.tar.gz" in names
    steps = eb.release_archive_install(skill, findings["auto"]["release_assets"])
    assert steps and "tensorfold-{version}-linux-x86_64.tar.gz" in steps["cuda"][1]

    # And a branch pin never asks the release API
    branch = dict(skill, ref="master", ref_kind="branch")
    again = epd.derive(branch, sha, repo_dir=repo)
    assert "release_assets" not in again["auto"]


def test_tensorfold_v1_0_5_release_is_native_archives():
    """The published TensorFold 1.0.5 release is what E10 must recognise.

    Reads the live GitHub release. A bump that cannot see these assets would
    leave the pip install that 1.0.5 refuses.
    """

    # Given the published TensorFold v1.0.5 release
    assets = eb._release_assets("https://github.com/ashhart/TensorFold", "v1.0.5")

    # When the bump classifies its assets
    found = eb._native_archives(assets)

    # Then both archives the skill's backends need are there, checksummed
    assert assets, "GitHub returned no assets for TensorFold v1.0.5"
    assert ("linux", "x86_64") in found
    assert ("macos", "arm64") in found
    assert found[("linux", "x86_64")].endswith(".tar.gz")
    skill = es.get_skill("tensorfold")
    steps = eb.release_archive_install(
        {**skill, "ref": "v1.0.5", "version": "v1.0.5"}, assets)
    assert steps is not None
    assert "tensorfold-{version}-linux-x86_64.tar.gz" in steps["cuda"][1]
    assert "tensorfold-{version}-macos-arm64.tar.gz" in steps["metal"][1]


def test_tensorfold_release_archive_unpacks_and_runs(tmp_path):
    """The install steps E10 writes actually install TensorFold 1.0.5.

    Downloads the real release archive, checks the published checksum and runs
    the unpacked binary. This is the step the cuda image died on: pip of
    v1.0.5 refuses to build, the archive is what upstream ships instead.
    """
    import hashlib
    import platform
    import tarfile

    # Given the archive E10 picks for this host's machine, and its published checksum.
    # macos-15-intel is Darwin but x86_64: system() alone picked the arm64
    # archive and the binary died with Bad CPU type.
    arch_tok = "x86_64" if platform.machine() in ("x86_64", "AMD64") else "arm64"
    os_tok = "linux" if platform.system() == "Linux" else "macos"
    assets = eb._release_assets("https://github.com/ashhart/TensorFold", "v1.0.5")
    found = eb._native_archives(assets)
    asset = found[(os_tok, arch_tok)]
    base = "https://github.com/ashhart/TensorFold/releases/download/v1.0.5"
    archive = tmp_path / asset
    eb._download(f"{base}/{asset}", archive)
    eb._download(f"{base}/{asset}.sha256", tmp_path / f"{asset}.sha256")

    # When the checksum is checked and the archive unpacked the way the install
    # step does (bin/ one level down, --strip-components=1)
    digest, named = (tmp_path / f"{asset}.sha256").read_text().split()
    assert named == asset
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == digest
    dest = tmp_path / "1.0.5"
    with tarfile.open(archive) as tar:
        members = [m for m in tar.getmembers() if m.name.startswith(asset[:-7] + "/bin/")]
        assert members, [m.name for m in tar.getmembers()]
        for m in members:
            m.name = "/".join(m.name.split("/")[1:])
            tar.extract(m, dest, filter="data")

    # Then the unpacked binary is the native engine and reports 1.0.5
    binary = dest / "bin" / "tensorfold-native"
    assert binary.is_file() and os.access(binary, os.X_OK)
    ver = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=60)
    assert ver.returncode == 0, ver.stderr
    assert "1.0.5" in ver.stdout + ver.stderr


def test_unit_job_fetches_history():
    """matrix(changed=origin/main) needs the parent commit in the unit checkout.

    A default actions/checkout is depth 1. git show origin/main:<path> then
    fails and every engine looks changed, so the placeholder row never appears.
    """

    # Given the unit job
    doc = yaml.safe_load((REPO / ".github" / "workflows" / "pipeline.yml").read_text())
    checkout = next(s for s in doc["jobs"]["unit"]["steps"]
                    if str(s.get("uses", "")).startswith("actions/checkout"))

    # When its checkout is read
    # Then it fetches full history, and macOS still does not run the docker action
    assert checkout.get("with", {}).get("fetch-depth") == 0
    docker = next(s for s in doc["jobs"]["unit"]["steps"]
                  if str(s.get("uses", "")).startswith("./.github/actions/docker"))
    assert docker.get("if") == "runner.os == 'Linux'"


def test_unit_recipe_keeps_the_image_build_out():
    """The hermetic unit list runs the bump tests and not the image build.

    make test-unit's container has no docker socket. The real llama.cpp cpu
    build lives in its own file so wiring the bump tests into the unit job
    cannot turn that job red.
    """

    # Given the test-unit recipe
    recipe = (REPO / "Makefile").read_text().split("\ntest-unit:", 1)[1].split("\n\n", 1)[0]

    # When its pytest file list is read
    # Then the bump tests run and the image build does not
    assert "tests/test_engine_bump.py" in recipe
    assert "tests/test_engine_bump_build.py" not in recipe
    assert "test_tensorfold_release_archive_unpacks_and_runs" in recipe
    live = (REPO / "Makefile").read_text().split("\ntest-engine-bump-live:", 1)[1].split("\n\n", 1)[0]
    assert "test_tensorfold_release_archive_unpacks_and_runs" in live
    unit = yaml.safe_load((REPO / ".github" / "workflows" / "pipeline.yml").read_text())["jobs"]["unit"]
    live_step = next(s for s in unit["steps"] if "test-engine-bump-live" in str(s.get("run", "")))
    assert live_step.get("if") == "runner.os == 'Linux'"


def _pytest_k_selects(expr: str, name: str) -> bool:
    """pytest `-k`: a bare word is true when it is a substring of the test name."""
    def repl(m):
        word = m.group(0)
        if word in ("and", "or", "not"):
            return word
        return "True" if word.lower() in name.lower() else "False"
    return bool(eval(re.sub(r"[A-Za-z_][A-Za-z0-9_]*", repl, expr)))  # noqa: S307


def test_unit_recipe_runs_the_destination_release_cases():
    """make test-unit runs the hermetic destination-tag cases and not the live release reads.

    The unit job calls this recipe. The three GitHub-release tests stay on
    `make test-engine-bump-live` (Linux only).
    """

    # Given the test-unit pytest invocation
    recipe = (REPO / "Makefile").read_text().split("\ntest-unit:", 1)[1].split("\n\n", 1)[0]
    expr = recipe.split("-k '", 1)[1].split("'", 1)[0]
    hermetic = (
        "test_derive_release_lookup_uses_the_passed_tag",
        "test_bump_reads_the_destination_release",
        "test_bump_leaves_pip_when_destination_release_has_no_archives",
        "test_bump_branch_does_not_query_a_release",
        "test_apply_release_archive_replaces_pip_install",
        "test_changed_engines_scopes_matrix",
        "test_each_failed_bump_engine_keeps_its_install_kind",
        "test_each_bump_pr_engine_is_scoped_not_a_placeholder",
        "test_bump_ignores_archives_published_only_on_the_old_tag",
        "test_bump_keeps_pip_when_archive_has_no_checksum",
        "test_bump_keeps_pip_when_a_backend_has_no_archive",
        "test_bump_already_at_latest_tag_does_nothing",
        "test_bump_ignores_a_newer_prerelease_tag",
        "test_bump_does_not_move_to_an_older_tag",
        "test_bump_branch_already_at_tip_does_nothing",
        "test_bump_tag_lookup_failure_leaves_the_pin",
        "test_two_moved_pins_list_both_engines",
        "test_a_non_image_file_change_stays_the_placeholder",
    )
    assert "tests/test_engine_image_matrix.py" in recipe
    live = (
        "test_derive_reports_the_live_release_archives",
        "test_tensorfold_v1_0_5_release_is_native_archives",
        "test_tensorfold_release_archive_unpacks_and_runs",
    )

    # When the -k expression is applied to each name
    # Then the hermetic cases run inside test-unit, and the live ones do not
    assert "tests/test_engine_bump.py" in recipe
    assert all(_pytest_k_selects(expr, name) for name in hermetic)
    assert not any(_pytest_k_selects(expr, name) for name in live)


def _dep_skill(tmp_path, repo, old, install, container):
    return _skill(
        tmp_path, str(repo), "master", "branch", old,
        install=install, container=container,
    )


def _image_install(skill_path: Path):
    """The Dockerfile and install steps `generate-engine-params` would build."""
    skill = es.load_skill(skill_path)
    params = es.generate_params(skill)
    assert params and "cuda" in params["variants"]
    return (
        es.render_dockerfile(params, "cuda"),
        es.render_base_dockerfile("cuda"),
        params["variants"]["cuda"]["install"],
    )


def test_new_requirements_the_skill_already_installs_are_reported(tmp_path):
    """A requirements.txt the install already pip-installs is not a hard-fail."""

    # Given the new pin adds newpkg and the skill pip-installs requirements.txt
    repo = _make_repo(tmp_path, "up", {
        "requirements.txt": "oldpkg\n",
        "Dockerfile": "RUN apt-get install -y --no-install-recommends libold1 \\\n    && rm -rf /var/lib/apt/lists/*\n",
    })
    old = _git(repo, "rev-parse", "HEAD")
    new = _commit(repo, {
        "requirements.txt": "oldpkg\nnewpkg>=1\n",
        "Dockerfile": "RUN apt-get install -y --no-install-recommends libold1 libnew1 \\\n    && rm -rf /var/lib/apt/lists/*\n",
    })
    skill = _dep_skill(
        tmp_path, repo, old,
        {"common": ["python3 -m pip install --no-cache-dir -r {src}/requirements.txt"]},
        {"cuda": {"apt": ["libold1"]}},
    )

    # When derive reads both shas
    found = epd.derive(skill, new, repo_dir=repo, old_sha=old)

    # Then the new python package is covered and the new apt package is applied
    deps = found["report"]["dependencies"]
    assert deps["python_added"] == ["newpkg"]
    assert deps["python_covered"] is True
    assert found["hard_fail"] is None
    assert found["auto"]["apt_add"] == ["libnew1"]
    skill_path = tmp_path / "skills" / "engines" / "testengine" / "SKILL.md"
    skill_text = skill_path.read_text().replace(
        "    apt:\n      - libold1\n", "    apt: [libold1]\n")
    skill_path.write_text(skill_text)
    orig = es.SKILLS_DIR
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    try:
        changed = eb._apply_findings("testengine", found)
    finally:
        es.SKILLS_DIR = orig
    text = skill_path.read_text()
    assert "apt=libnew1" in changed
    assert "apt: [libold1, libnew1]" in text

    # And the generated image installs that package, not a new pip line
    dockerfile, base, install = _image_install(skill_path)
    assert "apt-get install" in dockerfile and "libnew1" in dockerfile
    assert "libnew1" not in base
    joined = "\n".join(install)
    assert "pip install" in joined and "requirements.txt" in joined
    assert "newpkg" not in joined


def test_new_requirements_the_skill_does_not_install_hard_fail(tmp_path):
    """A new python requirement with no pip -r line is named and not guessed."""

    # Given a cmake-only install and a new requirements.txt package
    repo = _make_repo(tmp_path, "up", {"requirements.txt": "oldpkg\n", "Dockerfile": "FROM scratch\n"})
    old = _git(repo, "rev-parse", "HEAD")
    new = _commit(repo, {"requirements.txt": "oldpkg\nnewpkg\n", "Dockerfile": "FROM scratch\n"})
    skill = _dep_skill(
        tmp_path, repo, old,
        {"common": ["cmake --build {build}"]},
        {"cuda": {"apt": ["libold1"]}},
    )

    # When derive reads the new pin
    found = epd.derive(skill, new, repo_dir=repo, old_sha=old)

    # Then the bump records the package and does not invent a pip line
    assert found["report"]["dependencies"]["python_added"] == ["newpkg"]
    assert found["report"]["dependencies"]["python_covered"] is False
    assert "newpkg" in found["hard_fail"]
    assert "apt_add" not in found["auto"]
    skill_path = tmp_path / "skills" / "engines" / "testengine" / "SKILL.md"
    dockerfile, _base, install = _image_install(skill_path)
    joined = "\n".join(install)
    assert "cmake --build" in joined
    assert "newpkg" not in joined
    assert "newpkg" not in dockerfile


def test_new_apt_package_without_an_apt_list_hard_fails(tmp_path):
    """A new Dockerfile package is not written when the skill has no apt: list."""

    # Given no apt: key and a Dockerfile that gains libnew1
    repo = _make_repo(tmp_path, "up", {"Dockerfile": "RUN apt-get install -y libold1\n"})
    old = _git(repo, "rev-parse", "HEAD")
    new = _commit(repo, {"Dockerfile": "RUN apt-get install -y libold1 libnew1\n"})
    skill = _dep_skill(tmp_path, repo, old, {"common": ["true"]}, {})

    # When derive reads the new pin
    found = epd.derive(skill, new, repo_dir=repo, old_sha=old)

    # Then the package is named and no container block is created
    assert found["report"]["dependencies"]["apt_added"] == ["libnew1"]
    assert "libnew1" in found["hard_fail"]
    assert "apt_add" not in found["auto"]
    skill_path = tmp_path / "skills" / "engines" / "testengine" / "SKILL.md"
    assert "libnew1" not in skill_path.read_text()
    dockerfile, base, _install = _image_install(skill_path)
    assert "libnew1" not in dockerfile
    assert "libnew1" not in base


def test_release_pin_compares_the_old_tag_to_the_new_tag(tmp_path):
    """A tag move compares the old release tree to the new release tree.

    Names already at v1.0.0 are not new. Names only at v1.1.0 are. A name in
    both trees is not added, and a name the new tag dropped is not installed
    as if it were new.
    """

    # Given v1.0.0 and v1.1.0, each with its own requirements and Dockerfile
    repo = _make_repo(tmp_path, "up", {
        "requirements.txt": "oldpkg\nstaypkg\n",
        "Dockerfile": "RUN apt-get install -y libold1 libstay1\n",
    })
    _git(repo, "tag", "v1.0.0")
    old = _git(repo, "rev-parse", "v1.0.0^{}")
    _commit(repo, {
        "requirements.txt": "staypkg\nnewpkg>=1\n",
        "Dockerfile": "RUN apt-get install -y libstay1 libnew1\n",
    })
    _git(repo, "tag", "v1.1.0")
    new = _git(repo, "rev-parse", "v1.1.0^{}")
    skill = _skill(
        tmp_path, str(repo), "v1.0.0", "tag", old,
        install={"common": ["python3 -m pip install --no-cache-dir -r {src}/requirements.txt"]},
        container={"cuda": {"apt": ["libold1"]}},
    )

    # When derive reads the destination tag against the old tag
    found = epd.derive(skill, new, repo_dir=repo, old_sha=old, ref="v1.1.0")

    # Then only the names the new tag added are the install delta
    deps = found["report"]["dependencies"]
    assert deps["python_added"] == ["newpkg"]
    assert deps["python_removed"] == ["oldpkg"]
    assert "staypkg" not in deps["python_added"]
    assert deps["apt_added"] == ["libnew1"]
    assert deps["apt_removed"] == ["libold1"]
    assert "libstay1" not in deps["apt_added"]
    assert deps["python_covered"] is True
    assert found["hard_fail"] is None
    assert "release_assets" not in found["auto"]
    skill_path = tmp_path / "skills" / "engines" / "testengine" / "SKILL.md"
    skill_path.write_text(skill_path.read_text().replace(
        "    apt:\n      - libold1\n", "    apt: [libold1]\n"))
    orig = es.SKILLS_DIR
    es.SKILLS_DIR = tmp_path / "skills" / "engines"
    try:
        eb._apply_findings("testengine", found)
    finally:
        es.SKILLS_DIR = orig
    dockerfile, base, install = _image_install(skill_path)
    assert "libnew1" in dockerfile and "libold1" in dockerfile
    assert "libstay1" not in dockerfile
    assert "libnew1" not in base and "libstay1" not in base
    joined = "\n".join(install)
    assert "requirements.txt" in joined
    assert "newpkg" not in joined and "oldpkg" not in joined


def test_bump_applies_one_fixture_before_it_commits(tmp_path, capsys, monkeypatch):
    """One old tag and one new tag exercise the bump before commit and push.

    The new tree adds a requirements name, a pyproject name, an apt name, and
    noise the bump must ignore: a comment, a pip option, dev and test
    requirements, a package already on the apt: line, and a package present
    on both tags. The install does not pip-install the requirements, so the
    python names hard-fail while the new apt name is still appended.
    """

    # Given v1.2.0 and v1.3.0, and a skill pinned to the old tag
    old_files = {
        "requirements.txt": "oldpkg\n# commentpkg\n-e ./localpkg\nSome_Name>=1\n",
        "requirements-dev.txt": "devonly\n",
        "requirements-test.txt": "testonly\n",
        "pyproject.toml": (
            "[project]\nname = \"engine\"\nversion = \"1.2.0\"\n"
            "dependencies = [\"oldpy\"]\n"
        ),
        "Dockerfile": "RUN apt-get install -y --no-install-recommends libold1 libstay1\n",
    }
    new_files = {
        "requirements.txt": "oldpkg\n# commentpkg\n-e ./localpkg\nSome_Name>=1\nnew_pkg>=2\n",
        "requirements-dev.txt": "devonly\ndevnew\n",
        "requirements-test.txt": "testonly\ntestnew\n",
        "pyproject.toml": (
            "[project]\nname = \"engine\"\nversion = \"1.3.0\"\n"
            "dependencies = [\"oldpy\", \"New_PyDep>=1\"]\n"
        ),
        "Dockerfile": "RUN apt-get install -y --no-install-recommends libstay1 libnew1 libalready\n",
    }
    upstream = _make_repo(tmp_path, "up", old_files)
    _git(upstream, "tag", "v1.2.0")
    old = _git(upstream, "rev-parse", "v1.2.0^{}")
    _commit(upstream, new_files)
    _git(upstream, "tag", "v1.3.0")
    new = _git(upstream, "rev-parse", "v1.3.0^{}")
    skill_text = "\n".join([
        "---",
        "name: engine-fixtureengine",
        "engine: Fixture",
        "id: fixtureengine",
        f"repo: {upstream}",
        "ref: v1.2.0",
        "ref_kind: tag",
        "version: v1.2.0",
        f"pinned: {old}",
        'verified: "2026-10-05"',
        "license: MIT",
        "servable: true",
        "backends: [cuda, cpu]",
        "os: [linux]",
        "formats: [gguf]",
        "upstream_watch: [requirements.txt, requirements-dev.txt, requirements-test.txt, pyproject.toml, Dockerfile]",
        "install:",
        "  common:",
        "    - \"cmake --build {build}\"",
        "container:",
        "  cuda:",
        "    apt: [libold1, libalready]",
        "  cpu:",
        "    apt: [libold1, libalready]",
        "---",
        "# body",
        "",
    ])
    checkout, skill_path = _checkout(tmp_path, "fixtureengine", skill_text, old, "v1.2.0")
    _commit_real_regen(checkout, "fixtureengine")
    skill = es.load_skill(skill_path)

    # When derive has no old sha, the new tree is not treated as all-new
    bare = epd.derive(skill, new, repo_dir=upstream, ref="v1.3.0")
    assert "dependencies" not in bare["report"]
    assert bare["hard_fail"] is None

    # When the bump runs through pin, apply, and make generate-engine-params
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.setenv("LLGENIE_SRC", str(REPO))
    monkeypatch.setenv("LLGENIE_CHECKOUT", str(checkout))
    orig_skills, orig_root = es.SKILLS_DIR, eb.REPO_ROOT
    es.SKILLS_DIR = checkout / "skills" / "engines"
    eb.REPO_ROOT = checkout
    head = _git(checkout, "rev-parse", "HEAD")
    try:
        rows = eb.bump("fixtureengine")
    finally:
        es.SKILLS_DIR = orig_skills
        eb.REPO_ROOT = orig_root
    out = capsys.readouterr().out

    # Then the pin moved, the ignored names stayed out, and nothing was committed
    assert _git(checkout, "rev-parse", "HEAD") == head
    assert _git(checkout, "remote") == ""
    assert "SKILL.md" in _git(checkout, "status", "--porcelain")
    assert len(rows) == 1
    assert rows[0]["old_sha"] == old and rows[0]["new_sha"] == new
    assert rows[0]["new_ref"] == "v1.3.0"
    assert rows[0]["hard_fail"]
    assert "new-pkg" in rows[0]["hard_fail"] and "new-pydep" in rows[0]["hard_fail"]
    assert "commentpkg" not in rows[0]["hard_fail"]
    assert "devnew" not in rows[0]["hard_fail"] and "testnew" not in rows[0]["hard_fail"]
    assert (
        "[engine-bump] DEPS python_added=new-pkg,new-pydep "
        "apt_added=libalready,libnew1 python_removed= apt_removed=libold1"
    ) in out
    text = skill_path.read_text()
    assert "ref: v1.3.0" in text and f"pinned: {new}" in text
    assert text.count("apt: [libold1, libalready, libnew1]") == 2
    assert "libalready, libalready" not in text
    assert "cmake --build" in text and "new-pkg" not in text and "new-pydep" not in text
    # The files make wrote, not a second render after bump returned
    params = json.loads((checkout / "containers/engines/params/fixtureengine.json").read_text())
    for backend in ("cuda", "cpu"):
        dockerfile = (checkout / "containers/engines/dockerfiles/fixtureengine" / f"Dockerfile.{backend}").read_text()
        base = es.render_base_dockerfile(backend)
        assert "apt-get install" in dockerfile and "libnew1" in dockerfile
        assert "libalready" in dockerfile and "libold1" in dockerfile
        assert "libstay1" not in dockerfile and "libnew1" not in base
        joined = "\n".join(params["variants"][backend]["install"])
        assert "cmake --build" in joined
        assert "new-pkg" not in joined and "devnew" not in joined


def test_bump_reports_packages_the_new_tag_removed(tmp_path, capsys, monkeypatch):
    """The v1.0.7 shape: the new tag drops pyproject dependencies and adds none.

    bump must say those names were removed. It must not invent a pip line,
    and it must not commit.
    """

    # Given the packages the TensorFold v1.0.7 pin removed
    names = ["huggingface-hub", "jinja2", "mlx", "mlx-lm", "numpy", "safetensors", "tokenizers"]
    old_py = (
        "[project]\nname = \"engine\"\nversion = \"1.0.6\"\ndependencies = [\n"
        + "".join(f"  \"{name}\",\n" for name in names)
        + "]\n"
    )
    new_py = "[project]\nname = \"engine\"\nversion = \"1.0.7\"\ndependencies = []\n"
    upstream = _make_repo(tmp_path, "up", {"pyproject.toml": old_py})
    _git(upstream, "tag", "v1.0.6")
    old = _git(upstream, "rev-parse", "v1.0.6^{}")
    _commit(upstream, {"pyproject.toml": new_py})
    _git(upstream, "tag", "v1.0.7")
    new = _git(upstream, "rev-parse", "v1.0.7^{}")
    install = "uv tool install --python 3.11 tensorfold @ git+{repo}@{pinned}"
    skill_text = "\n".join([
        "---",
        "name: engine-fixtureengine",
        "engine: Fixture",
        "id: fixtureengine",
        f"repo: {upstream}",
        "ref: v1.0.6",
        "ref_kind: tag",
        "version: v1.0.6",
        f"pinned: {old}",
        'verified: "2026-10-05"',
        "license: MIT",
        "servable: true",
        "backends: [cuda]",
        "os: [linux]",
        "formats: [gguf]",
        "upstream_watch: [pyproject.toml]",
        "install:",
        "  common:",
        f"    - \"{install}\"",
        "---",
        "# body",
        "",
    ])
    checkout, skill_path = _checkout(tmp_path, "fixtureengine", skill_text, old, "v1.0.6")
    _commit_real_regen(checkout, "fixtureengine")

    # When the bump runs
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.setenv("LLGENIE_SRC", str(REPO))
    monkeypatch.setenv("LLGENIE_CHECKOUT", str(checkout))
    orig_skills, orig_root = es.SKILLS_DIR, eb.REPO_ROOT
    es.SKILLS_DIR = checkout / "skills" / "engines"
    eb.REPO_ROOT = checkout
    head = _git(checkout, "rev-parse", "HEAD")
    try:
        rows = eb.bump("fixtureengine")
    finally:
        es.SKILLS_DIR = orig_skills
        eb.REPO_ROOT = orig_root
    out = capsys.readouterr().out

    # Then the removal is on the DEPS line and the install text is untouched
    assert _git(checkout, "rev-parse", "HEAD") == head
    assert rows[0]["hard_fail"] is None
    removed = "huggingface-hub,jinja2,mlx,mlx-lm,numpy,safetensors,tokenizers"
    assert f"python_removed={removed}" in out
    assert "python_added= " in out or "python_added= apt_added=" in out
    text = skill_path.read_text()
    assert install in text
    assert "pip install" not in text
    assert f"pinned: {new}" in text


def _commit_real_regen(checkout: Path, skill_id: str) -> None:
    """Replace the `@true` Makefile with one that runs `write_params`."""

    (checkout / "regen.py").write_text(
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, os.environ['LLGENIE_SRC'])\n"
        "import scripts.engine_skills as es\n"
        "root = Path(os.environ['LLGENIE_CHECKOUT'])\n"
        "es.REPO_ROOT = root\n"
        "es.SKILLS_DIR = root / 'skills' / 'engines'\n"
        "es.CONTAINER_DIR = root / 'containers' / 'engines'\n"
        "es.PARAMS_DIR = es.CONTAINER_DIR / 'params'\n"
        "es.DOCKERFILES_DIR = es.CONTAINER_DIR / 'dockerfiles'\n"
        "es.BASE_DIR = es.CONTAINER_DIR / 'base'\n"
        f"es.write_params(es.load_skills(), only={skill_id!r})\n"
    )
    (checkout / "Makefile").write_text(
        "generate-engine-params:\n"
        "\tpython3 regen.py\n"
    )
    # The live bump edits Dockerfiles that are already tracked. Seed them so
    # git status names the files instead of a new untracked directory.
    for backend in ("cuda", "cpu"):
        path = checkout / "containers/engines/dockerfiles" / skill_id / f"Dockerfile.{backend}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n")
    params = checkout / "containers/engines/params" / f"{skill_id}.json"
    params.parent.mkdir(parents=True, exist_ok=True)
    params.write_text("{}\n")
    _git(checkout, "add", "-A")
    _git(checkout, "commit", "-qm", "regen runs write_params")


def test_dpkg_shlibdeps_names_libc(tmp_path):
    """dpkg-shlibdeps names the Debian packages a real binary links.

    The Linux unit container is root and can apt-get install gcc and dpkg-dev,
    then this asserts libc6. A host that cannot install the tool still runs
    the call and must fail loudly. The published test image is unchanged.
    """

    # Given a Debian root container, install the real tool
    if shutil.which("dpkg-shlibdeps") is None and shutil.which("apt-get") and os.geteuid() == 0:
        subprocess.run(["apt-get", "update", "-qq"], check=True)
        subprocess.run(
            ["apt-get", "install", "-y", "-qq", "gcc", "dpkg-dev"],
            check=True,
        )

    # Given the tool is still absent on this host
    if shutil.which("dpkg-shlibdeps") is None or shutil.which("gcc") is None:
        # When the call runs
        with pytest.raises(RuntimeError, match="dpkg-shlibdeps is not installed"):
            engine_deps.shlib_packages(tmp_path / "missing")
        # Then it named the missing tool
        return

    # Given a binary this machine just compiled
    src = tmp_path / "hi.c"
    src.write_text("int main(void){return 0;}\n")
    binary = tmp_path / "hi"
    built = subprocess.run(["gcc", "-o", str(binary), str(src)], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr

    # When the shared-library command reads it
    packages = engine_deps.shlib_packages(binary)

    # Then libc is one of the packages
    assert "libc6" in packages
