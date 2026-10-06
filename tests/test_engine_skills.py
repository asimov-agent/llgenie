"""Engine skills (issue #98): one SKILL.md per inference server.

Locks openspec/changes/feat-engine-skills/specs/engine-skills/spec.md. Hermetic:
hardware probes are replaced by fixed dicts or env seams. The registry check
runs against the pinned fixture tests/fixtures/trending-models.json, a copy of
trending-local-llms data/models.json.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

import scripts.engine_skills as es

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "trending-models.json"

ADA_16GB = {"os": "linux", "arch": "amd64", "machine": "x86_64", "backend": "cuda",
            "card_ram_bytes": 16 * 1024 ** 3, "compute_cap": "8.9", "cuda_arch": "89",
            "cuda_version": "13.3", "cuda_major": "13", "gpu_targets": "", "torch_backend": "auto", "jobs": "32"}
RTX3090 = {**ADA_16GB, "compute_cap": "8.6", "cuda_arch": "86"}
GPULESS_CI = {**ADA_16GB, "compute_cap": "", "cuda_arch": "", "cuda_version": "12.4", "cuda_major": "12"}
RDNA3 = {**ADA_16GB, "backend": "rocm", "compute_cap": "", "cuda_arch": "",
         "cuda_version": "", "cuda_major": "", "gpu_targets": "gfx1100"}
MAC = {**ADA_16GB, "os": "darwin", "arch": "arm64", "machine": "arm64", "backend": "metal",
       "compute_cap": "", "cuda_arch": "", "cuda_version": "", "cuda_major": ""}


@pytest.fixture(scope="module")
def skills():
    return es.load_skills()


def test_every_registry_engine_has_exactly_one_skill(skills):
    """Each engine in trending-local-llms engines{} maps to one skill."""

    # Given the pinned trending-local-llms registry
    registry = es.load_registry(str(FIXTURE))

    # When the skills are validated against it
    errors = es.validate(skills, registry)
    engines = [s["engine"] for s in skills.values()]

    # Then there are no errors and the mapping is one-to-one
    assert errors == []
    assert sorted(engines) == sorted(registry)
    assert len(set(engines)) == len(engines)


def test_validator_reports_a_registry_engine_without_a_skill(skills):
    """A new engine in the index is reported, not silently ignored."""

    # Given a registry with an engine no skill covers
    registry = {**es.load_registry(str(FIXTURE)), "BrandNewEngine": {"backend": "CUDA", "url": "x"}}

    # When the skills are validated
    errors = es.validate(skills, registry)

    # Then the missing skill is named
    assert any("BrandNewEngine" in e and "has no skill" in e for e in errors)


def test_front_matter_parser_matches_pyyaml_for_every_skill():
    """The stdlib parser reads each SKILL.md exactly like yaml.safe_load."""

    # Given every SKILL.md in skills/engines
    paths = sorted((REPO / "skills" / "engines").glob("*/SKILL.md"))
    assert len(paths) >= 16

    for path in paths:
        text = path.read_text()

        # When it is parsed by both parsers
        ours, _ = es.parse_front_matter(text)
        theirs = yaml.safe_load(text[4:text.index("\n---\n", 4)])

        # Then the result is identical
        assert ours == theirs, path


def test_parser_rejects_unquoted_dates():
    """YAML would turn 2026-10-05 into a date; the subset refuses it."""

    # Given front matter with an unquoted date
    text = "---\nverified: 2026-10-05\n---\nbody\n"

    # When it is parsed
    # Then it fails loudly
    with pytest.raises(ValueError, match="unquoted date"):
        es.parse_front_matter(text)


def test_cuda_arch_is_derived_from_compute_capability():
    """nvidia-smi compute_cap 8.9 becomes CMAKE_CUDA_ARCHITECTURES=89."""

    # Given compute capabilities reported by nvidia-smi
    caps = ["8.9", "8.6", "12.0", "7.5"]

    # When they are converted
    archs = [es.cuda_arch_from_compute_cap(c) for c in caps]

    # Then they are the CMake arch numbers
    assert archs == ["89", "86", "120", "75"]
    assert es.cuda_arch_from_compute_cap("") == ""


def test_llama_cpp_cuda_build_targets_the_detected_gpu(skills):
    """An Ada laptop builds for sm_89 only."""

    # Given the upstream llama.cpp skill and an RTX 4090 Laptop (8.9)
    skill = skills["llama.cpp"]

    # When the cuda cmake flags are rendered
    flags = es.cmake_flags(skill, "cuda", ADA_16GB)

    # Then the arch flag is derived and the deprecated LLAMA_CUBLAS is absent
    assert "-DGGML_CUDA=ON" in flags
    assert "-DCMAKE_CUDA_ARCHITECTURES=89" in flags
    assert "-DGGML_NATIVE=OFF" in flags
    assert "LLAMA_CUBLAS" not in flags


def test_gpuless_ci_cuda_build_omits_the_arch_flag(skills):
    """No visible GPU: CMake's default arch list is used."""

    # Given a CI container with nvcc but no GPU
    skill = skills["llama.cpp-prism"]

    # When the cuda cmake flags are rendered
    flags = es.cmake_flags(skill, "cuda", GPULESS_CI)

    # Then there is no CMAKE_CUDA_ARCHITECTURES flag
    assert "-DGGML_CUDA=ON" in flags
    assert "CMAKE_CUDA_ARCHITECTURES" not in flags


def test_rocm_build_uses_detected_gfx_target_and_hip_env(skills):
    """rocminfo gfx1100 becomes GPU_TARGETS=gfx1100 plus HIPCXX/HIP_PATH."""

    # Given the llama.cpp skill and an RDNA3 card
    skill = skills["llama.cpp"]

    # When the rocm plan is rendered
    plan = es.plan(skill, "rocm", RDNA3)

    # Then GGML_HIP and the detected target are in the configure step
    configure = next(s for s in plan["steps"] if s.startswith("cmake -S"))
    assert "-DGGML_HIP=ON" in configure
    assert "-DGPU_TARGETS=gfx1100" in configure
    assert "AMDGPU_TARGETS" not in configure
    assert plan["env"]["HIPCXX"] == "$(hipconfig -l)/clang"


def test_compute_capability_floor_blocks_unsupported_gpus(skills):
    """TensorFold needs sm_89: an RTX 3090 (8.6) is blocked with the reason."""

    # Given TensorFold and an RTX 3090
    skill = skills["tensorfold"]

    # When the install is checked
    blockers = es.check(skill, "cuda", RTX3090)

    # Then the compute capability is the stated blocker
    assert any("compute capability 8.6 < required 8.9" in b for b in blockers)


def test_cuda_toolkit_floor_blocks_old_toolkits(skills):
    """SGLang wheels need CUDA 13."""

    # Given SGLang and a CUDA 12.4 toolkit
    skill = skills["sglang"]

    # When the install is checked
    blockers = es.check(skill, "cuda", {**ADA_16GB, "cuda_version": "12.4"})

    # Then the toolkit version is the stated blocker
    assert any("CUDA toolkit 12.4 < required 13.0" in b for b in blockers)


def test_rocm_gfx_allow_list_blocks_unsupported_cards(skills):
    """exllamav3-rocm only supports RDNA3/3.5/4."""

    # Given the ROCm fork and an RDNA2 card
    skill = skills["exllamav3-rocm"]

    # When the install is checked
    blockers = es.check(skill, "rocm", {**RDNA3, "gpu_targets": "gfx1030"})

    # Then the gfx target is the stated blocker
    assert any("gfx1030 not in supported targets" in b for b in blockers)


def test_unsupported_backend_is_blocked(skills):
    """MLX-fast is Metal-only; TensorRT-LLM is not offered on a Mac."""

    # Given a Mac and the TensorRT-LLM skill
    skill = skills["tensorrt-llm"]

    # When the metal install is checked
    blockers = es.check(skill, "metal", MAC)

    # Then backend and OS are both reported
    assert any("backend metal not supported" in b for b in blockers)
    assert any("OS darwin not supported" in b for b in blockers)


