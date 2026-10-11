"""make install on an Apple-Silicon Mac with Docker (Colima) (issue #112).

Locks openspec/changes/fix-macos-make-install/specs/macos-install/spec.md.
Hermetic (make test-unit): no docker, no network. The container runtime is
replaced by a fake `docker` executable on PATH, and the `--version`
outputs are the exact shapes the runtimes print in front of / after the engine's
version line (recorded on the Mac host and on Linux CI).
"""
from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import scripts.engine_image as ei  # noqa: E402
import scripts.install_engine_launchers as il  # noqa: E402

LLAMA = "[engine-runner] llama.cpp/cpu: installed version: 0.5.0-dev (build 11382, commit 11fe02151)"
PRISM = "[engine-runner] llama.cpp-prism/cpu: installed version: 0.2.0-dev (build 10754, commit 2459f68b5)"
DOCKER_PLATFORM_WARN = ("WARNING: The requested image's platform (linux/amd64) does not match the "
                        "detected host platform (linux/arm64/v8) and no specific platform was requested")
NERDCTL_CLEANUP_WARN = ('time="2026-10-07T19:56:10+02:00" level=warning msg="force cleanup timed out for '
                        'container b821f2f12d14, but cleanup may continue in background"')
NERDCTL_FATAL = 'time="2026-10-07T19:56:27+02:00" level=fatal msg="exit status 1"'
PRISM_SIGILL = "[engine-runner] llama.cpp-prism/cpu: missing (detect exited -4)"


# ---------------------------------------------------------------------------
# the --version check: every output shape the runtimes produce
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("case, rc, stdout, stderr, ok, reported", [
    # Linux docker: the version is the only line
    pytest.param("linux-docker-clean", 0, LLAMA + "\n", "", True, LLAMA, id="linux-docker-clean"),
    # docker on an arm64 Mac without --platform: the warning comes FIRST on stderr
    pytest.param("mac-docker-platform-warning", 0, LLAMA + "\n", DOCKER_PLATFORM_WARN + "\n", True, LLAMA, id="mac-docker-platform-warning"),
    # a runtime cleanup warning AFTER the version line
    pytest.param("mac-nerdctl-cleanup-warning", 0, LLAMA + "\n", NERDCTL_CLEANUP_WARN + "\n", True, LLAMA, id="mac-nerdctl-cleanup-warning"),
    # several runtime warnings around the version
    pytest.param("mac-both-warnings", 0, LLAMA + "\n", DOCKER_PLATFORM_WARN + "\n" + NERDCTL_CLEANUP_WARN + "\n", True, LLAMA, id="mac-both-warnings"),
    # the version on stderr only (an engine that logs to stderr)
    pytest.param("version-on-stderr", 0, "", PRISM + "\n", True, PRISM, id="version-on-stderr"),
    # a version line plus trailing blank lines / CRLF
    pytest.param("crlf-and-blank-lines", 0, LLAMA + "\r\n\r\n\n", "", True, LLAMA, id="crlf-and-blank-lines"),
    # exit 0 but only runtime noise: the runtime's own timestamp is not a version
    pytest.param("noise-only", 0, "", NERDCTL_CLEANUP_WARN + "\n", False, NERDCTL_CLEANUP_WARN, id="noise-only"),
    # the engine crashed (SIGILL under emulation): non-zero exit
    pytest.param("prism-sigill", 1, PRISM_SIGILL + "\n", NERDCTL_FATAL + "\n", False, NERDCTL_FATAL, id="prism-sigill"),
    # a version printed but the script exited non-zero
    pytest.param("version-but-nonzero", 125, LLAMA + "\n", "", False, LLAMA, id="version-but-nonzero"),
    # nothing at all
    pytest.param("empty", 0, "", "", False, "", id="empty"),
])
def test_version_check_accepts_the_version_line_anywhere(case, rc, stdout, stderr, ok, reported):
    """The --version check passes on exit 0 with an engine version on ANY line that is not
    runtime noise, and reports that line; it fails on a non-zero exit or no version."""

    # Given a start script's exit code and output in one of the shapes the runtimes print
    result = (rc, stdout, stderr)

    # When the --version check reads it
    got_ok, got_line = il.version_ok(*result)

    # Then it passes exactly when the engine printed a version and exited 0,
    # And it reports the engine's version line, not the runtime's warning
    assert got_ok is ok, case
    assert got_line.strip() == reported, case


def _emit(stdout: str, stderr: str, rc: int) -> str:
    """sh body printing `stdout` then `stderr` verbatim (heredocs: quotes stay literal)."""
    return f"cat <<'OUT'\n{stdout}\nOUT\ncat >&2 <<'ERR'\n{stderr}\nERR\nexit {rc}"


def _fake_bin(tmp: Path, name: str, body: str) -> None:
    f = tmp / name
    f.write_text("#!/bin/sh\n" + body + "\n")
    f.chmod(0o755)


def test_built_engine_test_passes_when_a_runtime_warning_follows_the_version(tmp_path):
    """make test-built-engine: start scripts that print the version and THEN a runtime
    warning (the shapes seen on the Mac) are all OK."""

    # Given four installed start scripts that print the version first, then a runtime warning
    for name, ver, warn in (("llgenie-engine-llama-cpp", LLAMA, NERDCTL_CLEANUP_WARN),
                            ("llgenie-engine-llama-cpp-prism", PRISM, DOCKER_PLATFORM_WARN),
                            ("llama-server", LLAMA, NERDCTL_CLEANUP_WARN),
                            ("prism-server", PRISM, DOCKER_PLATFORM_WARN)):
        _fake_bin(tmp_path, name, _emit(ver, warn, 0))

    # When make test-built-engine runs them
    rc = il.test(tmp_path)

    # Then every script passes
    assert rc == 0


def test_built_engine_test_still_fails_a_crashed_engine(tmp_path):
    """A start script whose engine crashed (Prism SIGILL under emulation) fails the check."""

    # Given a start script whose engine dies with SIGILL
    _fake_bin(tmp_path, "llgenie-engine-llama-cpp-prism", _emit(PRISM_SIGILL, NERDCTL_FATAL, 1))

    # When make test-built-engine runs it
    rc = il.test(tmp_path)

    # Then it fails
    assert rc == 1


# ---------------------------------------------------------------------------
# runtime: docker, the same CLI on Linux and macOS (Colima's docker runtime)
# ---------------------------------------------------------------------------
def _makefile_runtime_block() -> str:
    text = (REPO / "Makefile").read_text()
    start = text.index("# ---- container runtime")
    return text[start:text.index("OS_IMG", start)]


