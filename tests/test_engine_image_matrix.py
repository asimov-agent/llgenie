"""The engine-image matrix publishes only images whose tag changed (issue #153).

The tag is `llgenie/<id>:<pin8>-<image-hash>-<arch>`. A ref where that tag is
identical is already published, so the matrix must leave it out. The git repo
is a real one, created in the test, never the working tree.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import scripts.engine_image as ei
import scripts.engine_skills as es

REPO = Path(__file__).resolve().parent.parent
PLACEHOLDER = {"engine": "none", "backend": "cpu", "variant": "none",
               "smoke": False, "test": "detect", "chat": ""}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _repo(tmp_path: Path, files: dict[str, str]) -> tuple[Path, str]:
    """A real git repo with `files` committed. Returns (repo, HEAD sha)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@llgenie")
    _git(repo, "config", "user.name", "test")
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    _git(repo, "add", ".")
    assert _git(repo, "commit", "-q", "-m", "base").returncode == 0
    return repo, _git(repo, "rev-parse", "HEAD").stdout.strip()


def _params(engine: str, pinned: str, variant: dict) -> str:
    return json.dumps({"id": engine, "engine": engine, "pinned": pinned,
                       "variants": {"cpu": variant}}, indent=2) + "\n"


_VARIANT = {"backend": "cpu", "base": "ubuntu:24.04", "prebuilt": False, "runtime_base": "",
            "runtime_copy": [], "apt": [], "build_args": {}, "install": ["echo hi"], "env": {},
            "detect": "true", "pre_launch": None, "launch": "true", "post_launch": None,
            "health": "GET /health", "alias_mode": "flag", "run_args": [], "port": 11434}


def _point(monkeypatch, repo: Path):
    monkeypatch.setattr(es, "REPO_ROOT", repo)
    monkeypatch.setattr(es, "CONTAINER_DIR", repo / "containers" / "engines")
    # engine_image imports the SKILLS module under its bare name (``import engine_skills as es``),
    # which is a DIFFERENT module object than ``scripts.engine_skills`` when the scripts/ package
    # is also on the path — so ei.build() would read the REAL committed Dockerfiles/params, not the
    # tmp repo's. Point ei at the same object the test patches so the synthetic tree is authoritative.
    monkeypatch.setattr(ei, "es", es)
    monkeypatch.setattr(ei, "CI_VARIANTS", {"cpu"})
    monkeypatch.setattr(ei, "disabled", lambda e, v: "")


_SHARED = {
    "containers/engines/entrypoint.sh": "#!/bin/sh\n",
    "scripts/engine_runner.py": "# runner\n",
    "containers/engines/dockerfiles/llama.cpp/Dockerfile.cpu": "FROM ubuntu\n",
    "containers/engines/dockerfiles/ollama/Dockerfile.cpu": "FROM ubuntu\n",
}


@pytest.mark.parametrize("engine", [
    "tensorfold",       # PR #165
    "llama.cpp-prism",  # PR #166
    "strata",           # PR #167
    "llama.cpp",        # PR #168
])
def test_each_bump_pr_engine_is_scoped_not_a_placeholder(tmp_path, monkeypatch, engine):
    """A pin move for this engine is that engine's rows, not the placeholder.

    linux / unit failed on #165, #166, #167 and #168 because the check compared
    the bump branch to origin/main and expected engine: none. The pin move
    changes the image tag, so the matrix lists this engine and not the sibling.
    Once that pin is committed, HEAD against itself is the placeholder again.
    """

    # Given this engine and a sibling, both pinned, then only this pin moves
    other = "ollama"
    old, new = "a" * 40, "b" * 40
    files = {
        f"containers/engines/params/{engine}.json": _params(engine, old, _VARIANT),
        f"containers/engines/params/{other}.json": _params(other, old, _VARIANT),
        "containers/engines/entrypoint.sh": "#!/bin/sh\n",
        "scripts/engine_runner.py": "# runner\n",
        f"containers/engines/dockerfiles/{engine}/Dockerfile.cpu": "FROM ubuntu\n",
        f"containers/engines/dockerfiles/{other}/Dockerfile.cpu": "FROM ubuntu\n",
    }
    repo, parent = _repo(tmp_path, files)
    moved = json.loads(files[f"containers/engines/params/{engine}.json"])
    moved["pinned"] = new
    (repo / "containers" / "engines" / "params" / f"{engine}.json").write_text(
        json.dumps(moved, indent=2) + "\n")
    _point(monkeypatch, repo)

    # When the matrix is scoped to the parent, before the pin is committed
    rows = ei.matrix(ci=True, changed=parent, params_dir=repo / "containers" / "engines" / "params")

    # Then this engine is built and the placeholder is not what a bump PR gets
    assert rows != [PLACEHOLDER]
    assert {r["engine"] for r in rows} == {engine}

    # And once the pin is the tree, HEAD against itself publishes nothing
    assert _git(repo, "add", ".").returncode == 0
    assert _git(repo, "commit", "-q", "-m", "pin").returncode == 0
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert ei.matrix(ci=True, changed=head,
                     params_dir=repo / "containers" / "engines" / "params") == [PLACEHOLDER]