def test_non_servable_engines_are_never_installed(skills):
    """WebLLM (browser-only) and the drafter/benchmark engines are not servers."""

    # Given the three non-server engines
    webllm, dflash, mlxfast = skills["webllm"], skills["dflash2"], skills["mlx-fast-bonsai2"]

    # When their serving status is read
    # Then WebLLM is false and the others point at host engines that have skills
    assert webllm["servable"] is False
    assert es.check(webllm, "cuda", ADA_16GB)
    assert dflash["servable"] == "via" and dflash["via"][0] == "sglang"
    assert mlxfast["servable"] == "via" and "tensorfold" in mlxfast["via"]
    for host in dflash["via"] + mlxfast["via"]:
        assert host in skills


def test_every_real_server_gets_a_container_image(skills):
    """A servable engine is an OpenAI server, so it gets an image on every backend that
    can run in a container. Opting one out (container: false) hides it from the trend
    list, which is how Strata was dropped. Only non-servers may have no image."""

    # Given every skill and the images generated from it
    for sid, skill in skills.items():
        params = es.PARAMS_DIR / f"{sid}.json"
        built = set(json.loads(params.read_text())["variants"]) if params.exists() else set()

        # When it is a real server on Linux
        # Then a generated image exists for each containerizable backend
        if skill.get("servable") is True and "linux" in (skill.get("os") or []):
            want = {b for b in skill.get("backends") or [] if b != "metal"}
            assert want <= built, (sid, sorted(want - built))
        else:
            assert skill.get("servable") in (False, "via"), sid


def test_every_servable_launch_exposes_llm_local_on_the_port(skills):
    """Whatever the engine, clients see 127.0.0.1:11434 and model llm-local."""

    for sid, skill in skills.items():
        if skill["servable"] is not True:
            continue
        backend = skill["backends"][0]

        # Given a servable skill rendered for its first backend
        plan = es.plan(skill, backend, {**ADA_16GB, "backend": backend})

        # When its launch, pre/post-launch and env are joined
        text = " ".join(str(x) for x in [plan["launch"], plan["pre_launch"], plan["post_launch"],
                                         *plan["env"].values()] if x)

        # Then the port is bound and the alias is exposed (or any name is accepted)
        assert "11434" in text, sid
        assert "llm-local" in text or skill["alias_mode"] == "any-name", sid
        assert "127.0.0.1" in text, sid


def test_engines_install_into_images_not_venvs(skills):
    """No skill creates a venv. Image backends install into the image's Python;
    Metal (no containers) uses `uv tool install`. No sudo, no curl|sh."""

    for sid, skill in skills.items():
        for backend in skill.get("backends") or []:
            steps = " ".join(str(x) for x in es._flatten(es._per_backend(skill.get("install"), backend)))

            # Given a skill's install steps for one backend
            # When they are scanned
            # Then there is no venv, sudo or pipe-to-shell, and pip targets the image or a uv tool.
            # A source build may make a python env inside the image (python3 -m venv),
            # which is not a host venv.
            assert "venv" not in steps or "python3 -m venv" in steps, (sid, backend)
            assert "sudo " not in steps, (sid, backend)
            assert not re.search(r"\|\s*(sudo\s+)?(sh|bash)\b", steps), (sid, backend)
            if "pip install" in steps:
                # uv targets the system python; source builds on rocm/pytorch use
                # that image's own interpreter (python3 -m pip), as upstream does;
                # a source build's own python env (python3 -m venv) installs into itself
                assert ("--system" in steps or "python3 -m pip install" in steps
                        or "python3 -m venv" in steps) and backend != "metal", (sid, backend)
                assert "uv pip install --system --break-system-packages --python" not in steps, (sid, backend)
            if backend == "metal" and "uv " in steps:
                assert "uv tool install" in steps, (sid, backend)


def test_native_install_is_refused_except_metal(skills, capsys):
    """Linux backends run from images; `engine-install` points at build-engine."""

    # Given vllm on cuda (an image backend) and mlx on metal
    # When a native install is attempted
    rc = es.install(skills["vllm"], "cuda", ADA_16GB, dry=True)
    err = capsys.readouterr().err

    # Then it is refused with the make command, while metal is allowed
    assert rc == 3
    assert "make build-engine ENGINE=vllm" in err
    assert es.native_allowed(skills["mlx"], "metal")
    assert not es.native_allowed(skills["llama.cpp"], "cpu")


def test_install_steps_are_idempotent(skills):
    """Re-running an install must not fail on what the first run created."""

    for sid, skill in skills.items():
        for step in es._flatten(skill.get("install")):
            step = str(step)

            # Given a step that creates a venv or clones a repo
            # When it is read
            # Then it is guarded so a second run skips it
            if "git clone" in step:
                assert step.startswith("test -d {src}/.git || "), (sid, step)


def test_env_prelude_lets_bash_expand_skill_env():
    """$(cmd) and $VAR in a skill env value are expanded by bash, not passed literally."""

    # Given an env with a command substitution and a variable
    prelude = es.env_prelude({"A": "$(echo expanded)", "B": "/x:$HOME"})

    # When bash evaluates the prelude
    out = subprocess.run(["bash", "-c", prelude + 'echo "$A|$B"'], capture_output=True,
                         text=True, check=True).stdout.strip()

    # Then both are expanded
    assert out == "expanded|/x:" + os.environ["HOME"]


def test_ollama_tarball_is_checksum_verified_before_extract(skills):
    """Ollama comes from the release tarball, checked against sha256sum.txt."""

    # Given the ollama skill on a CUDA host
    plan = es.plan(skills["ollama"], "cuda", ADA_16GB)
    steps = plan["steps"]

    # When the order of the steps is read
    check_i = next(i for i, s in enumerate(steps) if "sha256sum -c" in s)
    extract_i = next(i for i, s in enumerate(steps) if "tar -xf" in s)

    # Then the checksum runs before extraction, from the pinned release
    assert check_i < extract_i
    assert "releases/download/v0.35.1/ollama-linux-amd64.tar.zst" in " ".join(steps)
    assert "install.sh" not in " ".join(steps)


def test_mlx_cuda_extra_follows_detected_cuda_major(skills):
    """mlx[cuda13] on a CUDA 13 toolkit, mlx[cuda12] on CUDA 12."""

    # Given the MLX skill on two CUDA versions
    skill = skills["mlx"]

    # When the cuda installs are rendered
    s13 = " ".join(es.plan(skill, "cuda", ADA_16GB)["steps"])
    s12 = " ".join(es.plan(skill, "cuda", {**ADA_16GB, "cuda_version": "12.8", "cuda_major": "12"})["steps"])

    # Then the extra matches the toolkit
    assert "mlx[cuda13]" in s13
    assert "mlx[cuda12]" in s12


def test_detect_hardware_env_seams(monkeypatch):
    """CI forces the hardware via env; nothing is probed for those fields."""

    # Given the env seams for an RDNA3 box
    monkeypatch.setenv("LLAMA_BACKEND", "rocm")
    monkeypatch.setenv("LLAMA_RAM_BYTES", str(24 * 1024 ** 3))
    monkeypatch.setenv("LLGENIE_GPU_TARGETS", "gfx1100")
    monkeypatch.setenv("LLGENIE_CUDA_ARCH", "")
    monkeypatch.setenv("BUILD_JOBS", "6")

    # When the hardware is detected
    hw = es.detect_hardware()

    # Then the seams win
    assert hw["backend"] == "rocm"
    assert hw["gpu_targets"] == "gfx1100"
    assert hw["card_ram_bytes"] == 24 * 1024 ** 3
    assert hw["jobs"] == "6"