def test_runtime_is_docker_in_python_and_make(tmp_path):
    """engine_image.RUNTIME and the Makefile's RUNTIME are docker, with no RUNTIME set."""

    # Given no RUNTIME in the environment
    env = {k: v for k, v in os.environ.items() if k != "RUNTIME"}

    # When engine_image is imported and make resolves RUNTIME
    py = subprocess.run([sys.executable, "-c", "import engine_image as e; print(e.RUNTIME)"],
                        cwd=REPO / "scripts", env=env, capture_output=True, text=True)
    mk = subprocess.run(["make", "-s", "-f", "-", "show"], cwd=REPO, env=env, capture_output=True, text=True,
                        input=_makefile_runtime_block() + "\nshow:\n\t@echo $(RUNTIME)\n")

    # Then both are docker, and nerdctl is never named
    assert py.stdout.strip() == "docker", py.stderr
    assert mk.stdout.strip() == "docker", mk.stderr
    assert "nerdctl" not in _makefile_runtime_block()


def test_explicit_runtime_is_kept(tmp_path):
    """RUNTIME=<cli> in the environment overrides the default (python and make)."""

    # Given RUNTIME pointing at another docker CLI
    env = {**os.environ, "RUNTIME": "/opt/docker/bin/docker"}

    # When engine_image is imported and make resolves RUNTIME
    py = subprocess.run([sys.executable, "-c", "import engine_image as e; print(e.RUNTIME)"],
                        cwd=REPO / "scripts", env=env, capture_output=True, text=True)
    mk = subprocess.run(["make", "-s", "-f", "-", "show"], cwd=REPO, env=env, capture_output=True, text=True,
                        input=_makefile_runtime_block() + "\nshow:\n\t@echo $(RUNTIME)\n")

    # Then both keep it
    assert py.stdout.strip() == "/opt/docker/bin/docker", py.stderr
    assert mk.stdout.strip() == "/opt/docker/bin/docker", mk.stderr


def test_install_reports_a_dead_runtime_not_an_unpublished_image(tmp_path, monkeypatch, capsys):
    """A pull that fails because the runtime does not answer is reported as such,
    never as `not published in ghcr.io/...`."""

    # Given a runtime whose engine does not answer, so every pull fails
    importlib.reload(il)
    monkeypatch.setattr(il.ei, "_available", lambda tag: False)
    monkeypatch.setattr(il.ei, "runtime_answers", lambda rt: False)

    # When make install pulls the core engines
    rc = il.install(tmp_path, "cpu", build=False)

    # Then it fails and names the runtime, not the registry
    out = capsys.readouterr().out
    assert rc == 1
    assert "does not answer" in out and f"`{il.ei.RUNTIME} info` failed" in out
    assert "not published" not in out


def test_install_still_reports_an_unpublished_image_when_the_runtime_answers(tmp_path, monkeypatch, capsys):
    """With a working runtime, a missing tag is still `not published`."""

    # Given a working runtime and a tag that is not on the registry
    importlib.reload(il)
    monkeypatch.setattr(il.ei, "_available", lambda tag: False)
    monkeypatch.setattr(il.ei, "runtime_answers", lambda rt: True)

    # When make install pulls the core engines
    rc = il.install(tmp_path, "cpu", build=False)

    # Then it fails with "not published"
    out = capsys.readouterr().out
    assert rc == 1 and "not published in" in out and "does not answer" not in out


def test_pull_published_retries_a_tag_the_parallel_job_has_not_pushed_yet(monkeypatch):
    """A push run publishes the pinned tag from a parallel engine-image job. That
    job can still be pushing when install starts, so a failed pull is retried."""

    import scripts.engine_image as ei
    importlib.reload(ei)

    class R:
        def __init__(self, rc=0, out=""):
            self.returncode, self.stdout = rc, out

    pulls = {"n": 0}

    def fake_sh(cmd, **kw):
        if cmd[1:3] == ["buildx", "imagetools"]:
            return R(0, '"sha256:aaa"')
        if cmd[1] == "pull":
            pulls["n"] += 1
            return R(0 if pulls["n"] >= 3 else 1)
        return R(0)

    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "_sh", fake_sh)
    monkeypatch.setattr(ei, "_have_runtime", lambda: True)
    monkeypatch.setattr(ei.time, "sleep", lambda s: None)
    spec = {"tag": "llgenie/ollama:b0c1ca4f-de7798b2-cpu", "variant": "cpu"}

    # Given a tag the parallel job has not pushed yet
    # When it is pulled as published
    out = ei.pull_published(spec)

    # Then the pull was retried and the tag is used once it appears
    assert out == spec["tag"]
    assert pulls["n"] == 3


@pytest.mark.parametrize("plat", ["linux/amd64", "linux/arm64/v8"])
def test_start_scripts_pin_the_pulled_images_platform(tmp_path, monkeypatch, plat):
    """Every start script and shim passes --platform <the image's os/arch> to the runtime,
    read from the pulled image, so docker on an arm64 Mac does not warn on every run."""

    # Given pulled images whose platform the runtime reports as `plat`
    importlib.reload(il)
    monkeypatch.setattr(il.ei, "_available", lambda tag: True)
    monkeypatch.setattr(il.ei, "image_platform", lambda tag: plat)

    # When make install writes the start scripts
    assert il.install(tmp_path, "cpu", build=False) == 0

    # Then every docker run in every script carries --platform <plat>
    for name in ("llgenie-engine-llama-cpp", "llgenie-engine-llama-cpp-prism", "llama-server", "prism-server"):
        body = (tmp_path / name).read_text()
        runs = [ln for ln in body.splitlines() if f"{il.ei.RUNTIME} run --rm" in ln]
        assert runs and all(f"run --rm --platform {plat} " in ln for ln in runs), (name, runs)


def test_no_platform_flag_when_the_image_platform_is_unknown(tmp_path, monkeypatch):
    """An image whose platform cannot be read gets no --platform (the runtime's default)."""

    # Given images whose platform cannot be read
    importlib.reload(il)
    monkeypatch.setattr(il.ei, "_available", lambda tag: True)
    monkeypatch.setattr(il.ei, "image_platform", lambda tag: "")

    # When make install writes the start scripts
    assert il.install(tmp_path, "cpu", build=False) == 0

    # Then no script passes --platform
    assert all("--platform" not in p.read_text() for p in tmp_path.iterdir())


