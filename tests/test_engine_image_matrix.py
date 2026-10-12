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


def test_push_workflow_scopes_the_matrix():
    """A push compares against github.event.before, not the full matrix."""

    # Given the CI workflow
    text = (REPO / ".github" / "workflows" / "ci.yml").read_text()

    # When a push builds the engine matrix
    step = text.split("- id: m", 1)[1].split("engine-image:", 1)[0]

    # Then it scopes to the parent commit and keeps the full matrix only when
    # that sha is the all-zero sha of a brand new branch
    assert "CHANGED=$before" in step
    assert "github.event.before" in step
    assert "0000000000000000000000000000000000000000" in step
    assert "CHANGED=origin/${{ github.base_ref }}" in step


def test_every_changed_image_is_built_tested_and_published():
    """The row the matrix emits is the row CI builds, tests and pushes.

    A pull request and a push to main share one engine-image job. Its matrix
    comes from engine-matrix, so a tag that changed is built and published and
    a tag that did not is not — on both, not only on pull_request.
    """

    # Given the engine-image job
    text = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    job = text.split("engine-image:", 1)[1].split("engine-published-test:", 1)[0]

    # When CI runs a row
    # Then it builds, tests and publishes that exact engine and arch, and skips
    # the placeholder row that stands in for an unchanged tree
    assert "matrix: ${{ fromJSON(needs.engine-matrix.outputs.matrix) }}" in job
    assert "make build-engine ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}" in job
    assert "make test-engine-stage ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}" in job
    assert "make push-engine ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}" in job
    assert "if: ${{ matrix.engine != 'none' }}" in job
    assert "needs: [engine-matrix, engine-base, ci-images]" in job


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

    # Given the committed engines, and the make lines the engine-image job runs
    repo, sha = _real_build_inputs(tmp_path)
    job = (REPO / ".github" / "workflows" / "ci.yml").read_text().split("engine-image:", 1)[1]
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
        variants = [v for v in params["variants"] if v in ei.CI_VARIANTS and not ei.disabled(engine, v)]
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