def test_native_build_reads_generated_params_not_skills():
    """build_llama_server.sh evals native_build_env.py, which reads params/<id>.json only."""

    # Given the build script and a forced CUDA arch
    script = (REPO / "scripts" / "build_llama_server.sh").read_text()
    env = {**os.environ, "SERVER_ROOT": "/srv", "LLGENIE_CUDA_ARCH": "89"}

    # When the native build env is rendered for prism + cuda
    out = subprocess.run(["python3", str(REPO / "scripts" / "native_build_env.py"),
                          "llama.cpp-prism", "cuda"],
                         capture_output=True, text=True, env=env, check=True).stdout

    # Then the script consumes it, no skill is read, and the values come from the params
    assert "native_build_env.py" in script and "engine_skills.py" not in script
    assert "skills/" not in (REPO / "scripts" / "native_build_env.py").read_text().split('"""', 2)[2]
    assert "github.com/ggerganov" not in script
    assert "REPO_URL=https://github.com/PrismML-Eng/llama.cpp.git" in out
    assert "BRANCH=prism" in out
    assert "TREE_DIR=/srv/prism-llama.cpp" in out
    assert "BUILD_DIR=/srv/prism-llama.cpp/build-cuda" in out
    assert "-DCMAKE_CUDA_ARCHITECTURES=89" in out


def test_build_path_works_without_skills(tmp_path):
    """Everything make build-engine / make install needs runs with skills/ deleted:
    the skills are used ONLY by make generate-engine-params."""

    import shutil as sh

    # Given a copy of the repo with the skills directory removed
    dst = tmp_path / "repo"
    sh.copytree(REPO, dst, ignore=sh.ignore_patterns(".git", "skills", "__pycache__", ".pytest_cache", ".ci-home"))
    assert not (dst / "skills").exists()

    # When the build-path tools run: native build env, detect_server, image tag/matrix
    def run(*cmd, **env):
        return subprocess.run(["python3", *cmd], cwd=dst, capture_output=True, text=True,
                              env={**os.environ, "LLAMA_BACKEND": "cpu", **env})
    native = run("scripts/native_build_env.py", "llama.cpp-prism", "cpu")
    detect = run("scripts/detect_server.py", "--json")
    tag = run("scripts/engine_image.py", "tag", "llama.cpp", "--variant", "cuda")
    matrix = run("scripts/engine_image.py", "matrix", "--ci", "--json")

    # Then all succeed from the generated files alone
    for r in (native, detect, tag, matrix):
        assert r.returncode == 0, r.stderr
    assert "BUILD_DIR=" in native.stdout
    assert "PrismML-Eng" in detect.stdout or "ggml-org" in detect.stdout
    assert tag.stdout.startswith("llgenie/llama-cpp:")
    assert json.loads(matrix.stdout)["include"]


def test_skill_pins_are_full_shas_and_watch_lists_exist(skills):
    """Drift sync (#100) needs a pinned sha and the files to diff."""

    for sid, skill in skills.items():
        # Given a skill
        # When its pin and watch list are read
        # Then the pin is a 40-hex sha and at least one upstream file is watched
        assert len(str(skill["pinned"])) == 40, sid
        assert skill["upstream_watch"], sid


def test_cli_validate_against_fixture_exits_zero():
    """`make skills-validate` runs this exact command."""

    # Given the pinned registry fixture
    cmd = ["python3", str(REPO / "scripts" / "engine_skills.py"), "validate", "--registry", str(FIXTURE)]

    # When the validator CLI runs
    r = subprocess.run(cmd, capture_output=True, text=True)

    # Then it reports 0 errors
    assert r.returncode == 0, r.stderr
    assert "0 error(s)" in r.stdout


def _ci():
    return yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())


def test_committed_engine_params_match_the_skills(skills):
    """make check-engine-params: the frozen params are exactly what the skills generate."""

    # Given the current skills and the committed params files
    # When the params are regenerated in check-only mode
    stale = es.write_params(skills, check_only=True)

    # Then nothing differs
    assert stale == [], f"run make generate-engine-params: {stale}"


def test_params_have_one_variant_per_backend(skills):
    """One image per engine x backend; GPU arch coverage is a fat build inside it."""

    # Given the generated params for a compiled engine and a wheel engine
    prism = es.generate_params(skills["llama.cpp-prism"])
    vllm = es.generate_params(skills["vllm"])

    # When their variant keys are read
    # Then there is exactly one per backend
    assert set(prism["variants"]) == {"cuda", "rocm", "vulkan", "cpu"}
    assert set(vllm["variants"]) == {"cuda", "rocm", "cpu"}


def test_frozen_variant_is_hardcoded_and_self_contained(skills):
    """A variant has fixed in-image paths, the pin and the fat arch flags (quoted for bash)."""

    # Given prism's cuda variant
    v = es.generate_params(skills["llama.cpp-prism"])["variants"]["cuda"]
    steps = " ".join(v["install"])

    # When it is inspected
    # Then every common GPU arch is compiled in one build, from the pinned sha, in-image paths
    assert "'-DCMAKE_CUDA_ARCHITECTURES=75;80;86;89;90;120'" in steps
    assert skills["llama.cpp-prism"]["pinned"] in steps
    assert "/opt/llgenie/src/prism-llama.cpp" in steps
    assert str(Path.home()) not in json.dumps(v)
    assert "{host}" in v["launch"] and "{port}" in v["launch"] and "llm-local" in v["launch"]
    assert v["run_args"] == ["--device", "nvidia.com/gpu=all", *es.SHM]  # host driver via CDI


def test_rocm_variant_compiles_all_common_gfx_targets(skills):
    """One rocm image covers RDNA2..RDNA4 + MI300 (quoted list survives bash)."""

    # Given the Prism fork's rocm variant (no official image, so it compiles)
    steps = " ".join(es.generate_params(skills["llama.cpp-prism"])["variants"]["rocm"]["install"])

    # When its configure step is read
    # Then the fat gfx list is one quoted argument
    assert "'-DGPU_TARGETS=gfx1030;gfx1100;gfx1101;gfx1102;gfx1151;gfx1200;gfx1201;gfx942'" in steps


def test_variant_is_the_backend(skills, capsys):
    """The image for a machine is its backend; a GPU outside the fat list is reported."""

    # Given prism's params
    params = es.generate_params(skills["llama.cpp-prism"])

    # When images are picked for an sm_89 card, an sm_61 card and an RDNA3 card
    # Then each gets its backend image, and sm_61 is flagged as not compiled in
    assert es.pick_variant(params, "cuda", ADA_16GB) == "cuda"
    assert es.pick_variant(params, "rocm", RDNA3) == "rocm"
    assert es.pick_variant(params, "cuda", {**ADA_16GB, "cuda_arch": "61"}) == "cuda"
    assert "this GPU is 61" in capsys.readouterr().err


def test_one_generated_dockerfile_per_engine_arch(skills):
    """generate-engine-params writes containers/engines/dockerfiles/<id>/Dockerfile.<arch>."""

    # Given the committed params
    for path in sorted(es.PARAMS_DIR.glob("*.json")):
        params = json.loads(path.read_text())
        for variant in params["variants"]:
            df = es.dockerfile_path(params["id"], variant)

            # When the variant's Dockerfile is read
            text = df.read_text()

            # Then it exists, matches the generator, exposes the API and uses the entrypoint
            assert text == es.render_dockerfile(params, variant), df
            assert "EXPOSE 11434" in text and 'ENTRYPOINT ["/opt/llgenie/app/entrypoint.sh"]' in text
            assert "skills/" not in text.split("\n", 2)[2], df  # only the header names the skill


