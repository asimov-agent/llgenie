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


# ---------------------------------------------------------------------------
# the start scripts run the image as the platform it was built for
# ---------------------------------------------------------------------------
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
    same jobs, make commands and asserts (issue #112). The only per-OS step is the Docker
    setup action (macOS: docker/setup-docker-action). No macOS-only make target or job exists."""

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

    # Then a push starts ONE run (push only, every branch; no second pull_request run)
    assert list(triggers) == ["push"] and triggers["push"]["branches"] == ["**"]

    # And linux and macos call the same pipeline, on a Linux and a macOS runner
    assert callers["linux"] == ("./.github/workflows/pipeline.yml", "ubuntu-latest")
    assert callers["macos"] == ("./.github/workflows/pipeline.yml", "macos-15-intel")
    assert callers["linux-published"] == ("./.github/workflows/published.yml", "ubuntu-latest")
    assert callers["macos-published"] == ("./.github/workflows/published.yml", "macos-15-intel")

    # And every pipeline job runs on the caller's runner and only through make
    for name, job in pipeline.items():
        assert job["runs-on"] == "${{ inputs.runner }}", name

    # And only the linux jobs gate the run: every macOS job is optional (continue-on-error),
    # so a macOS failure or timeout reports on the PR but never turns the run red
    published = yaml.safe_load((wf / "published.yml").read_text())["jobs"]
    for name, job in {**pipeline, **published}.items():
        assert job["continue-on-error"] == "${{ inputs.optional }}", name
    assert jobs["macos"]["with"]["optional"] is True and jobs["macos-published"]["with"]["optional"] is True
    assert "optional" not in jobs["linux"]["with"] and "optional" not in jobs["linux-published"]["with"]
    install = "\n".join(st.get("run", "") for st in pipeline["install"]["steps"])
    assert "make test-install-ci" in install

    # And the only OS-specific steps are Docker's own setup actions on macOS (no Colima)
    mac_steps = [st for st in docker["runs"]["steps"] if st.get("if") == "runner.os == 'macOS'"]
    assert [st.get("uses", "").split("@")[0] for st in mac_steps] == [
        "docker/setup-docker-action", "docker/setup-buildx-action"]
    assert "colima" not in (REPO / ".github/actions/docker/action.yml").read_text().lower()
    # And the VM mounts the checkout writable (make bind-mounts the repo read-write)
    assert "--mount-writable" in mac_steps[0]["env"]["LIMA_START_ARGS"]

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


@pytest.mark.parametrize("docker_up, dns_up, resolv_fixes, dns_writes, stops, starts", [
    pytest.param(True, True, True, 0, 0, 0, id="healthy-untouched"),
    pytest.param(True, False, True, 1, 0, 0, id="vm-dns-broken-resolvers-rewritten"),
    pytest.param(True, False, False, 1, 1, 1, id="vm-dns-still-broken-restarted-with-dns"),
    pytest.param(False, False, True, 0, 0, 1, id="vm-stopped-started-with-dns"),
])
def test_macos_colima_is_repaired_before_a_container_starts(tmp_path, monkeypatch, docker_up, dns_up,
                                                            resolv_fixes, dns_writes, stops, starts):
    """On macOS, a stopped Colima VM is started with explicit DNS resolvers; a running VM whose
    DNS does not resolve the registry gets those resolvers written into it, and is restarted
    with them only when that does not help; a healthy VM is never touched."""

    # Given a Mac whose Colima VM is healthy, has broken DNS, or is stopped
    log = _fake_colima(tmp_path, docker_up, dns_up, resolv_fixes)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    monkeypatch.setattr(ei, "RUNTIME", "docker")

    # When make install / llgenie check the container environment
    ok = ei.ensure_container_env("darwin")

    # Then the environment works afterwards
    assert ok is True

    # And Colima was repaired only as far as needed, always with explicit DNS
    calls = log.read_text().splitlines() if log.exists() else []
    writes = [c for c in calls if c.startswith("colima ssh -- sudo sh -c")]
    assert len(writes) == dns_writes
    assert all("nameserver 1.1.1.1" in c and "8.8.8.8" in c and "> /etc/resolv.conf" in c for c in writes)
    assert sum(c == "colima stop" for c in calls) == stops
    started = [c for c in calls if c.startswith("colima start")]
    assert len(started) == starts
    assert all("--dns 1.1.1.1 --dns 8.8.8.8" in c for c in started)


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

    # Then each one checks the environment before pulling or running a container
    assert main.index("ei.ensure_container_env()") < main.index("return install(")
    assert invoke.index("ensure_container_env()") < invoke.index("subprocess.run(cmd)")
    assert first_use.index("ensure_container_env()") < first_use.index("install_engine_launchers.py")


# ---------------------------------------------------------------------------
# test-agents-read builds its own Python 3.12 venv (no pre-installed hermes-agent)
# ---------------------------------------------------------------------------
def test_agents_read_builds_its_own_python312_venv():
    """make test-agents-read builds its Python 3.12 venv (hermes-agent + pytest) itself and
    runs the scan and the guard's tests in it; CI only provides python3.12 and calls make."""

    # Given the Makefile and the shared CI pipeline
    mk = (REPO / "Makefile").read_text()
    job = yaml.safe_load((REPO / ".github/workflows/pipeline.yml").read_text())["jobs"]["agents-read"]

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

    # And the CI job runs no pip or pytest itself, only make
    runs = [st["run"] for st in job["steps"] if "run" in st]
    assert runs == ["make test-agents-read"]
    # And the venv lives outside the repo (the guard rejects a hermes module from the repo)
    assert "AGENTS_READ_VENV  ?= $(HOME)/.cache/llgenie/agents-read-venv" in mk