@pytest.mark.parametrize("inspect_out, rc, want", [
    ("linux/amd64\n", 0, "linux/amd64"),
    ("linux/arm64/v8\n", 0, "linux/arm64/v8"),
    ("", 1, ""),                              # no such image
    ("<no value>/amd64\n", 0, ""),            # a template the runtime could not fill
])
def test_image_platform_reads_os_arch_variant(tmp_path, monkeypatch, inspect_out, rc, want):
    """image_platform returns the image's os/arch[/variant], or "" when it cannot be read."""

    # Given a runtime whose `image inspect` prints `inspect_out` and exits `rc`
    _fake_bin(tmp_path, "fakert", f"printf '%s' '{inspect_out}'; exit {rc}")
    monkeypatch.setattr(ei, "RUNTIME", str(tmp_path / "fakert"))

    # When the image's platform is read
    got = ei.image_platform("llgenie/llama-cpp:t")

    # Then it is the os/arch[/variant], or "" when unreadable
    assert got == want


# ---------------------------------------------------------------------------
# CI: the macOS make install + make uninstall job
# ---------------------------------------------------------------------------
def test_linux_and_macos_run_the_same_pipeline():
    """CI runs ONE pipeline twice, in parallel: on a Linux and on a macOS runner, with the
    same jobs, make commands and asserts (issue #112). macOS never runs a Docker GitHub
    Action (the same targets run in the Python 3.11 venv). A failure on either OS fails
    the run. No macOS-only make target or job exists."""

    # Given the CI workflow, the shared pipelines and the Makefile
    wf = REPO / ".github" / "workflows"
    jobs = yaml.safe_load((wf / "ci.yml").read_text())["jobs"]
    pipeline = yaml.safe_load((wf / "pipeline.yml").read_text())["jobs"]
    docker = yaml.safe_load((REPO / ".github/actions/docker/action.yml").read_text())
    mk = (REPO / "Makefile").read_text()

    # When the triggers and the callers of each shared pipeline are read
    ci = yaml.safe_load((wf / "ci.yml").read_text())
    triggers = ci.get("on", ci.get(True))
    callers = {name: (job["uses"], job["with"]["runner"]) for name, job in jobs.items() if "uses" in job}

    # Then CI runs on pull requests targeting main AND on merges to main — never on a
    # bare feature-branch push (issue #107: PRs scope the engine matrix to changed engines)
    assert list(triggers) == ["pull_request", "push"]
    assert triggers["pull_request"]["branches"] == ["main"]
    assert triggers["push"]["branches"] == ["main"]

    # And linux and macos call the same pipeline, on a Linux and a macOS runner
    assert callers["linux"] == ("./.github/workflows/pipeline.yml", "ubuntu-latest")
    # (macOS: the SAME pipeline file, one job per make ci-<job>, no combined jobs, issue #120)
    assert callers["macos"] == ("./.github/workflows/pipeline.yml", "macos-15-intel")
    assert callers["linux-published"] == ("./.github/workflows/published.yml", "ubuntu-latest")
    # And macOS has no published-image stage: it never runs an engine container (issue #120)
    assert "macos-published" not in jobs

    # And every pipeline job runs on the caller's runner and only through make
    assert not (wf / "pipeline-macos.yml").exists()
    for name, job in pipeline.items():
        assert job["runs-on"] == "${{ inputs.runner }}", name

    # And a failure on either OS fails the run: no job is continue-on-error, and neither
    # macOS caller passes optional
    published = yaml.safe_load((wf / "published.yml").read_text())["jobs"]
    for name, job in {**pipeline, **published}.items():
        assert job["continue-on-error"] is False, name
    assert "optional" not in jobs["macos"]["with"]
    assert "optional" not in jobs["linux"]["with"] and "optional" not in jobs["linux-published"]["with"]
    install = "\n".join(st.get("run", "") for st in pipeline["install"]["steps"])
    assert "make ci-install" in install and "make install\n" not in install
    assert "test-install-ci" not in install
    ci_install = mk.split("\nci-install:", 1)[1].split("\n\n", 1)[0]
    assert "$(MAKE) test-env" in ci_install and "$(MAKE) ci-install-run" in ci_install
    assert "$(MAKE) ci-install-dry" in ci_install and "test-install-ci" not in ci_install
    run = mk.split("\nci-install-run:", 1)[1].split("\n\n", 1)[0]
    assert "ifeq ($(HOST_OS),Darwin)" in run and "$(ENGINE_TEST_RUN)" in run.split("else", 1)[1]

    # And the Docker action never RUNS a Docker GitHub Action and never starts Colima
    mac_steps = [st for st in docker["runs"]["steps"] if st.get("if") == "runner.os == 'macOS'"]
    assert mac_steps and all("uses" not in st for st in mac_steps)
    action = (REPO / ".github/actions/docker/action.yml").read_text()
    assert "uses: docker/setup-docker-action" not in action
    assert "colima start" not in action
    assert "exit 1" in action

    # And test-install-ci asserts make uninstall through test-uninstalled
    recipe = mk[mk.index("\ntest-install-ci:"):mk.index("\ntest-uninstalled:")]
    for step in ("make install", "make test-install-host", "make test-health-host",
                 "make test-install-trend", "make uninstall", "make test-uninstalled", "not-ours"):
        assert step in recipe, step

    # And no macOS-only make target or job exists
    assert "test-install-mac" not in mk and "test-install-cycle" not in mk
    assert not {"install-mac", "engine-smoke-mac", "server-variants-mac"} & set(jobs)


# ---------------------------------------------------------------------------
# macOS: a broken Colima (stopped VM, VM DNS not answering) is repaired before a pull
# ---------------------------------------------------------------------------
def _fake_colima(tmp: Path, docker_up: bool, dns_up: bool, resolv_fixes: bool = True) -> Path:
    """Fake `docker` + `colima` on PATH, logging every colima call. `colima start` brings
    docker and DNS up; writing the VM's resolv.conf (`colima ssh -- sudo sh -c ...`) fixes
    DNS when `resolv_fixes`."""
    log = tmp / "calls.log"
    state = tmp / "state"
    state.write_text(("D" if docker_up else "") + ("N" if dns_up else ""))
    fix = f'echo DN > "{state}"' if resolv_fixes else "true"
    _fake_bin(tmp, "docker", f'[ "$1" = info ] && grep -q D "{state}" && exit 0; [ "$1" = info ] && exit 1; exit 0')
    _fake_bin(tmp, "colima", f'''printf 'colima %s\\n' "$*" | tr -d '\\n' >> "{log}"; echo >> "{log}"
case "$1 $3" in
  "ssh getent") grep -q N "{state}" && echo "4.225.11.196 ghcr.io" && exit 0; exit 2 ;;
  "ssh sudo") {fix}; exit 0 ;;
esac
case "$1" in
  stop) exit 0 ;;
  start) echo DN > "{state}"; exit 0 ;;
esac''')
    return log