def test_official_upstream_images_are_used_as_bases(skills):
    """Prefer the engine's own image: no rebuild of vLLM/Ollama/SGLang/TRT-LLM."""

    # Given the generated Dockerfiles
    df = lambda e, v: es.dockerfile_path(e, v).read_text()  # noqa: E731

    # When their FROM lines are read
    # Then the official image is the base and nothing is installed on top
    assert "FROM vllm/vllm-openai:v0.31.0" in df("vllm", "cuda")
    assert "FROM vllm/vllm-openai-cpu:v0.31.0" in df("vllm", "cpu")
    assert "FROM vllm/vllm-openai-rocm:v0.31.0" in df("vllm", "rocm")
    assert "FROM ollama/ollama:0.35.1-rocm" in df("ollama", "rocm")
    assert "FROM lmsysorg/sglang:v0.5.21" in df("sglang", "cuda")
    assert "FROM nvcr.io/nvidia/tensorrt-llm/release:1.2.1" in df("tensorrt-llm", "cuda")
    for b in ("cpu", "cuda", "rocm", "vulkan"):
        assert "FROM ghcr.io/ggml-org/llama.cpp:server" in df("llama.cpp", b) and "@sha256:" in df("llama.cpp", b)
        assert "engine_runner.py install" not in df("llama.cpp", b)
    assert "engine_runner.py install" not in df("vllm", "cpu")


def test_compiled_engines_build_on_the_shared_base_and_ship_slim(skills):
    """llama.cpp builds FROM the published shared toolchain base, ships on the runtime base."""

    # Given prism's cuda Dockerfile and the shared cuda base
    text = es.dockerfile_path("llama.cpp-prism", "cuda").read_text()
    base = (es.BASE_DIR / "Dockerfile.cuda").read_text()

    # When their stages are read
    # Then the build stage is the shared base (no per-engine apt layer), the run stage is slim
    assert f"FROM {es.base_tag('cuda')} AS build" in text
    assert "apt-get install" not in text.split("FROM nvidia/cuda:13.0.2-runtime-ubuntu24.04")[0]
    assert "FROM nvidia/cuda:13.0.2-runtime-ubuntu24.04" in text
    assert "COPY --from=build /opt/llgenie/src/prism-llama.cpp/build-cuda/bin" in text
    assert "FROM nvidia/cuda:13.0.2-devel-ubuntu24.04" in base and "build-essential" in base


def test_build_engine_uses_the_generated_dockerfile_only():
    """The image driver builds the generated Dockerfile; it never reads skills."""

    # Given the image driver and the entrypoint
    driver = (REPO / "scripts" / "engine_image.py").read_text()
    entry = (REPO / "containers" / "engines" / "entrypoint.sh").read_text()

    # When they are read
    # Then the build copies the generated Dockerfile + params, and serve uses the frozen params
    assert 'spec["dockerfile"]' in driver and "es.params_path" in driver
    assert "load_skills" not in driver and "get_skill" not in driver
    assert not (REPO / "containers" / "engines" / "Dockerfile").exists()
    assert "engine_runner.py serve params.json" in entry


def test_image_tag_changes_only_when_the_frozen_variant_changes(skills):
    """Same params -> same tag (no rebuild); a changed parameter -> new tag."""

    # Given prism's params
    params = es.generate_params(skills["llama.cpp-prism"])
    tag = es.image_spec(params, "cuda")["tag"]

    # When the same params are tagged again, and once with a changed launch flag
    again = es.image_spec(params, "cuda")["tag"]
    changed = json.loads(json.dumps(params))
    changed["variants"]["cuda"]["launch"] += " --flash-attn on"

    # Then only the changed variant gets a new tag, and the tag names the backend
    assert tag == again
    assert es.image_spec(changed, "cuda")["tag"] != tag
    assert tag.startswith("llgenie/llama-cpp-prism:2459f68b-") and tag.endswith("-cuda")


def test_runner_serves_from_a_frozen_plan(tmp_path):
    """engine_runner (the only llgenie code in an image) binds host/port/model at run time."""

    import scripts.engine_runner as runner

    # Given a frozen plan whose "server" is a tiny python HTTP server
    port = __import__("scripts.engine_smoke", fromlist=["free_port"]).free_port()
    plan = {"id": "fake", "backend": "cpu", "env": {"GREETING": "$(echo ok)"},
            "launch": "test \"$GREETING\" = ok && test {model} = /m && exec python3 -m http.server {port} --bind {host}",
            "health": "GET /", "pre_launch": None, "post_launch": None}

    # When the runner serves it and the server is stopped once ready
    import threading, signal as sig
    def stop_when_up():
        for _ in range(100):
            if runner.probe(port, "GET /"):
                os.kill(os.getpid(), sig.SIGTERM)
                return
            __import__("time").sleep(0.1)
    threading.Thread(target=stop_when_up, daemon=True).start()
    old = sig.getsignal(sig.SIGTERM)
    try:
        rc = runner.serve_plan(plan, "/m", "127.0.0.1", port, ready_timeout=20)
    finally:
        sig.signal(sig.SIGTERM, old)

    # Then env was shell-expanded, placeholders were bound, and it came up (stopped by SIGTERM)
    assert rc in (0, -15, 143)


def test_ci_builds_every_engine_arch_in_parallel_from_make(skills):
    """CI computes the job list from the params and runs make build-engine per job."""

    import scripts.engine_image as ei

    # Given the CI workflow and the generated matrix
    jobs = _ci()["jobs"]
    rows = ei.matrix(ci=True)

    # When the matrix and steps are read
    steps = " ".join(str(st.get("run", "")) for st in jobs["engine-image"]["steps"])
    mat_steps = " ".join(str(st.get("run", "")) for st in jobs["engine-matrix"]["steps"])

    # Then jobs come from `make list-engine-images CI=1 JSON=1`, build + push via make,
    # curl-test cpu images, and every engine x CI arch is present
    assert "make -s list-engine-images CI=1 JSON=1" in mat_steps
    assert "fromJSON(needs.engine-matrix.outputs.matrix)" in str(jobs["engine-image"]["strategy"]["matrix"])
    assert "make build-engine ENGINE=" in steps and "make push-engine ENGINE=" in steps
    # every push run publishes (feature branches too, #101); pull_request runs never do
    assert str(jobs["engine-image"]["env"]["PUBLISH"]) == "${{ github.event_name == 'push' && '1' || '' }}"
    assert "make test-engine ENGINE=" in steps
    assert {(r["engine"], r["variant"]) for r in rows} >= {
        ("llama.cpp-prism", "vulkan"), ("vllm", "cpu"), ("ollama", "rocm"),
        ("llama.cpp", "vulkan"), ("llama.cpp", "rocm")}
    # every params variant is a CI job except the disabled ones (issue #103)
    every = {(r["engine"], r["variant"]) for r in ei.matrix()}
    assert {(r["engine"], r["variant"]) for r in rows} == every - set(ei.DISABLED)
    assert len(rows) == len(every) - len(ei.DISABLED)
    assert all(r["smoke"] == (r["variant"] == "cpu" and r["engine"] not in ei.SMOKE_SKIP) for r in rows)
    assert jobs["engine-image"]["needs"] == ["engine-matrix", "engine-base"]
    base_steps = " ".join(str(st.get("run", "")) for st in jobs["engine-base"]["steps"])
    assert "make build-engine-base BACKEND=" in base_steps and "PUSH=$PUBLISH" in base_steps


def test_ci_checks_params_are_fresh():
    """The unit job fails when someone edits a skill without regenerating params."""

    # Given the CI unit job
    steps = " ".join(str(st.get("run", "")) for st in _ci()["jobs"]["unit"]["steps"])

    # When its steps are read
    # Then check-engine-params runs
    assert "make check-engine-params" in steps


def test_every_smoked_engine_has_a_tiny_test_model(skills):
    """engine_smoke.py can pick a tiny model for each engine CI runs."""

    import scripts.engine_smoke as smoke

    import scripts.engine_image as ei

    # Given every engine CI smokes (images + macOS native)
    engines = {r["engine"] for r in ei.matrix(ci=True) if r["smoke"]}
    engines |= set(_ci()["jobs"]["engine-smoke-mac"]["strategy"]["matrix"]["engine"])

    for engine in engines:
        # When a test-model format is picked from the skill's formats
        fmt = smoke.pick_format(skills[engine])

        # Then a tiny ungated model is defined for it
        assert fmt in smoke.TEST_MODELS, engine


