"""Seamless TensorFold on a Mac (issue #114): picking TensorFold in `llgenie` makes it
ready whatever is on the host. Missing -> installed with its skill's install script
(`uv tool install --force 'tensorfold @ git+...@v<pinned>'`), installed at another
version -> updated to the pinned release, installed at the pinned release -> reused,
then served through its native start script.

The REAL skill code runs (engine_skills.install / detect / native_status rendering the
real skills/engines/tensorfold/SKILL.md, install_engine_launchers.ensure_native, the
`llgenie --select` path). Only the two host executables the skill calls, `uv` and
`tensorfold`, are stand-ins on PATH: they record every call and keep the installed
version in a state file, so the whole install / update / reuse cycle runs hermetically
without network or a 21 GB model."""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_skills as es  # noqa: E402
import install_engine_launchers as iel  # noqa: E402

SERVE = REPO / "scripts" / "llama_serve.py"
PINNED = es.pinned_version(es.get_skill("tensorfold"))
HUB_CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")

# `uv`: `uv tool install --force 'tensorfold @ git+<repo>.git@v<X>'` installs version X
# into the state file and drops a `tensorfold` executable into ~/.local/bin;
# `uv tool list` prints `tensorfold v<X>` like real uv. Every call is logged.
FAKE_UV = r"""#!/usr/bin/env bash
echo "uv $*" >> "$FAKE_LOG"
if [ "$1 $2" = "tool install" ]; then
  [ -n "${FAKE_UV_FAIL:-}" ] && { echo "error: network down" >&2; exit 2; }
  ver="$(printf '%s' "$*" | sed -E 's/.*@v([0-9.]+).*/\1/')"
  printf '%s' "$ver" > "$FAKE_STATE"
  mkdir -p "$HOME/.local/bin"
  cp "$FAKE_TF" "$HOME/.local/bin/tensorfold"; chmod +x "$HOME/.local/bin/tensorfold"
  echo "Installed 1 executable: tensorfold"
elif [ "$1 $2" = "tool list" ]; then
  [ -s "$FAKE_STATE" ] && printf 'tensorfold v%s\n- tensorfold\n' "$(cat "$FAKE_STATE")"
fi
exit 0
"""
FAKE_TF = r"""#!/usr/bin/env bash
echo "tensorfold $*" >> "$FAKE_LOG"
case "${1:-}" in --help) echo "usage: tensorfold serve MODEL"; exit 0 ;; esac
exit 0
"""