def test_two_moved_pins_list_both_engines(tmp_path, monkeypatch):
    """Two pin moves are two engines. A bump of one must not hide the other."""

    # Given llama.cpp and ollama, both pins moved and nothing else
    old, new = "a" * 40, "b" * 40
    files = {
        "containers/engines/params/llama.cpp.json": _params("llama.cpp", old, _VARIANT),
        "containers/engines/params/ollama.json": _params("ollama", old, _VARIANT),
        **_SHARED,
    }
    repo, parent = _repo(tmp_path, files)
    for engine in ("llama.cpp", "ollama"):
        moved = json.loads(files[f"containers/engines/params/{engine}.json"])
        moved["pinned"] = new
        (repo / "containers" / "engines" / "params" / f"{engine}.json").write_text(
            json.dumps(moved, indent=2) + "\n")
    _point(monkeypatch, repo)

    # When the matrix is scoped to the parent
    rows = ei.matrix(ci=True, changed=parent, params_dir=repo / "containers" / "engines" / "params")

    # Then both engines are listed and the placeholder is not
    assert {r["engine"] for r in rows} == {"llama.cpp", "ollama"}
    assert rows != [PLACEHOLDER]


def test_a_non_image_file_change_stays_the_placeholder(tmp_path, monkeypatch):
    """A file the image tag does not hash leaves the matrix on the placeholder."""

    # Given a committed tree, then only README.md changes
    files = {
        "containers/engines/params/llama.cpp.json": _params("llama.cpp", "a" * 40, _VARIANT),
        "README.md": "before\n",
        **_SHARED,
    }
    repo, parent = _repo(tmp_path, files)
    (repo / "README.md").write_text("after\n")
    _point(monkeypatch, repo)

    # When the matrix is scoped to the parent
    rows = ei.matrix(ci=True, changed=parent, params_dir=repo / "containers" / "engines" / "params")

    # Then nothing is built
    assert rows == [PLACEHOLDER]


def test_matrix_keeps_only_the_engine_whose_pin_changed(tmp_path, monkeypatch):
    """One moved pin rebuilds that engine only."""

    # Given a repo where llama.cpp's pin moved and ollama's did not
    base = {
        "containers/engines/params/llama.cpp.json": _params("llama.cpp", "a" * 40, _VARIANT),
        "containers/engines/params/ollama.json": _params("ollama", "b" * 40, _VARIANT),
        **_SHARED,
    }
    repo, parent = _repo(tmp_path, base)
    moved = json.loads(base["containers/engines/params/llama.cpp.json"])
    moved["pinned"] = "c" * 40
    (repo / "containers/engines/params/llama.cpp.json").write_text(json.dumps(moved, indent=2) + "\n")
    _point(monkeypatch, repo)

    # When the matrix is scoped to the parent commit
    rows = ei.matrix(ci=True, changed=parent, params_dir=repo / "containers" / "engines" / "params")

    # Then only llama.cpp is built
    assert {r["engine"] for r in rows} == {"llama.cpp"}
    assert rows[0]["variant"] == "cpu"