def test_builds_use_a_registry_cache_and_reuse_published_images():
    """buildx --cache-from/--cache-to GHCR; a published tag is pulled, not rebuilt."""

    # Given the image driver
    driver = (REPO / "scripts" / "engine_image.py").read_text()

    # When its build path is read
    # Then it uses buildx with a registry cache and pulls an existing published tag first
    assert '"buildx", "build"' in driver
    assert "--cache-from" in driver and "--cache-to" in driver and "mode=max" in driver
    assert "def _available" in driver and '"pull"' in driver


def test_push_targets_only_the_registry_tag(monkeypatch):
    """With PUSH, buildx gets ONLY <registry>/<tag> (never a bare tag Docker Hub would receive)."""

    import scripts.engine_image as ei

    # Given a registry and a recorder instead of docker
    calls = []
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "_sh", lambda cmd, **kw: (calls.append(cmd), subprocess.CompletedProcess(cmd, 0))[1])

    # When a pushed build runs
    rc = ei._buildx("llgenie/base-cpu:abc", "/ctx", True, "ghcr.io/asimov-agent/llgenie/base-cpu:buildcache")

    # Then the build pushes only the qualified tag, with the registry cache in and out
    build = calls[0]
    tags = [build[i + 1] for i, a in enumerate(build) if a == "-t"]
    assert rc == 0
    assert tags == ["ghcr.io/asimov-agent/llgenie/base-cpu:abc"]
    assert "--push" in build and "--load" not in build
    assert any(a.startswith("type=registry,ref=ghcr.io/asimov-agent/llgenie/base-cpu:buildcache") for a in build)


def test_every_image_uses_an_official_or_shared_base(skills):
    """No Dockerfile starts from a bare distro with a per-engine toolchain: each is FROM the
    engine's official image, an upstream runtime (NGC/rocm-pytorch), or the shared llgenie base."""

    for path in sorted(es.DOCKERFILES_DIR.glob("*/Dockerfile.*")):
        # Given a generated Dockerfile
        first_from = next(l for l in path.read_text().splitlines() if l.startswith("FROM "))

        # When its first FROM is read
        # Then it is an official/upstream image or the shared base, never a bare distro
        assert not first_from.startswith(("FROM ubuntu", "FROM debian", "FROM nvidia/cuda", "FROM rocm/dev")), path


def test_per_engine_arch_make_targets_resolve_engine_and_arch():
    """make build-engine-<engine>-<arch> splits on the LAST dash (engine ids contain dashes/dots)."""

    for target, engine, arch in [("build-engine-vllm-cuda", "vllm", "cuda"),
                                 ("build-engine-llama.cpp-prism-rocm", "llama.cpp-prism", "rocm"),
                                 ("build-engine-llama.cpp-laurentzuijdwijk-vulkan", "llama.cpp-laurentzuijdwijk", "vulkan")]:
        # Given a per-engine x arch target
        # When make prints (dry-run) what it would do
        out = subprocess.run(["make", "-n", target], cwd=REPO, capture_output=True, text=True).stdout

        # Then it calls build-engine with the right engine and arch
        assert f"build-engine ENGINE={engine} ARCH={arch}" in out, (target, out)



def test_openai_sdk_harness_contract_pinned_in_dev_deps():
    """The served test asserts the OpenAI API with the SDK inside the containerized
    python test environment (llgenie/test:latest bundles openai + pytest), reached
    over host networking exactly as an AI harness tool would."""

    req_txt = (REPO / "tools" / "requirements-dev.txt").read_text()
    harness = (REPO / "scripts" / "tools" / "llgenie_harness.py").read_text()
    smoke = (REPO / "scripts" / "engine_smoke.py").read_text()

    # Given the dev lockfile, the harness client and the smoke driver
    # When they are read
    # Then openai is pinned, the endpoint check runs in llgenie/test:latest with
    #     --network host, and the served check asserts via the SDK
    assert next(l for l in req_txt.splitlines() if l.startswith("openai=="))
    assert "llgenie/test:latest" in smoke
    assert "--network", "host" in smoke.replace("\n", " ")
    assert "from openai import OpenAI" in harness
    assert "models.list" in harness and "chat.completions.create" in harness
    assert "client.models.list()" in harness  # /v1/models via the client
    assert smoke.count("harness_sdk_check") >= 1


def test_ggml_official_base_sets_ld_library_path_for_impl_libs():
    """The ggml-org server image's llama-server rpaths $ORIGIN=/app, but llgenie moves
    WORKDIR to /opt/llgenie/app; the CPU CI smoke run failed with
    'libllama-server-impl.so: cannot open shared object'. ENV LD_LIBRARY_PATH=/app on
    the ggml-based images fixes it; no other engine gets it."""

    # Given the generated Dockerfiles
    # When their final ENV blocks are read
    # Then the ggml-org llama.cpp variants carry LD_LIBRARY_PATH=/app
    for b in ("cpu", "cuda", "rocm", "vulkan"):
        df = es.dockerfile_path("llama.cpp", b).read_text()
        assert "FROM ghcr.io/ggml-org/llama.cpp:server" in df
        assert "LD_LIBRARY_PATH=/app" in df, b

    # And no other engine's image carries it (their binaries link normal /usr/lib)
    for eid in ("ollama", "vllm", "sglang", "tensorrt-llm"):
        for b in ("cpu", "cuda", "rocm", "vulkan"):
            p = es.dockerfile_path(eid, b)
            if p.exists():
                assert "LD_LIBRARY_PATH=/app" not in p.read_text(), (eid, b)


def test_post_build_test_stage_runs_engine_version_alias():
    """Every engine image has a post-build pytest stage (tests/test_engine_runs.py):
    cpu images serve and must answer 'hi' on the OpenAI endpoint; GPU images must at
    least report the engine version. entrypoint.sh exposes `version` (= detect)."""

    ep = (REPO / "containers" / "engines" / "entrypoint.sh").read_text()
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    tr = (REPO / "tests" / "test_engine_runs.py").read_text()

    # Given the entrypoint, the workflow test stage and the python test file
    # When they are read
    # Then the version alias exists, the CI test stage runs the python file, and it asserts both contracts
    assert "  version)" in ep and "alias of detect" in ep
    assert "pytest tests/test_engine_runs.py in llgenie/test (endpoint" in ci
    assert "pytest tests/test_engine_version.py (engine binary reports its version" in ci
    assert "def test_engine_cpu_image_answers_hi(" in tr
    assert "def test_engine_binary_reports_a_version(" in (REPO / "tests" / "test_engine_version.py").read_text()
    assert "test-engine-image" in open(REPO / "Makefile").read()
    assert "engine_runner.py detect params.json" in ep