@pytest.mark.parametrize("docker_up, dns_up, resolv_fixes", [
    pytest.param(True, True, True, id="healthy-untouched"),
    pytest.param(True, False, True, id="vm-dns-broken-not-repaired"),
    pytest.param(True, False, False, id="vm-dns-still-broken-not-restarted"),
    pytest.param(False, False, True, id="vm-stopped-not-started"),
])
def test_macos_colima_is_never_started(tmp_path, monkeypatch, docker_up, dns_up, resolv_fixes):
    """On macOS, a stopped or DNS-broken runtime is reported. Colima is never called."""

    # Given a Mac whose runtime is healthy, has broken DNS, or is stopped
    log = _fake_colima(tmp_path, docker_up, dns_up, resolv_fixes)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    monkeypatch.setattr(ei, "RUNTIME", "docker")

    # When make install / llgenie check the container environment
    ok = ei.ensure_container_env("darwin")

    # Then a healthy runtime is OK, a broken one is not, and colima was never called
    assert ok is docker_up
    assert not log.exists()


def test_linux_container_env_is_never_touched(tmp_path, monkeypatch):
    """Off macOS the check is a no-op: colima is never called, even when docker is down."""

    # Given a Linux host with docker down and a colima binary on PATH
    log = _fake_colima(tmp_path, docker_up=False, dns_up=False)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    monkeypatch.setattr(ei, "RUNTIME", "docker")

    # When the container environment is checked
    ok = ei.ensure_container_env("linux")

    # Then it reports OK without calling colima
    assert ok is True
    assert not log.exists()


def test_install_and_llgenie_check_the_container_env_first():
    """make install (install_engine_launchers) and llgenie (llama_serve: the llama-server
    shim and first-use engine pulls) call the check before any container starts."""

    # Given the install script and the llgenie launcher source
    inst = (REPO / "scripts" / "install_engine_launchers.py").read_text()
    serve = (REPO / "scripts" / "llama_serve.py").read_text()

    # When the start paths are read
    main = inst[inst.index("def main("):]
    invoke = serve[serve.index("def invoke_llama_server("):serve.index("def _serve_chosen(")]
    first_use = serve[serve.index("def _ensure_and_exec("):serve.index("def _pick_mp(")]

    # Then a container path checks the environment before pulling or running.
    # macOS make install never pulls, even when --arch is passed. The llama-server
    # container check is Linux-only.
    assert 'if sys.platform == "darwin":' in main
    assert "Colima is not started" in main
    assert "ensure_native" in main
    assert 'if sys.platform != "darwin":' in invoke
    assert invoke.index("ensure_container_env()") < invoke.index("subprocess.run(cmd)")
    assert "macOS never starts an engine image" in first_use


# ---------------------------------------------------------------------------
# test-agents-read builds its own Python 3.12 venv (no pre-installed hermes-agent)
# ---------------------------------------------------------------------------
def test_macos_install_never_pulls_an_engine_image(tmp_path, monkeypatch):
    """A Darwin make install with a live runtime still never pulls an image."""

    # Given an Apple-Silicon Darwin host whose container runtime answers, and a fake pull
    calls = []
    monkeypatch.setattr(il.sys, "platform", "darwin")
    monkeypatch.setattr("detect_server._macos_silicon", lambda: True)
    monkeypatch.setattr(il.ei, "runtime_answers", lambda rt: True)
    monkeypatch.setattr(il.ei, "ensure_container_env", lambda *a, **k: calls.append("env") or True)
    monkeypatch.setattr(il, "ensure_image", lambda *a, **k: calls.append(("pull", a)) or "tag")
    monkeypatch.setattr(il, "ensure_native", lambda bindir, engine, dry=False: calls.append(("native", engine)) or 0)

    # When make install runs with no --arch
    import importlib
    mp = importlib.import_module("model_engine_pick")
    monkeypatch.setattr(mp, "metal_engines", lambda: {"llama.cpp"})
    rc = il.main(["--bin", str(tmp_path / "bin")])

    # Then it wrote the native script and never pulled or checked the runtime
    assert rc == 0
    assert ("native", "llama.cpp") in calls
    assert not any(c == "env" or (isinstance(c, tuple) and c[0] == "pull") for c in calls)

    # And an explicit --arch cpu is refused without a pull
    calls.clear()
    rc = il.main(["--bin", str(tmp_path / "bin"), "--arch", "cpu"])
    assert rc == 1
    assert calls == []


def test_intel_mac_install_does_not_install_metal_engines(tmp_path, monkeypatch):
    """An Intel Mac cannot install arm64 Metal wheels and must not pull an image."""

    # Given a Darwin x86_64 host (the macos-15-intel runner) and a live runtime
    calls = []
    monkeypatch.setattr(il.sys, "platform", "darwin")
    monkeypatch.setattr("detect_server._macos_silicon", lambda: False)
    monkeypatch.setattr(il.ei, "ensure_container_env", lambda *a, **k: calls.append("env") or True)
    monkeypatch.setattr(il, "ensure_image", lambda *a, **k: calls.append(("pull", a)) or "tag")
    monkeypatch.setattr(il, "ensure_native", lambda *a, **k: calls.append("native") or 0)

    # When make install runs
    rc = il.main(["--bin", str(tmp_path / "bin")])

    # Then it exits 0 without installing a Metal engine or pulling an image
    assert rc == 0
    assert calls == []