def test_matrix_rebuilds_all_when_a_shared_build_file_changes(tmp_path, monkeypatch):
    """engine_runner.py is hashed into every image tag."""

    # Given a parent where the shared runner differs and no pin does
    files = {
        "containers/engines/params/llama.cpp.json": _params("llama.cpp", "a" * 40, _VARIANT),
        "containers/engines/params/ollama.json": _params("ollama", "b" * 40, _VARIANT),
        **_SHARED,
    }
    repo, parent = _repo(tmp_path, files)
    (repo / "scripts" / "engine_runner.py").write_text("# runner\n# changed\n")
    _point(monkeypatch, repo)

    # When the matrix is scoped to that parent
    rows = ei.matrix(ci=True, changed=parent, params_dir=repo / "containers" / "engines" / "params")

    # Then both engines are rebuilt: the tag embeds the runner's bytes
    assert {r["engine"] for r in rows} == {"llama.cpp", "ollama"}


def test_matrix_placeholder_when_no_tag_changed(tmp_path, monkeypatch):
    """An unchanged tree publishes nothing, and the matrix stays legal."""

    # Given a repo compared with its own HEAD
    repo, head = _repo(tmp_path, {
        "containers/engines/params/llama.cpp.json": _params("llama.cpp", "a" * 40, _VARIANT),
        **_SHARED})
    _point(monkeypatch, repo)

    # When the matrix is scoped to it
    rows = ei.matrix(ci=True, changed=head, params_dir=repo / "containers" / "engines" / "params")

    # Then the only row is the placeholder an empty include list cannot be
    assert rows == [PLACEHOLDER]


def test_push_workflow_builds_the_whole_committed_set():
    """The engine-build producer builds every committed engine x variant (issue #614 / #1027);
    it does not CHANGED-scope like the old ci.yml engine-matrix did, so a bumped pin is rebuilt
    by dispatching the whole sweep — dispatch inputs (engine / arch) narrow it, never a git filter."""

    # Given the engine-build workflow
    text = (REPO / ".github" / "workflows" / "engine-build.yml").read_text()

    # Then the matrix comes from the committed params as the full sweep, and is narrowed only by dispatch inputs
    assert "make -s engine-build-matrix ENGINE=" in text
    assert "empty = every engine in the committed params" in text


def test_every_changed_image_is_built_tested_and_published():
    """The row the matrix emits is the row the engine-build producer builds, tests and pushes.

    The producer's build job runs build-engine -> test-engine-stage -> push-engine for every
    committed row, then the serve-leg (test-published-engine) and install-leg (test-engine-install)
    on the just-published image when the dispatch says push. A build-only dispatch publishes nothing.
    """

    # Given the engine-build workflow
    text = (REPO / ".github" / "workflows" / "engine-build.yml").read_text()

    # When the producer runs a row
    # Then it builds, tests and publishes that exact engine and arch, and never the none row
    assert "make build-engine ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}" in text
    assert "make test-engine-stage ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}" in text
    assert "make push-engine ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}" in text
    assert "make test-published-engine ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}" in text
    assert "make test-engine-install ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}" in text
    assert "matrix.engine != 'none'" in text and "inputs.push == 'true'" in text


# ---------------------------------------------------------------------------
# The tag itself is the contract: the matrix skips an image only when the tag
# `make install` pulls is already published. These lock that contract against
# the issue #154 failure class — a tag-hash change that moved every tag while
# the scoped matrix rebuilt nothing, so every install job asked GHCR for an
# image that had never been pushed.
# ---------------------------------------------------------------------------

_PUBLISHED_DIGEST = "e1d5f785"  # sha256(variant json + Dockerfile + entrypoint + runner)


def _fixture_params() -> dict:
    return {"id": "llama.cpp", "engine": "llama.cpp", "pinned": "a" * 40, "variants": {"cpu": _VARIANT}}


def test_tag_digest_is_the_published_scheme():
    """The tag hash inputs and their framing are the ones GHCR was published with.

    Changing what is hashed, or how the parts are joined, moves every engine's
    tag at once: every image already on GHCR becomes unreachable and every
    install job fails with 'not published' while the scoped matrix rebuilds
    nothing. The digest is therefore pinned here — a change must be deliberate.
    """

    # Given the fixed fixture inputs (variant params, Dockerfile, entrypoint, runner)
    params = _fixture_params()

    # When the tag bytes are hashed
    digest = hashlib.sha256(es._image_inputs(params, "cpu", dockerfile=b"FROM ubuntu\n",
                                             entrypoint=b"#!/bin/sh\n", runner=b"# runner\n")).hexdigest()[:8]

    # Then the digest is the published scheme's, unchanged
    assert digest == _PUBLISHED_DIGEST