def test_install_writes_container_start_scripts(tmp_path, monkeypatch):
    """make install writes one start script per engine image (+ the llama-server shim);
    make test-built-engine runs each with --version."""

    import importlib
    import scripts.install_engine_launchers as il
    importlib.reload(il)

    # Given images that are "available" (no docker needed for writing the scripts)
    monkeypatch.setattr(il.ei, "_available", lambda tag: True)
    monkeypatch.setattr(il, "detected_arch", lambda: "cpu")

    # When the launchers are installed into a temp bin dir for a cpu host (default = core)
    rc = il.install(tmp_path, "cpu", build=False)

    # Then only the llama.cpp core gets a start script (other engines on first use)
    names = sorted(p.name for p in tmp_path.glob("llgenie-engine-*"))
    assert rc == 0
    assert names == ["llgenie-engine-llama-cpp", "llgenie-engine-llama-cpp-prism"]
    # And ENGINES=all writes one per engine with a cpu image
    assert il.install(tmp_path, "cpu", build=False, only=["all"]) == 0
    assert {"llgenie-engine-vllm", "llgenie-engine-ollama"} <= {p.name for p in tmp_path.glob("llgenie-engine-*")}
    for p in tmp_path.glob("llgenie-engine-*"):
        body = p.read_text()
        assert p.stat().st_mode & 0o111 and " run --rm " in body and '"$IMAGE" version' in body
    # And llama-server runs the stock llama.cpp image, prism-server the Prism image,
    # each with that image's own llama-server path (not a host binary)
    stock = (tmp_path / "llama-server").read_text()
    prism = (tmp_path / "prism-server").read_text()
    assert f"--entrypoint {il.server_binary('llama.cpp', 'cpu')} " in stock and "llgenie/llama-cpp:" in stock
    assert f"--entrypoint {il.server_binary('llama.cpp-prism', 'cpu')} " in prism
    assert "llgenie/llama-cpp-prism:" in prism
    assert 'name="llgenie-prism-server-$port"' in prism and 'name="llgenie-llama-server-$port"' in stock
    # And make test-built-engine drives the --version check
    mk = (REPO / "Makefile").read_text()
    assert "install: venv-install engine-launchers link test-built-engine smoke" in mk
    assert "install_engine_launchers.py --bin \"$(BIN)\" --test" in mk



def test_cuda_containers_get_the_host_driver_via_cdi(tmp_path, monkeypatch):
    """cuda images never ship a driver: make run-engine and every start script pass
    the nvidia-container-toolkit CDI device, which mounts the host libcuda/nvidia-smi."""

    import importlib
    import scripts.install_engine_launchers as il
    importlib.reload(il)

    # Given the frozen cuda variant and a cuda install
    v = es.generate_params(es.load_skills()["llama.cpp"])["variants"]["cuda"]
    monkeypatch.setattr(il.ei, "_available", lambda tag: True)
    monkeypatch.setattr(il, "cuda_cdi_ready", lambda: False)
    assert il.install(tmp_path, "cuda", build=False, only=["llama.cpp"]) == 1  # loud without the toolkit
    monkeypatch.setattr(il, "cuda_cdi_ready", lambda: True)
    assert il.install(tmp_path, "cuda", build=False, only=["llama.cpp"]) == 0

    # When the run args, start script and llama-server shim are read
    script = (tmp_path / "llgenie-engine-llama-cpp").read_text()
    shim = (tmp_path / "llama-server").read_text()

    # Then all three request the CDI GPU device, never a baked-in driver
    assert v["run_args"] == ["--device", "nvidia.com/gpu=all", *es.SHM]
    assert "--device nvidia.com/gpu=all" in script and "--device nvidia.com/gpu=all" in shim
    assert "libcuda" not in (REPO / es.dockerfile_path("llama.cpp", "cuda")).read_text()



def test_published_images_are_tested_again_as_a_separate_matrix_stage():
    """Issue #102: after build -> test -> push, a separate matrix job pulls every image
    from GHCR (no build, digest check) and runs the same tests + the install path."""

    import yaml

    # Given the CI workflow and the Makefile
    jobs = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())["jobs"]
    pub = jobs["engine-published-test"]
    steps = " ".join(st.get("run", "") for st in pub["steps"])
    build = jobs["engine-image"]
    order = [st.get("run", "") for st in build["steps"] if st.get("run")]
    mk = (REPO / "Makefile").read_text()

    # When the published stage and the build job are read
    # Then the build job tests before it pushes
    i_test = next(i for i, r in enumerate(order) if "make test-engine" in r)
    i_push = next(i for i, r in enumerate(order) if "make push-engine" in r)
    assert i_test < i_push
    # And the published stage runs after it, on every push run, over the same matrix
    assert set(pub["needs"]) == {"engine-matrix", "engine-image"}
    assert "github.event_name == 'push'" in pub["if"] and "!cancelled()" in pub["if"]
    assert pub["name"] == "test-published-${{ matrix.engine }}-${{ matrix.variant }}"
    assert pub["strategy"]["matrix"] == build["strategy"]["matrix"]
    assert pub["permissions"]["packages"] == "read"
    # And it never builds: it pulls, re-tests, installs from the registry only
    assert "make build-engine" not in steps and "make push-engine" not in steps
    assert "make test-published-engine ENGINE=" in steps
    assert "make engine-launchers" in steps and "BUILD=1" not in steps and "make test-built-engine" in steps
    assert "pull-published" in mk[mk.index("test-published-engine:"):mk.index("push-engine:")]


def test_pull_published_refuses_a_local_build_and_a_digest_mismatch(monkeypatch):
    """pull-published removes any local copy, pulls the pinned tag and requires the
    same digest as the moving :<arch> tag."""

    import importlib
    import scripts.engine_image as ei
    importlib.reload(ei)

    calls = []

    class R:
        def __init__(self, rc=0, out=""):
            self.returncode, self.stdout = rc, out

    def fake_sh(cmd, **kw):
        calls.append(cmd)
        if cmd[1:3] == ["buildx", "imagetools"]:
            return R(0, '"sha256:aaa"' if ":cpu" not in cmd[4] or digest["same"] else '"sha256:bbb"')
        return R(0)

    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "_sh", fake_sh)
    spec = {"tag": "llgenie/llama-cpp:8f9ae20c-abc-cpu", "variant": "cpu"}

    # Given matching digests
    digest = {"same": True}
    # When the image is pulled as published
    out = ei.pull_published(spec)
    # Then the local copy was removed first, the registry tag pulled, and it passes
    assert out == spec["tag"]
    assert calls[0][:2] == [ei.RUNTIME, "rmi"]
    assert [ei.RUNTIME, "pull", "ghcr.io/asimov-agent/" + spec["tag"]] in calls

    # Given the :cpu tag points elsewhere
    digest["same"] = False
    calls.clear()
    # Then the pull is refused
    assert ei.pull_published(spec) == ""

    # Given no registry
    monkeypatch.setattr(ei, "REGISTRY", "")
    # Then there is nothing to test
    assert ei.pull_published(spec) == ""



def test_digest_reads_the_live_registry_and_retries_a_failed_lookup(capsys):
    """Live GHCR, no mocks: the published llama.cpp cpu image's pinned tag and its
    moving :cpu tag resolve to the same digest; a missing tag is retried, then "".
    (A transient GHCR lookup failure once failed test-published-freetoken-rocm.)"""
    import importlib
    import scripts.engine_image as ei
    importlib.reload(ei)
    reg = "ghcr.io/asimov-agent"
    # Given the published llama.cpp cpu image
    tag = ei.resolve("llama.cpp", None, "cpu")["tag"]
    # When both refs are looked up
    d_pinned = ei._digest(f"{reg}/{tag}")
    d_arch = ei._digest(f"{reg}/{tag.split(':')[0]}:cpu")
    # Then both are the same sha256 digest
    assert d_pinned.startswith("sha256:") and d_pinned == d_arch
    # And a tag that does not exist is retried and gives ""
    assert ei._digest(f"{reg}/llgenie/llama-cpp:llgenie-no-such-tag", attempts=2) == ""
    assert "retrying" in capsys.readouterr().out


def test_native_plan_binds_skill_env_to_the_requested_port(skills):
    """macOS ollama smoke hung 600 s: OLLAMA_HOST rendered with the default port while
    the smoke polled a free port. The plan's env must use the run's host/port."""

    # Given the ollama skill and a smoke run on port 49200
    hw = {**es.detect_hardware(), "backend": "metal", "os": "darwin"}
    p = es.plan(skills["ollama"], "metal", hw, extra={"port": 49200})

    # When its env is rendered
    # Then OLLAMA_HOST points at that port, in the env and the bash prelude
    assert p["env"]["OLLAMA_HOST"].endswith(":49200")
    assert 'OLLAMA_HOST="127.0.0.1:49200"' in p["env_prelude"]