def test_intel_mac_built_engine_test_and_uninstall_are_noops(tmp_path, monkeypatch):
    """On Intel macOS, make install writes nothing, so test-built-engine and uninstall
    (the steps that follow make install) must also pass with nothing to do; Linux must
    still fail a missing install (issue #120)."""

    # Given a Darwin x86_64 host (the macos-15-intel runner)
    monkeypatch.setattr(il.sys, "platform", "darwin")
    monkeypatch.setattr("detect_server._macos_silicon", lambda: False)

    # When make install's test-built-engine and uninstall steps run
    rc_test = il.main(["--bin", str(tmp_path / "bin"), "--test"])
    rc_uninstall = il.main(["--bin", str(tmp_path / "bin"), "--uninstall"])

    # Then both are a no-op that exits 0 (nothing was written, nothing to remove)
    assert rc_test == 0
    assert rc_uninstall == 0
    assert list(tmp_path.iterdir()) == []

    # And an explicit --arch cpu is still refused (the health / top-tier job asserts it)
    rc_cpu = il.main(["--bin", str(tmp_path / "bin"), "--arch", "cpu"])
    assert rc_cpu == 1

    # And on Linux a missing install still fails test-built-engine loudly
    monkeypatch.setattr(il.sys, "platform", "linux")
    rc_linux = il.test(tmp_path)
    assert rc_linux == 1


def test_intel_mac_ensure_still_installs_a_metal_engine_natively(tmp_path, monkeypatch):
    """Even on Intel macOS, an explicit `--ensure <engine> --arch metal` (the llgenie
    pick path, driven on the macos-15-intel runner by LLAMA_BACKEND=metal) still runs the
    engine's native Metal install — only the default make install is a no-op there."""

    # Given a Darwin x86_64 host (the macos-15-intel runner)
    calls = []
    monkeypatch.setattr(il.sys, "platform", "darwin")
    monkeypatch.setattr("detect_server._macos_silicon", lambda: False)
    monkeypatch.setattr(il, "ensure_native", lambda bindir, engine, dry=False: calls.append(engine) or 0)

    # When llgenie ensures one engine natively for metal (the TensorFold pick)
    rc = il.main(["--bin", str(tmp_path / "bin"), "--ensure", "tensorfold", "--arch", "metal"])

    # Then it ran the native install and wrote nothing to a container
    assert rc == 0
    assert calls == ["tensorfold"]



def test_linux_install_still_pulls_images(tmp_path, monkeypatch):
    """Linux make install still checks the runtime and pulls this host's images."""

    # Given a Linux host
    calls = []
    monkeypatch.setattr(il.sys, "platform", "linux")
    monkeypatch.setattr(il, "detected_arch", lambda: "cpu")
    monkeypatch.setattr(il.ei, "ensure_container_env", lambda *a, **k: calls.append("env") or True)
    monkeypatch.setattr(il, "install", lambda *a, **k: calls.append("install") or 0)

    # When make install runs with no --arch
    rc = il.main(["--bin", str(tmp_path / "bin")])

    # Then the runtime was checked and the image install ran
    assert rc == 0
    assert calls == ["env", "install"]


def test_agents_read_builds_its_own_python312_venv():
    """make test-agents-read builds its Python 3.12 venv (hermes-agent + pytest) itself and
    runs the scan and the guard's tests in it; CI only provides python3.12 and calls make."""

    # Given the Makefile and the shared CI pipeline
    mk = (REPO / "Makefile").read_text()
    jobs = yaml.safe_load((REPO / ".github/workflows/pipeline.yml").read_text())["jobs"]

    # When the test-agents-read recipe and the venv rule are read
    recipe = mk[mk.index("\ntest-agents-read:"):mk.index("\ntest-install:")]
    venv_rule = mk[mk.index("\n$(AGENTS_READ_STAMP):"):mk.index("\ntest-agents-read:")]

    # Then test-agents-read depends on the venv, built with python3.12 and the pinned deps
    assert recipe.split("\n")[1].startswith("test-agents-read: agents-read-venv")
    assert "PY312             ?= python3.12" in mk and "HERMES_AGENT_PIN  := hermes-agent==0.19.0" in mk
    assert "$(PY312) -m venv" in venv_rule and '"$(HERMES_AGENT_PIN)" pytest' in venv_rule

    # And the scan and the guard's tests run with that venv's python
    assert '"$(AGENTS_READ_VENV)/bin/python" scripts/scan_agents_md.py AGENTS.md' in recipe
    assert '"$(AGENTS_READ_VENV)/bin/python" -m pytest tests/test_agents_read.py' in recipe

    # And the CI job runs no pip or pytest itself, only make (one ci-<job> target, issue #117)
    runs = [st["run"] for st in jobs["agents-read"]["steps"] if "run" in st]
    assert runs == ["make ci-agents-read"]
    ci_recipe = mk.split("\nci-agents-read:", 1)[1].split("\n\n", 1)[0]
    assert "$(MAKE) test-agents-read" in ci_recipe
    # And the job sets up python3.12 before that step (the same job runs on macOS: one pipeline file)
    steps = jobs["agents-read"]["steps"]
    assert any(st.get("uses", "").startswith("actions/setup-python") and st["with"]["python-version"] == "3.12"
               for st in steps)
    # And the venv lives outside the repo (the guard rejects a hermes module from the repo)
    assert "AGENTS_READ_VENV  ?= $(HOME)/.cache/llgenie/agents-read-venv" in mk


# ---------------------------------------------------------------------------
# bash 5 recipe-shell parity gate (issue #120): macOS uses brew bash 5, Linux bash 5
# ---------------------------------------------------------------------------
import scripts.check_bash as cb  # noqa: E402


def _makefile_shell_block() -> str:
    text = (REPO / "Makefile").read_text()
    start = text.index("SHELL    := $(shell")
    return text[start:text.index("HOME    := $(shell", start)]


def test_macos_make_uses_bash5():
    """The Makefile resolves SHELL to a bash 5 on macOS (brew's bash preferred over
    the system bash 3.2), and the bash-check gate passes under it."""

    # Given the Makefile's SHELL resolution and the check_bash gate
    block = _makefile_shell_block()
    mk = subprocess.run(["make", "-s", "-f", "-", "show"], cwd=REPO, capture_output=True, text=True,
                        input=block + "\nshow:\n\t@echo $(SHELL)\n")

    # When the resolved SHELL is read and the gate runs against it
    shell = mk.stdout.strip()
    rc = cb.real_main([shell])

    # Then it is a bash 5 and the gate passes
    assert os.path.basename(shell) == "bash", shell
    assert cb.version_at_least_5(cb.bash_version(shell) or ""), shell
    assert rc == 0
    assert "export LLGENIE_BASH := $(SHELL)" in block