@pytest.fixture
def host(tmp_path, monkeypatch):
    """A Mac home with fake `uv` on PATH; `installed=` seeds an existing install."""
    home, tools = tmp_path / "home", tmp_path / "tools"
    tools.mkdir(parents=True)
    (home / ".local" / "bin").mkdir(parents=True)
    log, state = tmp_path / "calls.log", tmp_path / "tf.version"
    log.write_text("")
    for name, body in (("uv", FAKE_UV), ("tf-template", FAKE_TF)):
        p = tools / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    env = {"HOME": str(home), "FAKE_LOG": str(log), "FAKE_STATE": str(state),
           "FAKE_TF": str(tools / "tf-template"),
           "PATH": f"{tools}:/usr/bin:/bin:/usr/sbin:/sbin", "LLAMA_BACKEND": "metal"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(Path, "home", lambda: home)

    class Host:
        bindir = home / "bin"
        calls = log

        def install(self, version):
            """TensorFold already on the host at `version`."""
            state.write_text(version)
            tf = home / ".local" / "bin" / "tensorfold"
            tf.write_text(FAKE_TF)
            tf.chmod(0o755)

        def version(self):
            return state.read_text() if state.exists() else None

        def installs(self):
            return [ln for ln in log.read_text().splitlines() if ln.startswith("uv tool install")]

        def env(self):
            return {**os.environ}

    return Host()


# ---------------------------------------------------------------------------
# serving window: Metal TensorFold gets a 64K+ window (Hermes Agent's tool-use floor)
# ---------------------------------------------------------------------------
def test_metal_tensorfold_serves_a_64k_window_with_the_full_mac_budget(monkeypatch):
    """TensorFold's default Mac budget (70% of RAM) gives a 48 GB Mac a 29,696-token
    window, below Hermes Agent's 64K floor; llgenie asks for 65,536 and the full budget."""

    # Given the TensorFold skill on a 48 GB Apple-Silicon Mac, no override
    monkeypatch.delenv("LLGENIE_CONTEXT", raising=False)
    skill = es.get_skill("tensorfold")
    hw = {"os": "darwin", "arch": "arm64", "backend": "metal", "card_ram_bytes": str(48 * 2**30)}

    # When its Metal and CUDA launches are planned
    metal = es.plan(skill, "metal", hw, mode="run")
    cuda = es.plan(skill, "cuda", {**hw, "backend": "cuda"}, mode="run")

    # Then Metal serves a 65,536 window with the Mac's RAM as TensorFold's budget
    assert metal["launch"].endswith("--name llm-local --context 65536"), metal["launch"]
    assert metal["env"] == {"TENSORFOLD_MEMORY_LIMIT_GB": "48"}

    # And CUDA keeps TensorFold's own sizing (no Metal-only flag or env)
    assert "--context" not in cuda["launch"] and "TENSORFOLD_MEMORY_LIMIT_GB" not in cuda["env"]


@pytest.mark.parametrize("value,tail", [("131072", "--name llm-local --context 131072"),
                                        ("0", "--name llm-local")])
def test_llgenie_context_overrides_the_tensorfold_window(monkeypatch, value, tail):
    # Given LLGENIE_CONTEXT set by the user
    monkeypatch.setenv("LLGENIE_CONTEXT", value)

    # When the Metal launch is planned
    p = es.plan(es.get_skill("tensorfold"), "metal",
                {"os": "darwin", "backend": "metal", "card_ram_bytes": str(64 * 2**30)}, mode="run")

    # Then that window is passed to TensorFold; 0 leaves --context out, so TensorFold sizes
    #      the window to its budget (TensorFold's own `--context 0` means unlimited on Metal)
    assert p["launch"].rstrip().endswith(tail), p["launch"]
    assert "--context 0" not in p["launch"]
    assert p["env"]["TENSORFOLD_MEMORY_LIMIT_GB"] == "64"


# ---------------------------------------------------------------------------
# native_status: the three states the picker shows and ensure acts on
# ---------------------------------------------------------------------------
def test_pinned_version_comes_from_the_skill():
    # Given the TensorFold and llama.cpp skills

    # When their pinned release is read
    tf, lc = es.get_skill("tensorfold"), es.get_skill("llama.cpp")

    # Then TensorFold pins its tagged release and a branch-tracking skill pins none
    assert es.pinned_version(tf) == str(tf["version"]).lstrip("v") == PINNED
    assert es.pinned_version(lc) is None


@pytest.mark.parametrize("seed,state", [(None, "missing"), ("0.6.4", "outdated"), (PINNED, "current")])
def test_native_status_missing_outdated_current(host, seed, state):
    # Given TensorFold absent, at an older release, or at the pinned release
    if seed:
        host.install(seed)

    # When its native state is read through the skill's real detect
    st = iel.native_state("tensorfold")

    # Then it is missing / outdated / current, with the installed and wanted versions
    assert st == {"state": state, "installed": seed, "wanted": PINNED}


# ---------------------------------------------------------------------------
# ensure_native: install / update / reuse through the skill's install script
# ---------------------------------------------------------------------------
def test_missing_tensorfold_is_installed_with_its_skill_install_script(host, capsys):
    # Given a Mac without TensorFold
    assert host.version() is None

    # When llgenie ensures TensorFold for the pick
    rc = iel.ensure_native(host.bindir, "tensorfold")

    # Then it ran the skill's exact install step, the pinned tag, once
    out = capsys.readouterr().out
    assert rc == 0, out
    assert host.installs() == [
        f"uv tool install --force tensorfold @ git+https://github.com/ashhart/TensorFold.git@v{PINNED}"]
    assert "not installed -> installing" in out

    # And TensorFold is now current and its native start script exists
    assert host.version() == PINNED
    script = host.bindir / "llgenie-engine-tensorfold"
    assert os.access(script, os.X_OK) and "serve tensorfold --backend metal" in script.read_text()


def test_outdated_tensorfold_is_updated_to_the_pinned_release(host, capsys):
    # Given TensorFold installed at an older release
    host.install("0.6.4")

    # When llgenie ensures TensorFold
    rc = iel.ensure_native(host.bindir, "tensorfold")

    # Then it reinstalls the pinned release with the same skill step
    out = capsys.readouterr().out
    assert rc == 0, out
    assert f"installed 0.6.4 != pinned {PINNED} -> updating" in out
    assert len(host.installs()) == 1 and host.installs()[0].endswith(f"@v{PINNED}")
    assert host.version() == PINNED


def test_newer_unpinned_tensorfold_is_brought_back_to_the_pinned_release(host):
    """A newer release than the skill pins is not what CI tested: llgenie installs the pin."""

    # Given TensorFold installed at a newer, untested release
    host.install("9.9.9")

    # When llgenie ensures TensorFold
    rc = iel.ensure_native(host.bindir, "tensorfold")

    # Then it is back at the pinned release
    assert rc == 0 and host.version() == PINNED


def test_current_tensorfold_is_reused_without_reinstalling(host, capsys):
    # Given TensorFold at the pinned release
    host.install(PINNED)

    # When llgenie ensures TensorFold twice
    assert iel.ensure_native(host.bindir, "tensorfold") == 0
    assert iel.ensure_native(host.bindir, "tensorfold") == 0

    # Then nothing is installed, and the start script is written
    assert host.installs() == []
    assert "(current)" in capsys.readouterr().out
    assert (host.bindir / "llgenie-engine-tensorfold").exists()


def test_install_then_reuse_installs_exactly_once(host):
    # Given a Mac without TensorFold

    # When llgenie ensures it three times (first pick, then later picks)
    for _ in range(3):
        assert iel.ensure_native(host.bindir, "tensorfold") == 0

    # Then the skill's install step ran exactly once
    assert len(host.installs()) == 1


def test_a_failed_install_fails_loudly_and_writes_no_start_script(host, monkeypatch, capsys):
    # Given a Mac without TensorFold whose install fails (e.g. no network)
    monkeypatch.setenv("FAKE_UV_FAIL", "1")

    # When llgenie ensures TensorFold
    rc = iel.ensure_native(host.bindir, "tensorfold")

    # Then it fails non-zero, says so, and leaves no start script to exec
    assert rc != 0
    assert "FAIL tensorfold/metal" in capsys.readouterr().out
    assert not (host.bindir / "llgenie-engine-tensorfold").exists()


def test_detect_finds_a_uv_tool_install_outside_path(host, monkeypatch):
    """`uv tool install` puts tensorfold in ~/.local/bin, which a fresh macOS shell
    often lacks on PATH: llgenie must still see the install and not reinstall it."""

    # Given TensorFold at the pinned release in ~/.local/bin, which is not on PATH
    host.install(PINNED)
    assert str(Path.home() / ".local" / "bin") not in os.environ["PATH"]

    # When llgenie ensures it
    rc = iel.ensure_native(host.bindir, "tensorfold")

    # Then it is recognised as current, not reinstalled
    assert rc == 0 and host.installs() == []


# ---------------------------------------------------------------------------
# the llgenie pick: the state is shown, and the pick makes TensorFold ready
# ---------------------------------------------------------------------------
def _llgenie(host, tmp_path, *args):
    env = {**os.environ, "LLAMA_MODELS_ROOT": str(tmp_path / "models"),
           "LLAMA_RAM_BYTES": str(48 * 2**30), "LLGENIE_SYSTEM_RAM_BYTES": str(48 * 2**30),
           "XDG_CACHE_HOME": str(HUB_CACHE)}
    env.pop("LLGENIE_REGISTRY_SRC", None)
    return subprocess.run([sys.executable, str(SERVE), *args], env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=600)


@pytest.mark.parametrize("seed,label", [
    (None, f"(installs {PINNED} on pick)"),
    ("0.6.4", f"(installed 0.6.4 -> updates to {PINNED} on pick)"),
    (PINNED, f"(installed {PINNED})"),
])
def test_select_shows_what_picking_tensorfold_will_do(host, tmp_path, seed, label):
    # Given TensorFold absent / outdated / current on a 48 GB Mac
    if seed:
        host.install(seed)

    # When `llgenie --select 1 --dry` plans the pick (Qwen3.8-27B on TensorFold)
    r = _llgenie(host, tmp_path, "--select", "1", "--dry")

    # Then the Engine line says whether TensorFold is installed, updated or reused
    assert r.returncode == 0, r.stderr
    assert f"Engine : TensorFold [metal]" in r.stdout
    engine_line = next(ln for ln in r.stdout.splitlines() if ln.startswith("Engine :"))
    assert engine_line.endswith(label), engine_line

    # And a dry run never installs anything
    assert host.installs() == []


def test_llgenie_pick_installs_tensorfold_then_execs_its_start_script(host, tmp_path):
    """The whole seamless path without the 21 GB model: a local TensorFold checkpoint
    dir, `llgenie --select 1 --engine tensorfold`, no TensorFold on the host. llgenie
    installs TensorFold with its skill and execs the native start script, which serves
    through the skill's frozen launch (`tensorfold serve <dir> ... --name llm-local`)."""

    # Given a Mac without TensorFold, and Qwen3.8-27B's TensorFold checkpoint already local
    sys.path.insert(0, str(REPO / "scripts"))
    import model_engine_pick as mp
    os.environ.pop("LLGENIE_REGISTRY_SRC", None)
    row = next(r for r in mp.offer(mp.load_registry(), "metal", 48, root=tmp_path / "models", ram_gb=48)
               if r["model"]["name"] == "Qwen3.8-27B")
    plan = mp.engine_plan(row, row["engines"][0])
    ckpt = tmp_path / "models" / plan["repo"].replace("/", "__")
    ckpt.mkdir(parents=True)
    (ckpt / "config.json").write_text('{"model_type": "qwen3_5"}')
    (ckpt / "model.safetensors").write_bytes(b"\0" * 16)

    # When the user picks model 1 with TensorFold (port not served: the fake exits at once)
    r = _llgenie(host, tmp_path, "--select", "1", "--engine", "tensorfold", "--port", "18999")

    # Then TensorFold was installed with the skill's step, at the pinned tag
    assert host.installs() == [
        f"uv tool install --force tensorfold @ git+https://github.com/ashhart/TensorFold.git@v{PINNED}"], r.stdout + r.stderr
    assert host.version() == PINNED

    # And llgenie exec'd the native start script, which launched `tensorfold serve` on the local checkpoint
    calls = host.calls.read_text()
    assert f"tensorfold serve {ckpt}" in calls and "--port 18999" in calls and "--name llm-local" in calls, \
        r.stdout + r.stderr + calls


def test_interactive_llgenie_lists_pick_qwen38_27b_then_tensorfold_which_installs_and_serves(host, tmp_path):
    """The INTERACTIVE path, hermetic (make test-unit, every CI run): plain `llgenie` in a
    pty, no --select. The test reads the printed trend list, types Qwen3.8-27B's number,
    reads its engine list, types TensorFold's number; TensorFold is missing, so the pick
    installs it with the skill's step and serves the model's TensorFold checkpoint."""

    # Given a 48 GB Mac without TensorFold, and Qwen3.8-27B's TensorFold checkpoint local
    import re
    sys.path.insert(0, str(REPO / "tests"))
    sys.path.insert(0, str(REPO / "scripts"))
    from ptydrive import Pty
    import model_engine_pick as mp
    os.environ.pop("LLGENIE_REGISTRY_SRC", None)
    row = next(r for r in mp.offer(mp.load_registry(), "metal", 48, root=tmp_path / "models", ram_gb=48)
               if r["model"]["name"] == "Qwen3.8-27B")
    ckpt = tmp_path / "models" / mp.engine_plan(row, row["engines"][0])["repo"].replace("/", "__")
    ckpt.mkdir(parents=True)
    (ckpt / "config.json").write_text('{"model_type": "qwen3_5"}')
    (ckpt / "model.safetensors").write_bytes(b"\0" * 16)
    env = {**os.environ, "LLAMA_MODELS_ROOT": str(tmp_path / "models"), "TERM": "xterm",
           "LLAMA_RAM_BYTES": str(48 * 2**30), "LLGENIE_SYSTEM_RAM_BYTES": str(48 * 2**30),
           "XDG_CACHE_HOME": str(HUB_CACHE)}

    # When the user runs plain `llgenie` and picks from the two printed lists
    p = Pty([sys.executable, str(SERVE), "--port", "18998"], env, cwd=str(tmp_path))
    try:
        p.expect(r"Pick model \[1\]: ", 300)
        models = re.findall(r"^\s+(\d+)\.\s{2}(.+?)\s+(?:trending|recent|stale)\s+trend", p.out, re.M)
        n_model = next(n for n, name in models if name.strip() == "Qwen3.8-27B")
        p.send(n_model)
        p.expect(r"Pick inference server \[1\]: ", 300)
        menu = p.out.split("Engines for Qwen3.8-27B", 1)[1]
        engines = re.findall(r"^\s+(\d+)\.\s+(.+?)\s+\[(\w+)\](.*)$", menu, re.M)
        n_engine, _, variant, tail = next(e for e in engines if e[1].strip() == "TensorFold")
        p.send(n_engine)
        rc = p.wait(300)
    finally:
        p.close()

    # Then Qwen3.8-27B was in the trend list and TensorFold in its engine list, native metal, "installs on pick"
    assert models, p.out[-3000:]
    assert variant == "metal" and tail.rstrip().endswith(f"(installs {PINNED} on pick)"), tail

    # And the pick installed the pinned TensorFold with the skill's step
    assert host.installs() == [
        f"uv tool install --force tensorfold @ git+https://github.com/ashhart/TensorFold.git@v{PINNED}"], p.out[-3000:]

    # And served Qwen3.8-27B's TensorFold checkpoint through the native start script
    calls = host.calls.read_text()
    assert rc == 0, p.out[-3000:]
    assert f"tensorfold serve {ckpt}" in calls and "--port 18998" in calls and "--name llm-local" in calls, \
        p.out[-3000:] + calls