def test_tag_hash_follows_every_input_it_claims(tmp_path):
    """Each input moves the tag it is said to cover, and only that one."""

    # Given the fixture tree
    params = _fixture_params()
    base = es._image_inputs(params, "cpu", dockerfile=b"FROM ubuntu\n",
                            entrypoint=b"#!/bin/sh\n", runner=b"# runner\n")

    # When one input changes at a time
    moved_pin = hashlib.sha256(es._image_inputs({**params, "pinned": "c" * 40}, "cpu",
                                                dockerfile=b"FROM ubuntu\n", entrypoint=b"#!/bin/sh\n",
                                                runner=b"# runner\n")).hexdigest()[:8]
    moved_variant = hashlib.sha256(es._image_inputs(
        {"id": "llama.cpp", "engine": "llama.cpp", "pinned": "a" * 40,
         "variants": {"cpu": {**_VARIANT, "port": 12345}}}, "cpu",
        dockerfile=b"FROM ubuntu\n", entrypoint=b"#!/bin/sh\n", runner=b"# runner\n")).hexdigest()[:8]
    moved_dockerfile = hashlib.sha256(es._image_inputs(params, "cpu", dockerfile=b"FROM ubuntu\n# x\n",
                                                       entrypoint=b"#!/bin/sh\n", runner=b"# runner\n")).hexdigest()[:8]
    moved_entry = hashlib.sha256(es._image_inputs(params, "cpu", dockerfile=b"FROM ubuntu\n",
                                                  entrypoint=b"#!/bin/sh\n# x\n", runner=b"# runner\n")).hexdigest()[:8]
    moved_runner = hashlib.sha256(es._image_inputs(params, "cpu", dockerfile=b"FROM ubuntu\n",
                                                   entrypoint=b"#!/bin/sh\n", runner=b"# runner\n# x\n")).hexdigest()[:8]

    # Then every one of them moves the tag, and the unchanged tree does not
    assert hashlib.sha256(base).hexdigest()[:8] == _PUBLISHED_DIGEST
    assert {moved_pin, moved_variant, moved_dockerfile, moved_entry, moved_runner} - {_PUBLISHED_DIGEST}