def test_loopback_fixture_does_no_hostname_lookup():
    """The macOS 15 runner stalls socket.getfqdn() ~35s between bind and listen
    (actions/runner-images#14409). python3 -m http.server does that lookup, so a
    30s probe reports it dead. The fixture must bind and listen with no lookup."""

    # Given the fixture and the two tests that serve a plan through the runner
    src = (REPO / "scripts" / "loopback_server.py").read_text()
    callers = "\n".join((REPO / "tests" / f).read_text()
                         for f in ("test_engine_skills.py", "test_macos_install.py"))

    # When we look at what they launch
    # Then the fixture does no name lookup, and neither test uses http.server
    code = src.split('"""', 2)[-1]
    assert "getfqdn(" not in code and "import http.server" not in code
    assert "socket.listen" in src or ".listen(" in src
    launches = [l for l in callers.splitlines() if l.strip().startswith('"launch"')]
    assert len(launches) >= 2 and all("loopback_server.py" in l for l in launches)


def test_runner_serves_with_the_bash_make_selected_not_bin_bash(tmp_path, monkeypatch):
    """The macOS CI runner invokes /bin/bash (3.2) as a login shell, which drops the
    venv from PATH. The runner must use the bash make selected (LLGENIE_BASH), or a
    launch of a server never binds (issue #120, run 37929800971)."""

    import scripts.engine_runner as runner

    # Given the runner's /bin/bash (a login shell: it drops the venv, so the server
    # never binds) and the bash make selected (it keeps PATH)
    marker = tmp_path / "shell-used"
    login = tmp_path / "bin-bash"
    login.write_text(f"#!/bin/sh\nprintf '%s' bin-bash > {marker}\nexit 1\n")
    login.chmod(0o755)
    good = tmp_path / "bash5"
    good.write_text(f"#!/bin/sh\nprintf '%s' bash5 > {marker}\nexec /bin/bash --noprofile --norc \"$@\"\n")
    good.chmod(0o755)
    monkeypatch.setenv("LLGENIE_BASH", str(good))
    port = __import__("scripts.engine_smoke", fromlist=["free_port"]).free_port()
    plan = {"id": "fake", "backend": "cpu", "env": {},
            "launch": "exec python3 scripts/loopback_server.py {port} --bind {host}",
            "health": "GET /", "pre_launch": None, "post_launch": None}

    # When the runner serves that plan
    rc = runner.serve_plan(plan, "/m", "127.0.0.1", port, ready_timeout=15, on_ready=lambda: None)

    # Then the shell that ran is the one make selected, and the server came up
    assert marker.read_text() == "bash5"
    assert rc in (0, -15, 143)


def test_bash5_gate_fails_closed_on_bash32():
    """Passing the macOS system bash 3.2 to the gate fails closed (exit 1), so no
    stage ever runs under bash 3.2."""

    # Given the macOS system bash (3.2) as the recipe shell
    sys_bash = "/bin/bash"
    v = cb.bash_version(sys_bash)

    # When the gate evaluates it
    rc = cb.real_main([sys_bash])

    # Then it fails closed unless that bash is already bash 5 (Linux CI).
    # Exit 3 means bash 5 exists elsewhere (brew) but is not the recipe shell:
    # still fail-closed, the Makefile must re-run so SHELL resolves to it.
    if v and cb.version_at_least_5(v):
        assert rc == 0
    else:
        assert rc in (1, 3), rc


def test_bash5_gate_installs_via_brew_when_missing(tmp_path, monkeypatch):
    """On macOS with brew available and no brew bash, the gate installs bash 5 via
    `brew install bash` and asks for a re-run (exit 3)."""

    # Given a macOS host with brew but no brew bash, and a bash 5 elsewhere
    monkeypatch.setattr(cb, "sys", type("S", (), {"platform": "darwin"})())
    monkeypatch.setattr(cb.shutil, "which", lambda name: "/opt/homebrew/bin/brew" if name == "brew" else "/bin/bash")
    monkeypatch.setattr(cb, "brew_bash", lambda: "/opt/homebrew/bin/bash")
    monkeypatch.setattr(cb.os.path, "isfile", lambda p: False)
    calls = []
    monkeypatch.setattr(cb.subprocess, "run", lambda *a, **k: calls.append(a[0]) or type("R", (), {"returncode": 0})())

    # When the gate runs with a non-bash-5 effective shell
    rc = cb.real_main(["/bin/bash"])

    # Then it installs bash via brew and asks for a re-run
    assert ["brew", "install", "bash"] in calls
    assert rc == 3


def test_macos_make_installs_bash5_when_missing(monkeypatch, capsys):
    """At make-parse time (`check_bash.py --resolve`, the Makefile's SHELL) a macOS host with
    brew but no brew bash gets `brew install bash` FIRST, and SHELL is brew's bash 5 in the
    SAME make run, so a fresh CI runner needs no second `make` (the failure of run 37890648373)."""

    # Given a macOS host with brew but no brew bash yet
    state = {"installed": False}
    monkeypatch.setattr(cb, "sys", type("S", (), {"platform": "darwin", "stderr": sys.stderr})())
    monkeypatch.setattr(cb.shutil, "which", lambda name: "/opt/homebrew/bin/brew" if name == "brew" else "/bin/bash")
    monkeypatch.setattr(cb, "brew_bash", lambda: "/opt/homebrew/bin/bash")
    monkeypatch.setattr(cb.os.path, "isfile", lambda p: state["installed"])
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        state["installed"] = True
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(cb.subprocess, "run", run)

    # When make resolves its SHELL
    rc = cb.real_main(["--resolve"])

    # Then bash was installed via brew and SHELL is brew's bash (stdout is only the path)
    assert rc == 0 and calls == [["brew", "install", "bash"]]
    assert capsys.readouterr().out.strip() == "/opt/homebrew/bin/bash"

    # And the Makefile takes SHELL from that resolver
    assert "SHELL    := $(shell python3 scripts/check_bash.py --resolve" in (REPO / "Makefile").read_text()


def test_pure_make_surface_runs_the_python_script():
    """The bash-check make target is a thin entrypoint that runs scripts/check_bash.py
    (the single source of truth), not a second shell implementation."""

    # Given the Makefile's bash-check recipe
    mk = (REPO / "Makefile").read_text()
    recipe = mk[mk.index("\nbash-check:"):mk.index("\n# Put ~/bin on PATH", mk.index("\nbash-check:"))]

    # When the recipe is read
    # Then it runs the python script with the resolved SHELL, and no shell logic is duplicated
    assert "python3 scripts/check_bash.py" in recipe
    assert '"$(SHELL)"' in recipe
    assert "brew install bash" not in recipe  # the install lives in the the python script, not make