def test_native_smoke_runs_the_endpoint_test_without_docker():
    """macOS (Metal) has no docker on the runner: the native smoke runs the same
    pytest endpoint file with uv and the pinned dev deps, not in the test image."""

    src = (REPO / "scripts" / "engine_smoke.py").read_text()

    # Given the smoke driver
    # When its two harness calls are read
    # Then the image smoke uses the test container and the native smoke does not
    assert "harness_sdk_check(port, engine=spec[\"id\"], arch=spec[\"variant\"])" in src
    assert "harness_sdk_check(port, engine=skill_id, arch=backend, container=False)" in src
    assert '"uv", "run", "--no-project"' in src and "tests/test_engine_runs.py" in src
    assert '"--with-requirements", str(root / "tools" / "requirements-dev.txt")' in src


def test_post_build_tests_run_in_the_test_image_not_on_the_bare_runner():
    """#98 CI regression: runners have no pytest and no llgenie/test image.
    The engine-image job builds llgenie/test before its post-build stage, and
    test-engine-image runs pytest inside it (host docker socket), not via host python."""
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    job = ci.split("\n  engine-image:\n", 1)[1].split("\n  engine-published-test:\n", 1)[0]
    assert job.index("run: make test-image") < job.index("post-build test:")
    mk = (REPO / "Makefile").read_text()
    recipe = mk.split("\ntest-engine-image:", 1)[1].split("\n\n", 1)[0].split("\ntest-", 1)[0]
    assert "$(ENGINE_TEST_ARGS)" in recipe and "$(TEST_IMG)" in recipe
    assert "$(PY) -m pytest" not in recipe


def test_any_name_engines_are_not_required_to_list_llm_local():
    """mlx_lm.server has no alias flag (alias_mode any-name): the endpoint test
    gets the skill's alias_mode and only requires a listed model + an answer
    to model=llm-local."""
    smoke = (REPO / "scripts" / "engine_smoke.py").read_text()
    assert '"LLGENIE_TEST_ALIAS_MODE": alias_mode' in smoke
    runs = (REPO / "tests" / "test_engine_runs.py").read_text()
    assert 'LLGENIE_TEST_ALIAS_MODE") == "any-name"' in runs
    assert 'model="llm-local"' in runs


def test_top_tier_serve_ci_model_dir_is_visible_to_the_engine_container():
    """The llama-server shim runs the engine image through the HOST docker and
    mounts the model's dir; pytest's /tmp inside the test container does not
    exist on the host, so the model must live under the repo-mounted CI home."""
    mk = (REPO / "Makefile").read_text()
    line = next(l for l in mk.splitlines() if "tests/test_top_tier_serve.py" in l and "ENGINE_TEST_RUN" in l)
    assert "--basetemp=$$HOME/" in line


def test_mlx_cpu_image_smoke_uses_an_unquantized_model():
    """MLX CPU is minutes per token on 4-bit weights (CI #98 timed out), so the
    cpu image smoke picks the bf16 model; Metal keeps the 4-bit one. The mlx
    launch symlinks llm-local -> model so model=llm-local is not looked up on HF."""
    import scripts.engine_smoke as sm
    assert sm.TEST_MODELS["mlx-safetensors-cpu"][0].endswith("-bf16")
    assert sm.TEST_MODELS["mlx-safetensors"][0].endswith("-4bit")
    src = (REPO / "scripts" / "engine_smoke.py").read_text()
    assert "f\"{fmt}-{spec['backend']}\"" in src
    launch = es.get_skill("mlx")["launch"]
    assert "ln -sfn {model} llm-local" in launch and "--model llm-local" in launch


def test_every_published_image_is_started_and_answers_hi():
    """After publishing, each image (GPU ones too, without GPU devices on the
    GPU-less runner) is pulled, its binary version checked, and the running
    container must answer "hi" on the OpenAI chat endpoint."""
    mk = (REPO / "Makefile").read_text()
    recipe = mk[mk.index("test-published-engine:"):mk.index("push-engine:")]
    assert "pull-published" in recipe
    assert "$(MAKE) test-engine-image" in recipe
    assert "engine_smoke.py" in recipe and "--image" in recipe
    assert "$(if $(filter cpu,$(ARCH)),,--no-gpu)" in recipe
    assert 'ei.chat_testable("$(ENGINE)", "$(ARCH)")' in recipe
    smoke = (REPO / "scripts" / "engine_smoke.py").read_text()
    assert 'spec = {**spec, "run_args": list(es.SHM)}' in smoke
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    job = ci.split("\n  engine-published-test:\n", 1)[1].split("\n  # ----", 1)[0]
    assert "make test-published-engine ENGINE=" in job
    assert "if: matrix.test" not in job  # no GPU image skips the chat test


def test_llama_server_shim_uses_the_images_real_binary_path():
    """CI #98 install: Prism images have llama-server under build-<arch>/bin, not
    /app (ggml-org images): the shim takes the path from the frozen launch line."""
    import scripts.install_engine_launchers as il
    prism = il.server_binary("llama.cpp-prism", "cpu")
    assert prism.endswith("/build-cpu/bin/llama-server") and not prism.startswith("/app/")
    assert il.server_binary("llama.cpp", "cpu") == "/app/llama-server"
    shim = il.llama_server_shim("t", "cpu", prism)
    assert f"--entrypoint {prism} " in shim
    assert f"LD_LIBRARY_PATH={prism.rsplit('/', 1)[0]} " in shim


def test_vllm_cpu_does_not_reserve_90_percent_of_ram_and_gets_shm():
    """CI #98 vllm/cpu: --gpu-memory-utilization is a RAM share on CPU (0.90 refused
    to start) and docker's 64 MiB /dev/shm is too small for vLLM's buffers."""
    v = json.loads((REPO / "containers/engines/params/vllm.json").read_text())["variants"]
    assert "--gpu-memory-utilization" not in v["cpu"]["launch"]
    assert v["cpu"]["env"].get("VLLM_CPU_KVCACHE_SPACE")
    assert "--gpu-memory-utilization 0.90" in v["cuda"]["launch"]
    for b in ("cpu", "cuda", "vulkan"):
        assert "--shm-size" in es.RUN_ARGS[b]


def test_rocm_source_builds_pin_a_base_their_build_accepts():
    """CI #98: exllamav3 needs ROCm >= 7.2.4 (the shared 7.0 base fails), sglang's
    setup_rocm.py hard-codes c++17 (rocm/pytorch:latest needs c++20 headers),
    FreeToken's ROCm build exists only after v0.1.3."""
    p = lambda e: json.loads((REPO / f"containers/engines/params/{e}.json").read_text())["variants"]["rocm"]  # noqa: E731
    base = "rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:"
    assert p("exllamav3-rocm")["base"].startswith(base)
    assert p("sglang")["base"].startswith(base)
    ft = p("freetoken")
    assert ft["base"].startswith(base)
    assert not any("git clone -b v" in s for s in ft["install"])
    assert any("whl/rocm7.2" in s and "torch==2.11" in s for s in ft["install"])
    assert all(":latest" not in p(e)["base"] for e in ("exllamav3-rocm", "sglang", "freetoken"))


def test_published_stage_pulls_with_the_run_token():
    """A first-time GHCR package can be private: engine-published-test logs in with the
    run's read token before pulling, and every published image is chatted with."""
    import yaml as _y
    job = _y.safe_load((REPO / ".github/workflows/ci.yml").read_text())["jobs"]["engine-published-test"]
    runs = [st.get("run", "") for st in job["steps"]]
    i_login = next(i for i, r in enumerate(runs) if "docker login ghcr.io" in r)
    i_pull = next(i for i, r in enumerate(runs) if "make test-published-engine" in r)
    assert i_login < i_pull and job["permissions"]["packages"] == "read"