def _real_build_inputs(tmp_path) -> tuple[Path, str]:
    """A scratch git repo holding THIS repo's committed build inputs (params,
    Dockerfiles, entrypoint, runner). The working tree is never touched.

    Returns (repo, sha of the untouched tree).
    """
    repo = tmp_path / "tree"
    for rel in ("containers/engines/params", "containers/engines/dockerfiles"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(REPO / rel, repo / rel)
    for rel in ("containers/engines/entrypoint.sh", "scripts/engine_runner.py"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, repo / rel)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@llgenie")
    _git(repo, "config", "user.name", "test")
    _git(repo, "add", ".")
    assert _git(repo, "commit", "-q", "-m", "committed build inputs").returncode == 0
    return repo, _git(repo, "rev-parse", "HEAD").stdout.strip()


def _rows(repo: Path, ref: str) -> list[dict]:
    return ei.matrix(ci=True, changed=ref, params_dir=repo / "containers" / "engines" / "params")


def test_unchanged_committed_tree_publishes_nothing(tmp_path):
    """The committed tree compared with itself builds no engine at all."""

    # Given a scratch repo whose working tree equals its own commit
    repo, sha = _real_build_inputs(tmp_path)

    # When the matrix is scoped to that commit
    rows = _rows(repo, sha)

    # Then only the placeholder row is left: an empty include list is illegal
    assert rows == [PLACEHOLDER]


def test_a_moved_pin_builds_only_that_engine(tmp_path):
    """On the real 13-engine tree, one moved pin rebuilds that engine's variants."""

    # Given the committed build inputs, with ollama's pin moved in the working tree
    repo, sha = _real_build_inputs(tmp_path)
    ollama = repo / "containers" / "engines" / "params" / "ollama.json"
    params = json.loads(ollama.read_text())
    params["pinned"] = "0" * 40
    ollama.write_text(json.dumps(params, indent=2) + "\n")

    # When the matrix is scoped to the untouched commit
    rows = _rows(repo, sha)

    # Then ollama's CI variants are the only rows, every other engine is skipped
    assert {r["engine"] for r in rows} == {"ollama"}
    assert {r["variant"] for r in rows} == {v for v in params["variants"] if v in ei.CI_VARIANTS}


# The engine-image job's run lines. A bumped row is built, tested and published
# by substituting matrix.engine / matrix.variant / matrix.test into these.
_CI_MAKE = (
    "make build-engine ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}",
    "make test-engine-stage ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }} TEST=${{ matrix.test }}",
    "make push-engine ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}",
)


def _ci_make_calls(row: dict) -> list[str]:
    """The make commands the engine-image job runs for one matrix row."""
    return [line.replace("${{ matrix.engine }}", row["engine"])
                .replace("${{ matrix.variant }}", row["variant"])
                .replace("${{ matrix.test }}", row["test"])
            for line in _CI_MAKE]


def test_each_bumped_engine_gets_its_make_calls(tmp_path):
    """A moved pin on any engine is the make build/test/push CI runs for its variants."""

    # Given the committed engines, and the make lines the engine-build build job runs
    repo, sha = _real_build_inputs(tmp_path)
    job = (REPO / ".github" / "workflows" / "engine-build.yml").read_text()
    for line in _CI_MAKE:
        assert line in job
    params_dir = repo / "containers" / "engines" / "params"

    # When each engine's pin is moved, one engine at a time
    seen = []
    for path in sorted(params_dir.glob("*.json")):
        original = path.read_text()
        params = json.loads(original)
        engine = params["id"]
        params["pinned"] = "c" * 40 if params.get("pinned") == "b" * 40 else "b" * 40
        path.write_text(json.dumps(params) + "\n")
        rows = _rows(repo, sha)
        path.write_text(original)

        # Then CI's make commands name that engine and each of its CI variants
        variants = [v for v in params["variants"]
                    if v in ei.CI_VARIANTS and not ei.disabled(engine, v)
                    and not (engine in ei.DEFAULT_CPU_ONLY and v != "cpu")]
        if not variants:
            assert rows == [PLACEHOLDER], engine
            continue
        assert {r["engine"] for r in rows} == {engine}, engine
        assert {r["variant"] for r in rows} == set(variants), engine
        calls = [call for row in rows for call in _ci_make_calls(row)]
        for row in rows:
            assert _ci_make_calls(row) == [
                f"make build-engine ENGINE={engine} ARCH={row['variant']}",
                f"make test-engine-stage ENGINE={engine} ARCH={row['variant']} TEST={row['test']}",
                f"make push-engine ENGINE={engine} ARCH={row['variant']}",
            ]
        assert all(f"ENGINE={engine} " in call for call in calls)
        seen.append(engine)

    # And two bumped engines produce both engines' make calls, not one of them
    assert len(seen) >= 2
    first, second = seen[0], seen[1]
    for engine in (first, second):
        path = params_dir / f"{engine}.json"
        params = json.loads(path.read_text())
        params["pinned"] = "d" * 40
        path.write_text(json.dumps(params) + "\n")
    rows = _rows(repo, sha)
    calls = [call for row in rows for call in _ci_make_calls(row)]
    assert {r["engine"] for r in rows} == {first, second}
    for engine in (first, second):
        assert any(call.startswith(f"make build-engine ENGINE={engine} ") for call in calls)
        assert any(call.startswith(f"make push-engine ENGINE={engine} ") for call in calls)


def test_a_variant_param_builds_only_that_variant(tmp_path):
    """A frozen variant param (not the pin) moves exactly that engine x arch row."""

    # Given the committed build inputs, with vllm's cpu port changed
    repo, sha = _real_build_inputs(tmp_path)
    vllm = repo / "containers" / "engines" / "params" / "vllm.json"
    params = json.loads(vllm.read_text())
    params["variants"]["cpu"]["port"] = 12345
    vllm.write_text(json.dumps(params, indent=2) + "\n")

    # When the matrix is scoped to the untouched commit
    rows = _rows(repo, sha)

    # Then only vllm/cpu is rebuilt; its cuda/rocm rows are already published
    assert {(r["engine"], r["variant"]) for r in rows} == {("vllm", "cpu")}


def test_default_vllm_matrix_is_cpu_only_and_explicit_arch_builds_gpu(tmp_path):
    """Issue #1836: the default whole-set sweep builds vllm CPU only; the GPU
    cells are built only when ARCH=cuda / ARCH=rocm is explicit.

    The vllm cuda cell OOMs the standard runner (run 42176975953, exit 143) and
    the rocm cell runs ~4 h and is wall-cancelled (run 42159549121), so a GPU
    vllm cell must NOT be part of the default build-engine pipeline. An explicit
    ARCH= still emits exactly that variant.
    """

    # Given the real committed build inputs (params carry vllm cuda/rocm/cpu)
    repo, sha = _real_build_inputs(tmp_path)

    # When the default (ARCH= empty, CI) matrix is computed
    default = ei.matrix(ci=True)

    # Then vllm is CPU-only: cpu present, cuda/rocm absent
    vllm = {r["variant"] for r in default if r["engine"] == "vllm"}
    assert "cpu" in vllm
    assert vllm == {"cpu"}, vllm

    # And the explicit-arch matrix still emits exactly that GPU variant
    for arch in ("cuda", "rocm"):
        gpu = {r["variant"] for r in ei.matrix(ci=True, arch=arch) if r["engine"] == "vllm"}
        assert gpu == {arch}, (arch, gpu)


def test_a_shared_build_file_rebuilds_every_ci_engine(tmp_path):
    """entrypoint.sh / engine_runner.py are in every tag, so they rebuild all."""

    # Given the committed build inputs, with the shared runner edited
    repo, sha = _real_build_inputs(tmp_path)
    runner = repo / "scripts" / "engine_runner.py"
    runner.write_text(runner.read_text() + "# touched\n")

    # When the matrix is scoped to the untouched commit
    rows = _rows(repo, sha)

    # Then every engine the unscoped CI matrix would build appears here too
    assert {r["engine"] for r in rows} == {r["engine"] for r in ei.matrix(ci=True)}


def test_matrix_tag_is_the_tag_install_pulls():
    """The tag the matrix compares is the tag `make install` pulls.

    If the two ever disagree, the matrix can skip an image the install path then
    asks GHCR for — the exact failure that turned every install job red.
    """

    # Given every committed engine x variant
    for path in sorted((REPO / "containers" / "engines" / "params").glob("*.json")):
        params = json.loads(path.read_text())

        # When the matrix's tag and the install path's tag are computed
        for variant in params["variants"]:
            # Then they are the same tag, and it names the built image
            assert ei._current_tag(params, variant) == es.image_spec(params, variant)["tag"]


def test_every_matrix_row_is_an_engine_make_build_engine_can_build():
    """Every row the CI matrix emits has the params + Dockerfile build-engine needs."""

    # Given the unscoped CI matrix (every engine x arch CI builds)
    rows = ei.matrix(ci=True)

    # When each row is resolved the way `make build-engine ENGINE=… ARCH=…` does
    makefile = (REPO / "Makefile").read_text()
    assert "make build-engine ENGINE=<id>" in makefile or "build-engine ENGINE=" in makefile
    for row in rows:
        # Then its params file and its generated Dockerfile exist in the repo
        params = json.loads((REPO / "containers" / "engines" / "params" / f"{row['engine']}.json").read_text())
        dockerfile = es.dockerfile_path(row["engine"], row["variant"])

        # And the row is the engine/arch build-engine is given, with a real tag
        assert dockerfile.exists(), f"{row['engine']}/{row['variant']}: no {dockerfile}"
        assert es.image_spec(params, row["variant"])["tag"].endswith(f"-{row['variant']}")


def test_every_supported_arch_has_a_generated_dockerfile():
    """Every engine's every supported variant (from its params) has a generated Dockerfile
    at containers/engines/dockerfiles/<engine>/Dockerfile.<variant> (issue #1092).

    A supported arch with no Dockerfile is a gap that must be caught HERE, not discovered
    when the build runs — the engine-build matrix can only build what a Dockerfile exists
    for. The base toolchain Dockerfile.<backend> it FROMs is checked by the build itself.
    """
    params_dir = REPO / "containers" / "engines" / "params"
    df_dir = REPO / "containers" / "engines" / "dockerfiles"
    missing: list[str] = []
    checked = 0
    for p in sorted(params_dir.glob("*.json")):
        variants = json.loads(p.read_text()).get("variants") or {}
        for v in variants:
            checked += 1
            if not (df_dir / p.stem / f"Dockerfile.{v}").is_file():
                missing.append(f"{p.stem}/{v}")
    assert checked > 0, "no engine params found — the audit would pass vacuously"
    assert not missing, f"supported arch(es) with no generated Dockerfile: {missing}"


# ---------------------------------------------------------------------------
# The derived-cell base-stage merge (issue #1753 / #1832): on the docker-container
# buildx driver a base left by a PREVIOUS buildx invocation is never resolvable by a
# later `FROM <base>` — buildx falls through to the registry (docker.io for a bare
# `llgenie/base-*` name) and is denied with `insufficient_scope`. `_combine_base_stage`
# aliases the backend toolchain `FROM` and points the derived `FROM <base>` at that
# internal stage, so ONE build resolves it with no registry dependency. These lock the
# conversion on the REALLY-committed per-arch Dockerfiles, so a param/Dockerfile change
# that reintroduces a cross-invocation base pull is caught here.
# ---------------------------------------------------------------------------


def test_combine_base_stage_removes_cross_invocation_base_pull():
    """A derived Dockerfile that `FROM`s the backend base must, after the stage merge,
    resolve the base INSIDE the build (an alias stage) — never as a bare image name that
    buildx would pull from the registry (issue #1753, run 41971301136 @ 84e9684ca2)."""

    # Given every REAL derived engine Dockerfile that FROMs its backend toolchain base
    df_dir = REPO / "containers" / "engines" / "dockerfiles"
    checked = 0
    for df in sorted(df_dir.glob("*/Dockerfile.*")):
        backend = df.suffix[1:]
        if backend not in {"cpu", "cuda", "rocm", "vulkan"}:
            continue
        derived = df.read_text()
        tag = es.base_tag(backend)
        if f"FROM {tag}" not in derived:
            continue  # not a FROM<base> cell (e.g. an env-only variant); nothing to merge
        combined = ei._combine_base_stage(backend, derived, tag)
        checked += 1

        # When it is merged, the derived's cross-invocation base FROM is gone
        assert "FROM llgenie-base" in combined, f"{df.name}: derived FROM not aliased to llgenie-base"
        assert f"FROM {tag}" not in combined.replace("FROM llgenie-base", ""), \
            f"{df.name}: a bare {tag} FROM survives the merge — buildx would pull it from the registry"
        assert combined.count("AS llgenie-base") == 1, \
            f"{df.name}: the backend toolchain base must be aliased exactly once"
        assert not any("docker.io" in line for line in combined.splitlines()), \
            f"{df.name}: an raw docker.io ref leaked into the combined Dockerfile"
    assert checked >= 1, "no derived cell FROMs a backend base — this audit would pass vacuously"


def test_vllm_cuda_dockerfile_base_stage_is_hermetic():
    """vllm/cuda is a THIN prebuilt image over vLLM's official serving base — an external
    docker.io pull exempt from the internal base-stage merge (mirrors sglang/cuda +
    tensorrt-llm/cuda). It must NOT be aliased to the shared cuda base's internal stage."""
    derived = (REPO / "containers" / "engines" / "dockerfiles" / "vllm" / "Dockerfile.cuda").read_text()
    tag = es.base_tag("cuda")
    # exempt: it pulls vLLM's official CUDA serving image by name (prebuilt: true), never the
    # shared toolchain base, so the internal-stage merge must not be applied to it
    assert "FROM docker.io/vllm/vllm-openai:v0.33.0" in derived
    assert f"FROM {tag}" not in derived
    assert "AS llgenie-base" not in derived
    # and the prebuilt Dockerfile carries no shared-base alias and no source-build wrap
    assert "FROM llgenie-base" not in derived
    assert "engine_runner.py install" not in derived


def test_build_push_false_routes_from_base_cell_through_internal_stage(tmp_path, monkeypatch):
    """build() with push=false (the read-only verify cell, issue #1832) must route a `FROM <base>`
    cell through _combine_base_stage: the ONE Dockerfile written into the buildx ctx carries the
    internal `AS llgenie-base` stage and no bare base `FROM` / docker.io ref, so the cache-capable
    buildx driver never falls through to a denied registry pull."""
    repo, _ = _repo(tmp_path, {".gitkeep": ""})
    (repo / "containers" / "engines" / "base").mkdir(parents=True)
    (repo / "containers" / "engines" / "base" / "Dockerfile.cuda").write_text("FROM nvidia/cuda:13.0.2-devel-ubuntu24.04\n")
    (repo / "containers" / "engines" / "scripts").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "engine_runner.py").write_text("# runner\n")
    (repo / "containers" / "engines" / "entrypoint.sh").write_text("#!/bin/sh\n")

    _point(monkeypatch, repo)

    spec = {
        "id": "vllm", "backend": "cuda", "variant": "cuda", "tag": "llgenie/vllm:test",
        "dockerfile": "containers/engines/dockerfiles/vllm/Dockerfile.cuda",
        "params_file": "containers/engines/params/vllm.json",
    }
    (repo / "containers" / "engines" / "dockerfiles" / "vllm").mkdir(parents=True)
    (repo / "containers" / "engines" / "dockerfiles" / "vllm" / "Dockerfile.cuda").write_text(
        f"FROM {es.base_tag('cuda')}\nRUN echo build\n")
    params = json.dumps({
        "repo": "vllm/vllm", "pinned": "<sha>",
        "variants": {"cuda": {"image": "ubuntu", "build": ["echo"]}},
    })
    (repo / "containers" / "engines" / "params").mkdir(parents=True)
    (repo / "containers" / "engines" / "params" / "vllm.json").write_text(params)

    captured = {}

    def fake_buildx(tag, ctx, push, buildcache, force=False, **kw):
        captured["ctx"] = (Path(ctx) / "Dockerfile").read_text()
        captured["push"] = push
        return 0

    monkeypatch.setattr(ei, "_buildx", fake_buildx)
    monkeypatch.setattr(ei, "REGISTRY", "")

    assert ei.build(spec, force=True, push=False) == 0

    combined = captured["ctx"]
    assert captured["push"] is False
    assert "FROM llgenie-base" in combined
    assert f"FROM {es.base_tag('cuda')}" not in combined.replace("FROM llgenie-base", "")
    assert "docker.io" not in combined
    assert combined.count("AS llgenie-base") == 1