# ---------------------------------------------------------------------------
# issue #120: ONE engine stage (make ci-engines) is the only per-OS row
# ---------------------------------------------------------------------------
def test_engine_stage_is_one_make_target():
    """The engine install stage is make ci-engines (scripts/ci_engines.py). CI runs it on
    Linux per container backend; BACKEND=metal stays a make target for an Apple-Silicon
    host (issue #120: no macOS CI job, the runners have no Metal GPU)."""

    # Given the workflows and the Makefile
    wf = REPO / ".github" / "workflows"
    published = yaml.safe_load((wf / "published.yml").read_text())["jobs"]["install-published"]
    mk = (REPO / "Makefile").read_text()

    # When the engine-install steps are collected
    linux_runs = [st["run"] for st in published["steps"] if "run" in st and "ci-engines" in st["run"]]

    # Then the Linux row calls make ci-engines per backend
    assert linux_runs == ["make ci-engines BACKEND=${{ matrix.backend }}"]

    # And the target is a thin entrypoint over the python script
    recipe = mk.split("\nci-engines:", 1)[1].split("\n\n", 1)[0]
    assert "python3 scripts/ci_engines.py $(BACKEND)" in recipe and "bash-check" in recipe.splitlines()[0]
    assert re.search(r"^test-native-engines:", mk, re.M)
    assert "tests/test_native_engines.py" in mk.split("\ntest-native-engines:", 1)[1].split("\n\n", 1)[0]


@pytest.mark.parametrize("backend, want", [
    pytest.param("cpu", ["make test-install-published BACKEND=cpu"], id="linux-cpu"),
    pytest.param("cuda", ["make test-install-published BACKEND=cuda"], id="linux-cuda"),
    pytest.param("metal", ["make test-native-engines", "make test-native-engine",
                           "make test-interactive-tensorfold-ci", "make test-native-engine-light"], id="macos-metal"),
])
def test_ci_engines_plans_the_backends_engine_matrix(backend, want):
    """scripts/ci_engines.py maps BACKEND to the make targets of that OS's engine row."""

    # Given the ci_engines script

    # When it plans BACKEND
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "ci_engines.py"), "--plan", backend],
                       capture_output=True, text=True)

    # Then it prints exactly that row's make targets
    assert r.returncode == 0, r.stderr
    assert r.stdout.split("\n")[:-1] == want


def test_ci_engines_runs_every_stage_and_fails_when_one_fails(tmp_path):
    """Every stage of the row runs; one failing stage fails the run (no stage hides another)."""

    # Given a fake make that fails only test-native-engine
    log = tmp_path / "make.log"
    _fake_bin(tmp_path, "make", f'echo "$*" >> "{log}"; [ "$1" = test-native-engine ] && exit 3; exit 0')
    sys.path.insert(0, str(REPO / "scripts"))
    import ci_engines
    importlib.reload(ci_engines)

    # When the metal row runs on an Apple-Silicon host
    old = os.environ.get("MAKE")
    os.environ["MAKE"] = str(tmp_path / "make")
    try:
        ci_engines.apple_silicon = lambda: True
        rc = ci_engines.real_main(["metal"])
    finally:
        os.environ.pop("MAKE") if old is None else os.environ.__setitem__("MAKE", old)

    # Then all four stages ran and the run failed
    assert rc == 1
    assert log.read_text().split("\n")[:-1] == list(ci_engines.NATIVE_TARGETS)


def test_ci_engines_rejects_an_unknown_backend_and_metal_off_apple_silicon():
    """An unknown BACKEND is a usage error; metal on a non-Apple-Silicon host fails loudly."""

    # Given the ci_engines script
    sys.path.insert(0, str(REPO / "scripts"))
    import ci_engines
    importlib.reload(ci_engines)

    # When it is asked for an unknown backend, and for metal off Apple Silicon
    unknown = ci_engines.real_main(["sparc"])
    ci_engines.apple_silicon = lambda: False
    metal = ci_engines.real_main(["metal"])

    # Then both fail (never a silent pass)
    assert unknown == 2 and metal == 1


def test_macos_ci_does_not_run_docker_github_actions():
    """macOS CI never runs a Docker GitHub Action: the same make targets run in the
    Python 3.11 venv, and a failure on either OS fails the run (issue #120)."""

    # Given the workflows, the Docker action and the Makefile
    wf = REPO / ".github" / "workflows"
    pipeline = yaml.safe_load((wf / "pipeline.yml").read_text())["jobs"]
    published = yaml.safe_load((wf / "published.yml").read_text())["jobs"]
    ci = yaml.safe_load((wf / "ci.yml").read_text())["jobs"]
    docker = (REPO / ".github/actions/docker/action.yml").read_text()
    mk = (REPO / "Makefile").read_text()

    # When the Docker steps and the install/health recipes are read
    docker_steps = [st for jobs in (pipeline, published) for j in jobs.values()
                    for st in j.get("steps", []) if st.get("uses") == "./.github/actions/docker"]
    linux_only = ("install", "openspec", "cpu-health", "top-tier")

    # Then no workflow step runs a Docker GitHub Action, and no macOS job starts Colima
    assert "uses: docker/setup-docker-action" not in docker
    assert "uses: docker/setup-buildx-action@v3" in docker and "runner.os == 'Linux'" in docker
    assert "colima start" not in docker
    assert "macOS must not call this action" in docker

    # And every shared pipeline job that mentions the Docker action gates it to Linux
    # (published.yml is Linux only: macOS has no published-image stage)
    for name, step in ((name, st) for name, j in pipeline.items()
                       for st in j.get("steps", []) if st.get("uses") == "./.github/actions/docker"):
        assert step.get("if") == "runner.os == 'Linux'", name
    assert "macos-published" not in ci

    # And install, health and top-tier are the same targets on both OSes (no second Darwin install)
    for target, same in (
        ("ci-install", "$(MAKE) test-env"),
        ("ci-install", "$(MAKE) ci-install-run"),
        ("ci-install", "$(MAKE) ci-install-dry"),
        ("ci-install", "$(MAKE) ci-install-uninstall"),
        ("ci-cpu-health", "$(MAKE) test-health"),
        ("ci-top-tier", "$(MAKE) test-top-tier-ci "),
    ):
        recipe = mk.split("\n" + target + ":", 1)[1].split("\n\n", 1)[0]
        assert same in recipe and "Darwin" not in recipe, target

    # And every macOS job and every Linux job must succeed for the run to be green
    for name, job in {**pipeline, **published}.items():
        assert job["continue-on-error"] is False, name
    for name in ("linux", "macos", "linux-published"):
        assert "optional" not in ci[name]["with"], name


