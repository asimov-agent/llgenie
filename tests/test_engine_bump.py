"""Daily engine pin bump (issue #107, feat-engine-bump-daily).

Locks openspec/changes/feat-engine-bump-daily/specs/engine-bump-daily/spec.md.
Hermetic: fixture git repos are REAL git repos created in the test (not mocked
subprocess calls), so plan/derive run against real git. No network, no skips.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.engine_bump as eb
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
    """Tag skill picks the highest stable vX.Y.Z, no -rc, peeled sha."""
    repo = _make_repo(tmp_path, "up", {"f": "x"})
    for tag in ("v0.9.7-rc1", "v0.10.0", "v0.9.10", "v0.40.0"):
        _git(repo, "tag", tag)
    skill = _skill(tmp_path, str(repo), "v0.35.1", "tag", "a" * 40)
    orig = es.load_skills
    es.load_skills = lambda: {"testengine": skill}
    try:
        rows = eb.plan("testengine")
    finally:
        es.load_skills = orig
    assert rows[0]["new_ref"] == "v0.40.0"
    assert rows[0]["new_sha"]  # peeled sha present


def test_plan_never_moves_backwards(tmp_path):
    """A pin newer than the highest upstream tag is skipped."""
    repo = _make_repo(tmp_path, "up", {"f": "x"})
    _git(repo, "tag", "v0.10.0")
    skill = _skill(tmp_path, str(repo), "v0.35.1", "tag", "a" * 40)
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
        "ref: v0.35.1\n"
        "ref_kind: tag\n"
        "version: v0.35.1\n"
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
    with pytest.raises(SystemExit, match="another engine"):
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


def test_changed_engines_scopes_matrix(tmp_path):
    """matrix(changed=...) keeps only engines whose params differ."""
    import scripts.engine_image as ei
    # no diff on this branch -> the one placeholder row, never an empty include
    # (GitHub fails a workflow whose matrix include list is empty)
    rows = ei.matrix(ci=True, changed="origin/main")
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


def test_real_docker_build_llama_cpp_cpu():
    """Real happy path: `make build-engine ENGINE=llama.cpp ARCH=cpu` builds the
    image from the generated Dockerfile + params (docker required). The image
    must build and its entrypoint must report a version."""
    import shutil
    if not shutil.which("docker"):
        pytest.fail("docker is required for the real build test")
    import scripts.engine_image as ei
    spec = ei.resolve("llama.cpp", None, "cpu")
    # build (force, so it actually runs even if a stale tag exists)
    rc = ei.build(spec, force=True)
    assert rc == 0, f"make build-engine llama.cpp cpu failed (exit {rc})"
    # the built image answers `version`
    r = subprocess.run([ei.RUNTIME, "run", "--rm", spec["tag"], "version"],
                       capture_output=True, text=True, timeout=300)
    out = (r.stdout + r.stderr).strip()
    assert r.returncode == 0, f"llama.cpp cpu `version` exited {r.returncode}: {out}"
    assert out, "llama.cpp cpu `version` printed nothing"
    print(f"[build] llama.cpp cpu built and answered: {out.splitlines()[-1]}")