@pytest.mark.parametrize("arch, want", [
    ("cpu", {"llama.cpp": "cpu", "llama.cpp-prism": "cpu", "vllm": "cpu", "sglang": None}),
    # Prism cuda/rocm and exllamav3 rocm are disabled (issue #103): cpu fallback / skipped
    ("cuda", {"llama.cpp": "cuda", "llama.cpp-prism": "cpu", "vllm": "cuda", "exllamav3-rocm": None,
              "llama.cpp-laurentzuijdwijk": "cpu"}),
    ("rocm", {"llama.cpp": "rocm", "llama.cpp-prism": "cpu", "exllamav3-rocm": None, "mlx": "cpu",
              "llama.cpp-laurentzuijdwijk": "rocm"}),
    ("vulkan", {"llama.cpp": "vulkan", "llama.cpp-prism": "vulkan", "vllm": "cpu", "sglang": None}),
])
def test_install_pulls_only_the_images_for_this_backend(tmp_path, monkeypatch, arch, want):
    """make install pulls (never builds by default) exactly the image variant that
    matches the detected backend; an engine without one falls back to cpu or is skipped."""
    import importlib
    import scripts.install_engine_launchers as il
    importlib.reload(il)
    asked, built = [], []
    monkeypatch.setattr(il.ei, "_available", lambda tag: asked.append(tag) or True)
    monkeypatch.setattr(il.ei, "build", lambda spec, *a, **k: built.append(spec["tag"]) or 0)
    monkeypatch.setenv("LLGENIE_NO_GPU", "1")  # no CDI check on the test host
    for engine, variant in want.items():
        assert il.variant_for(engine, arch) == variant, (engine, arch)
    assert il.install(tmp_path, arch, build=False, only=["all"]) == 0
    assert not built
    for engine in ("llama.cpp", "llama.cpp-prism"):
        assert il.ei.resolve(engine, None, il.variant_for(engine, arch))["tag"] in asked
    assert all(t.endswith(tuple(f"-{v}" for v in (arch, "cpu"))) for t in asked)
    # a disabled image (issue #103) is never pulled
    assert not any(il.ei.resolve(e, None, v)["tag"] in asked for e, v in il.ei.DISABLED)


def test_install_fails_loudly_when_an_image_is_not_published(tmp_path, monkeypatch):
    """Default install never builds: an unpublished image is a hard failure."""
    import importlib
    import scripts.install_engine_launchers as il
    importlib.reload(il)
    monkeypatch.setattr(il.ei, "_available", lambda tag: False)
    monkeypatch.setattr(il.ei, "build", lambda *a, **k: (_ for _ in ()).throw(AssertionError("built")))
    assert il.install(tmp_path, "cpu", build=False) == 1


def test_ensure_pulls_one_engine_on_first_use(tmp_path, monkeypatch):
    """llgenie --pick/--engine: --ensure pulls only the picked engine for this backend."""
    import importlib
    import scripts.install_engine_launchers as il
    importlib.reload(il)
    asked = []
    monkeypatch.setattr(il.ei, "_available", lambda tag: asked.append(tag) or True)
    monkeypatch.setattr(il.ei, "image_exists", lambda tag: False)
    assert il.ensure(tmp_path, "vllm", "cpu", build=False) == 0
    assert [p.name for p in tmp_path.glob("llgenie-engine-*")] == ["llgenie-engine-vllm"]
    assert asked == [il.ei.resolve("vllm", None, "cpu")["tag"]]
    src = (REPO / "scripts" / "llama_serve.py").read_text()
    assert '"--ensure", eng["id"], "--arch", eng["variant"]' in src


def test_make_install_defaults_pull_from_the_published_registry():
    mk = (REPO / "Makefile").read_text()
    assert "export LLGENIE_REGISTRY ?= ghcr.io/asimov-agent" in mk
    recipe = mk.split("\nengine-launchers:", 1)[1].split("\n\n", 1)[0]
    assert "$(if $(BUILD),--build,)" in recipe and "--no-build" not in recipe


def test_gpu_scripts_can_run_on_cpu_for_tests():
    """LLGENIE_NO_GPU=1 drops the GPU device flags (the GPU image runs on CPU)."""
    import importlib
    import scripts.install_engine_launchers as il
    importlib.reload(il)
    for body in (il.launcher("ollama", "cuda", "t", "/m"), il.llama_server_shim("t", "rocm")):
        assert '[ -n "${LLGENIE_NO_GPU:-}" ] && gpu=(' in body and '"${gpu[@]}"' in body


def test_install_published_is_the_last_stage_per_mocked_backend():
    """make install is tested LAST, against the published images, per backend
    (cpu/cuda/rocm/vulkan mocked via LLAMA_BACKEND), after engine-published-test."""
    import yaml as _y
    jobs = _y.safe_load((REPO / ".github/workflows/ci.yml").read_text())["jobs"]
    job = jobs["install-published"]
    assert job["needs"] == ["engine-published-test"]
    assert "github.event_name == 'push'" in job["if"] and "!cancelled()" in job["if"]
    assert job["strategy"]["matrix"]["backend"] == ["cpu", "cuda", "rocm", "vulkan"]
    runs = [st.get("run", "") for st in job["steps"]]
    assert any("docker login ghcr.io" in r for r in runs)
    assert any("make test-install-published BACKEND=${{ matrix.backend }}" in r for r in runs)
    assert not any("make build-engine" in r or "BUILD=1" in r for r in runs)
    mk = (REPO / "Makefile").read_text()
    recipe = mk.split("\ntest-install-published:", 1)[1].split("\n\n", 1)[0]
    assert "-e LLAMA_BACKEND=$(BACKEND) -e LLGENIE_NO_GPU=1" in recipe
    assert "tests/test_install_published.py" in recipe
    t = (REPO / "tests" / "test_install_published.py").read_text()
    for needle in ('"(pull published images only)"', '"[engine-image] built" not in', '"--pick", "--auto", "--engine"',
                   '_make("uninstall")', '("prism", "prism-server", "llama.cpp-prism")'):
        assert needle in t, needle


def test_pre_publish_jobs_build_and_the_pull_only_install_runs_last():
    """install/cpu-health/top-tier run in PR runs too (read-only token, nothing
    published yet): they build the image (BUILD=1 / --build). The pull-only
    `make install` is proven later by install-published, against published images."""
    mk = (REPO / "Makefile").read_text()
    for target in ("test-install-ci:", "test-top-tier-serve-ci:", "test-health:"):
        recipe = mk.split("\n" + target, 1)[1].split("\n\n", 1)[0]
        assert "make install BUILD=1" in recipe or "--build --engines" in recipe, target
    recipe = mk.split("\ntest-install-published:", 1)[1].split("\n\n", 1)[0]
    assert "BUILD" not in recipe and "--build" not in recipe


def test_published_install_step_runs_gpu_images_on_cpu():
    """CI run 37407553595: the registry-only install of a cuda image failed on the
    GPU-less runner (no CDI spec); that step sets LLGENIE_NO_GPU=1."""
    import yaml as _y
    job = _y.safe_load((REPO / ".github/workflows/ci.yml").read_text())["jobs"]["engine-published-test"]
    step = next(st for st in job["steps"] if "make engine-launchers" in st.get("run", ""))
    assert step["env"]["LLGENIE_NO_GPU"] == "1"


def test_only_engines_with_a_cpu_fallback_are_chat_tested_on_gpu_images():
    """CI run 37407553595: vLLM/SGLang/TensorRT-LLM/FreeToken/mlx-cuda/TensorFold GPU
    images refuse to start without a GPU; llama.cpp-family and Ollama fall back to CPU."""
    import scripts.engine_image as ei
    assert ei.chat_testable("llama.cpp", "cuda") and ei.chat_testable("ollama", "rocm")
    assert ei.chat_testable("llama.cpp-prism", "vulkan")
    for e, v in (("vllm", "rocm"), ("sglang", "cuda"), ("tensorrt-llm", "cuda"), ("freetoken", "rocm"),
                 ("mlx", "cuda"), ("tensorfold", "cuda")):
        assert not ei.chat_testable(e, v), (e, v)
    assert ei.chat_testable("vllm", "cpu") and ei.chat_testable("mlx", "cpu")