def test_macos_has_no_published_image_or_native_engine_ci_job():
    """macOS never runs an inference server in a container and its GitHub runners have no
    Metal GPU (issue #120): CI has no macos-published stage and no native-engine job."""

    # Given ci.yml and published.yml
    wf = REPO / ".github" / "workflows"
    ci = yaml.safe_load((wf / "ci.yml").read_text())["jobs"]
    published = (wf / "published.yml").read_text()

    # When the jobs and their runners are read
    runners = {n: j.get("runs-on") or j.get("with", {}).get("runner") for n, j in ci.items()}
    macos = {n for n, r in runners.items() if r and "macos" in str(r)}

    # Then the only macOS job is the shared pipeline
    assert macos == {"macos"}
    assert "macos-published" not in ci and "native-engine-macos-arm64" not in ci

    # And published.yml is Linux only (no macOS runner, no runner.os branch)
    assert "macos" not in published and "runner.os" not in published


def test_native_engine_matrix_covers_every_metal_skill():
    """tests/test_native_engines.py proves EVERY native-Metal engine (none left out)."""

    # Given the engine skills and the native-engines test
    import scripts.engine_skills as es
    src = (REPO / "tests" / "test_native_engines.py").read_text()

    # When the native-Metal set is read
    import scripts.model_engine_pick as mp
    native = sorted(mp.metal_engines())

    # Then every native engine has a tiny-model serve or a named serve target
    assert native, "no native-Metal engine skill"
    for engine in native:
        assert any(f'"{engine}": {v}' in src for v in ("(", "_GGUF", '"make ')), engine
    # And the llama.cpp builds are part of it (built natively with Metal, issue #120)
    assert {"llama.cpp", "llama.cpp-prism"} <= set(native)


# ---------------------------------------------------------------------------
# issue #120: Python 3.11 everywhere (test image + gguf venv)
# ---------------------------------------------------------------------------
def test_test_image_and_tools_image_are_python311():
    """The test image and the tools lockfile image run Python 3.11 (issue #120)."""

    # Given the two Dockerfiles

    # When their base images are read
    bases = [l for f in ("containers/test/Dockerfile", "tools/Dockerfile")
             for l in (REPO / f).read_text().splitlines() if l.startswith("FROM ")]

    # Then every base is python:3.11-slim
    assert bases and all("python:3.11-slim" in b for b in bases), bases


def test_venv_is_created_with_python311(tmp_path):
    """tools create-venv uses scripts/check_python.py: a venv that is not 3.11 is recreated."""

    # Given the tools Makefile and a fake venv whose python is 3.10
    mk = (REPO / "tools" / "Makefile").read_text()
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    _fake_bin(venv / "bin", "python", 'echo "3 10"')

    # When check_python inspects it, and the running 3.x interpreter is resolved
    rc_old = subprocess.run([sys.executable, str(REPO / "scripts" / "check_python.py"), "--venv", str(venv)]).returncode
    _fake_bin(venv / "bin", "python", 'echo "3 11"')
    rc_new = subprocess.run([sys.executable, str(REPO / "scripts" / "check_python.py"), "--venv", str(venv)]).returncode

    # Then a 3.10 venv is rejected, a 3.11 one reused, and the recipe uses the script
    assert rc_old == 1 and rc_new == 0
    recipe = mk.split("\ncreate-venv:", 1)[1].split("\n\n", 1)[0]
    assert "../scripts/check_python.py --venv" in recipe and "python3.10" not in recipe


def test_macos_make_test_stages_run_in_the_311_venv_not_a_container():
    """macOS runs every test stage natively in the Python 3.11 venv; Linux in llgenie/test (issue #120)."""

    # Given the Makefile
    mk = (REPO / "Makefile").read_text()

    # When the Darwin and Linux branches of the test runners are read
    darwin = mk.split("ifeq ($(HOST_OS),Darwin)\n", 1)[1].split("\nelse\n", 1)[0]
    linux = mk.split("ifeq ($(HOST_OS),Darwin)\n", 1)[1].split("\nelse\n", 1)[1].split("\nendif", 1)[0]
    env = mk.split("\ntest-env:", 1)[1].split("\n\n", 1)[0]

    # Then macOS uses the venv python (no docker run, no test image) and Linux the 3.11 test image
    assert '$(VENV)/bin' in darwin and "$(RUNTIME) run" not in darwin and "$(TEST_IMG)" not in darwin
    assert "TEST_RUN :=" in darwin and "engine_test =" in darwin and "CI_HOME_CLEAN :=" in darwin
    assert "$(TEST_IMG)" in linux and "TEST_RUN :=" in linux
    assert "$(MAKE) -C tools venv-dev-install" in env and "ci_images.py pull test" in env

    # And every CI job prepares that environment with make test-env, never make test-image-pull
    for wf in ("pipeline.yml", "published.yml"):
        text = (REPO / ".github" / "workflows" / wf).read_text()
        assert "make test-image-pull" not in text.split("\non:", 1)[1], wf
        assert "run: make test-env" in text, wf


def test_macos_test_env_installs_uv_before_make_install():
    """macOS test-env puts uv on PATH before make install; Linux does not brew (issue #120)."""

    # Given the Makefile test-env recipe
    mk = (REPO / "Makefile").read_text()
    env = mk.split("\ntest-env:", 1)[1].split("\n\n", 1)[0]
    darwin, linux = env.split("ifeq ($(HOST_OS),Darwin)\n", 1)[1].split("\nelse\n", 1)
    linux = linux.split("\nendif", 1)[0]

    # When the Darwin and Linux branches are read
    # Then Darwin installs uv only when it is missing, and checks it is on PATH
    assert "$(MAKE) -C tools venv-dev-install" in darwin
    assert "command -v uv >/dev/null || brew install uv" in darwin
    assert darwin.strip().endswith("command -v uv >/dev/null")
    assert "colima" not in darwin.lower()

    # And Linux still only pulls the test image
    assert "ci_images.py pull test" in linux and "brew" not in linux