# ---------------------------------------------------------------------------
# the LONG build step streams its log (issue #2089) — never a captured buffer
# ---------------------------------------------------------------------------
class _FakeProc:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.stdout = None
        self.stderr = None


def _capture_build_step(monkeypatch, *, push: bool, rc: int = 0) -> dict:
    """Run `_buildx` with a recording `run_live` and a `_sh` that REFUSES to run a build.

    The refusal is the discrimination: if a build step is routed through the capturing `_sh`
    (as it was before the fix) the assertion fires instead of the test silently passing.
    """
    seen: dict = {}
    monkeypatch.setattr(ei, "_cache_exists", lambda ref: True)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent/llgenie")
    monkeypatch.setattr(ei, "CACHE_WRITE", False)

    def fake_live(cmd, **kw):
        seen.setdefault("live", []).append(list(cmd))
        return _FakeProc(rc)

    def fake_sh(cmd, **kw):
        assert "build" not in cmd, f"a build step was CAPTURED instead of streamed: {cmd}"
        return _FakeProc(0)

    monkeypatch.setattr(ei, "run_live", fake_live)
    monkeypatch.setattr(ei, "_sh", fake_sh)
    seen["rc"] = ei._buildx("llgenie/x:pinhash-arch", "/tmp/ctx2089", push, "ghcr.io/x:buildcache")
    return seen


def test_a_local_build_streams_its_log_through_run_live(monkeypatch):
    """`_buildx`'s local build step runs through `proc.run_live`, so buildx's own progress lands on
    the log as it is written — the difference between a diagnosable cold compile and a silent cell."""
    seen = _capture_build_step(monkeypatch, push=False)
    assert seen["rc"] == 0
    assert seen["live"], "the build step never reached run_live"
    cmd = seen["live"][0]
    assert cmd[:3] == [ei.RUNTIME, "buildx", "build"]
    assert "--progress=plain" in cmd
    assert "--load" in cmd


def test_a_push_build_streams_its_log_and_keeps_the_exit_code(monkeypatch):
    """The `--push` build step streams too, and its rc is still the caller's verdict (a failing
    compile reds the cell)."""
    seen = _capture_build_step(monkeypatch, push=True, rc=2)
    assert seen["rc"] == 2
    cmd = seen["live"][0]
    assert "--push" in cmd and "--progress=plain" in cmd
