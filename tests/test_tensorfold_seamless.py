"""Seamless TensorFold on a Mac (issue #114): picking TensorFold in `llgenie` makes it
ready whatever is on the host. Missing -> installed with its skill's install
script, installed at another version -> updated to the pinned release, installed
at the pinned release -> reused, then served through its native start script.

The module is INSTALL-KIND AGNOSTIC (issue #386): it drives whatever install the
skill declares. On main the tensorfold skill is a pip/uv install
(`uv tool install --force 'tensorfold @ git+...@v<pinned>'`); after the
release-archive bump (engine_bump._apply_release_archive) it is
mkdir/curl/shasum/tar/ln steps unpacking into {prefix}/{version} with
{prefix}/current -> {version}. Both reach missing / outdated / current through
the REAL engine_skills.native_status and install_engine_launchers.ensure_native,
and the picker labels hold for both. The tests run the "live" skill (pip on main,
archive after a bump) and a synthesized archive-kind skill side by side, so the
archive shape is proven even while main's skill is still pip.

The REAL skill code runs (engine_skills.install / detect / native_status rendering
the real skills/engines/tensorfold/SKILL.md, install_engine_launchers.ensure_native,
the `llgenie --select` path). Only the host executables the skill shells out to
(`uv`, `tensorfold`/`tensorfold-native`, and for the archive kind `curl`, `shasum`,
`tar`) are stand-ins on PATH: they record every call, log it, and keep the installed
version in a state file, so the whole install / update / reuse cycle runs hermetically
without network or a 21 GB model. No product code is mocked; no test is skipped.
"""
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
import hf_auth  # noqa: E402
import install_engine_launchers as iel  # noqa: E402
import llgenie_serve  # noqa: E402

SERVE = REPO / "scripts" / "llgenie_serve.py"
PINNED = es.pinned_version(es.get_skill("tensorfold"))
HUB_CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")

LIVE, ARCHIVE = "live", "archive"
# The release-archive shape engine_bump rewrites the skill to (issue #386): the
# binary goes through {prefix}/current (a symlink to the unpacked release) so
# detect asks the INSTALLED binary its version, and binary_flags documents both
# --help and --version.
ARCHIVE_PINNED = "1.1.8"
_ARCHIVE_INSTALL = "\n".join(
    '    - "' + step.replace('"', '\\"') + '"'
    for step in (
        "mkdir -p {prefix}/{version}",
        "curl -fsSL -o {prefix}/tensorfold-{version}-macos-arm64.tar.gz {repo}/releases/download/v{version}/tensorfold-{version}-macos-arm64.tar.gz",
        "curl -fsSL -o {prefix}/tensorfold-{version}-macos-arm64.tar.gz.sha256 {repo}/releases/download/v{version}/tensorfold-{version}-macos-arm64.tar.gz.sha256",
        "cd {prefix} && shasum -a 256 -c tensorfold-{version}-macos-arm64.tar.gz.sha256",
        "tar -xzf {prefix}/tensorfold-{version}-macos-arm64.tar.gz -C {prefix}/{version} --strip-components=1",
        'exe=$(find {prefix}/{version}/bin -maxdepth 1 -type f -perm -111); set -- $exe; ln -sfn "$1" {prefix}/{version}/bin/{id}',
        "ln -sfn {prefix}/{version} {prefix}/current",
    )
)
ARCHIVE_SKILL = f"""---
name: engine-tensorfold
description: "Use when installing TensorFold from a release archive (issue #386)"
engine: "TensorFold"
id: tensorfold
repo: https://github.com/ashhart/TensorFold
ref: v{ARCHIVE_PINNED}
ref_kind: tag
version: v{ARCHIVE_PINNED}
pinned: 609ca419abecebdc5a059498a613680bd3aa847f
verified: "2026-10-05"
license: Apache-2.0
servable: true
backends: [metal, cuda]
os: [darwin, linux]
formats: [mlx-safetensors]
# The derivation drops the pip tool from prereqs when the archive steps do not call it
# (issue #386): a leftover `uv` would block the install on a host that has none.
prereqs:
  cuda: [nvidia-smi, nvcc]
install:
  metal:
{_ARCHIVE_INSTALL}
  cuda:
    - "mkdir -p {{prefix}}/{{version}}"
    - "curl -fsSL -o {{prefix}}/tensorfold-{{version}}-linux-x86_64.tar.gz {{repo}}/releases/download/v{{version}}/tensorfold-{{version}}-linux-x86_64.tar.gz"
    - "curl -fsSL -o {{prefix}}/tensorfold-{{version}}-linux-x86_64.tar.gz.sha256 {{repo}}/releases/download/v{{version}}/tensorfold-{{version}}-linux-x86_64.tar.gz.sha256"
    - "cd {{prefix}} && sha256sum -c tensorfold-{{version}}-linux-x86_64.tar.gz.sha256"
    - "tar -xzf {{prefix}}/tensorfold-{{version}}-linux-x86_64.tar.gz -C {{prefix}}/{{version}} --strip-components=1"
    - 'exe=$(find {{prefix}}/{{version}}/bin -maxdepth 1 -type f -perm -111); set -- $exe; ln -sfn "$1" {{prefix}}/{{version}}/bin/{{id}}'
    - "ln -sfn {{prefix}}/{{version}} {{prefix}}/current"
binary: "{{prefix}}/current/bin/{{id}}"
binary_flags: ["--help", "--version"]
detect: "{{binary}} --version"
launch:
  common: "{{binary}} serve {{model}} --host {{host}} --port {{port}} --name {{alias}}"
  metal: "{{context_flag}}"
env:
  metal:
    TENSORFOLD_MEMORY_LIMIT_GB: "{{ram_gib}}"
health: "GET /v1/models"
alias_mode: flag
container:
  cuda:
    base: "nvcr.io/nvidia/pytorch:26.07-py3"
---

# body
"""

PIP = "pip"
# The pip shape a release-archive bump starts FROM (and the shape main's skill still
# has). It is SYNTHESIZED for the same reason the archive one is: a test that needs "the
# pip kind" must not depend on which kind the repo's own skill happens to declare, or it
# starts failing the moment a bump moves TensorFold to its archives (issue #389).
PIP_PINNED = "0.6.5"
PIP_SKILL = f"""---
name: engine-tensorfold
description: "Use when installing TensorFold from a pip package (issue #389)"
engine: "TensorFold"
id: tensorfold
repo: https://github.com/ashhart/TensorFold
ref: v{PIP_PINNED}
ref_kind: tag
version: v{PIP_PINNED}
pinned: 609ca419abecebdc5a059498a613680bd3aa847f
verified: "2026-10-05"
license: Apache-2.0
servable: true
backends: [metal, cuda]
os: [darwin, linux]
formats: [mlx-safetensors]
prereqs:
  common: [uv]
  cuda: [nvidia-smi, nvcc]
install:
  metal:
    - "uv tool install --force 'tensorfold @ git+{{repo}}.git@v{{version}}'"
  cuda:
    - "uv pip install --system --break-system-packages 'tensorfold @ git+{{repo}}.git@v{{version}}'"
binary: "tensorfold"
binary_flags: ["--help"]
detect: "{{binary}} --help > /dev/null && uv tool list | grep '^tensorfold '"
launch:
  common: "{{binary}} serve {{model}} --host {{host}} --port {{port}} --name {{alias}}"
  metal: "{{context_flag}}"
env:
  metal:
    TENSORFOLD_MEMORY_LIMIT_GB: "{{ram_gib}}"
health: "GET /v1/models"
alias_mode: flag
container:
  cuda:
    base: "nvcr.io/nvidia/pytorch:26.07-py3"
---

# body
"""


# `uv`: `uv tool install --force 'tensorfold @ git+<repo>.git@v<X>'` installs version X
# into the state file and drops a `tensorfold` executable into ~/.local/bin;
# `uv tool list` prints `tensorfold v<X>` like real uv. Every call is logged.
# Any failing external tool respects FAKE_INSTALL_FAIL (the failed-install test).
FAKE_UV = r"""#!/usr/bin/env bash
echo "uv $*" >> "$FAKE_LOG"
if [ "$1 $2" = "tool install" ]; then
  [ -n "${FAKE_INSTALL_FAIL:-}" ] && { echo "error: network down" >&2; exit 2; }
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
# `tensorfold` (pip kind) and `tensorfold-native` (archive kind) are the SAME script:
# --help prints usage (the pip skill's detect asks it), --version prints the release
# recorded in the shared state file (the archive skill's detect and native_status ask
# it). A copy is dropped into the install layout by fake uv / fake tar.
FAKE_TF = r"""#!/usr/bin/env bash
echo "tensorfold $*" >> "$FAKE_LOG"
case "${1:-}" in
  --help) echo "usage: tensorfold serve MODEL"; exit 0 ;;
  --version) [ -s "$FAKE_STATE" ] && cat "$FAKE_STATE"; echo; exit 0 ;;
esac
exit 0
"""
# The archive install downloads into `-o <file>` (curl -fsSL -o <file> <url>).
FAKE_CURL = r"""#!/usr/bin/env bash
echo "curl $*" >> "$FAKE_LOG"
[ -n "${FAKE_INSTALL_FAIL:-}" ] && { echo "error: download failed" >&2; exit 7; }
out=""
prev=""
for arg in "$@"; do
  [ "$prev" = "-o" ] && out="$arg"
  prev="$arg"
done
[ -n "$out" ] && : > "$out"
exit 0
"""
FAKE_SHASUM = r"""#!/usr/bin/env bash
echo "shasum $*" >> "$FAKE_LOG"
[ -n "${FAKE_INSTALL_FAIL:-}" ] && { echo "checksum mismatch" >&2; exit 1; }
exit 0
"""
# `tar -xzf <archive> -C <dir> --strip-components=1` unpacks bin/tensorfold-native
# (upstream's name, a copy of the fake ~tensorfold~ script) plus VERSION, and records
# the release in the shared state file so the installed binary's `--version` answers
# the release that was actually unpacked (what native_status asks).
FAKE_TAR = r"""#!/usr/bin/env bash
echo "tar $*" >> "$FAKE_LOG"
d=""
prev=""
for arg in "$@"; do
  [ "$prev" = "-C" ] && d="$arg"
  prev="$arg"
done
if [ -n "$d" ]; then
  mkdir -p "$d/bin"
  cp "$FAKE_TF" "$d/bin/tensorfold-native"; chmod +x "$d/bin/tensorfold-native"
  ver="$(printf '%s' "$*" | sed -E 's/.*tensorfold-([0-9.]+)-macos.*/\1/')"
  [ -n "$ver" ] && printf '%s' "$ver" > "$FAKE_STATE"
  printf '%s' "${ver:-unknown}" > "$d/VERSION"
fi
exit 0
"""

_TOOL_FAKES = {"uv": FAKE_UV, "curl": FAKE_CURL, "shasum": FAKE_SHASUM, "tar": FAKE_TAR}


@pytest.fixture
def host(tmp_path, monkeypatch):
    """A Mac home with the skill's external tools on PATH; `installed=` seeds an install."""
    home, tools = tmp_path / "home", tmp_path / "tools"
    engines = tmp_path / "engines"
    tools.mkdir(parents=True)
    (home / ".local" / "bin").mkdir(parents=True)
    log, state = tmp_path / "calls.log", tmp_path / "tf.version"
    log.write_text("")
    for name, body in _TOOL_FAKES.items():
        p = tools / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    tf_template = tools / "tf-template"
    tf_template.write_text(FAKE_TF)
    tf_template.chmod(tf_template.stat().st_mode | stat.S_IEXEC)
    env = {"HOME": str(home), "FAKE_LOG": str(log), "FAKE_STATE": str(state),
           "FAKE_TF": str(tf_template), "LLGENIE_ENGINES": str(engines),
           "PATH": f"{tools}:/usr/bin:/bin:/usr/sbin:/sbin", "LLAMA_BACKEND": "metal"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(Path, "home", lambda: home)

    class Host:
        bindir = home / "bin"
        calls = log
        tool_dir = tools
        tmp = tmp_path

        def install(self, version):
            """TensorFold already on the host at `version`, reachable by BOTH
            install kinds: ~/.local/bin/tensorfold (pip/uv) and the {prefix}/current
            layout the archive install uses. The version they report comes from the
            one shared state file."""
            state.write_text(version)
            tf = home / ".local" / "bin" / "tensorfold"
            tf.write_text(FAKE_TF)
            tf.chmod(0o755)
            prefix = engines / "tensorfold"
            verdir = prefix / version
            (verdir / "bin").mkdir(parents=True, exist_ok=True)
            native = verdir / "bin" / "tensorfold-native"
            native.write_text(FAKE_TF)
            native.chmod(0o755)
            (verdir / "VERSION").write_text(version)
            (verdir / "bin" / "tensorfold").symlink_to("tensorfold-native")
            cur = prefix / "current"
            if cur.is_symlink() or cur.exists():
                cur.unlink()
            cur.symlink_to(verdir, target_is_directory=True)

        def version(self):
            return state.read_text() if state.exists() else None

        def installs(self):
            """How many real install batches ran, whatever the install kind: each
            ensure_native install runs the skill's steps, which is one `uv tool
            install` (pip) or one `tar -xzf` (archive)."""
            lines = log.read_text().splitlines() if log.exists() else []
            steps = " ".join(str(x) for x in es._flatten((es.get_skill("tensorfold").get("install") or {})))
            return [ln for ln in lines
                    if ln.startswith("tar -xzf" if "tar -xzf" in steps else "uv tool install")]

        def env(self):
            return {**os.environ}

    return Host()


@pytest.fixture
def tf(host, monkeypatch, request):
    """`(kind, pinned)` for the skill the tests drive.

    `live` runs the real repo skill (pip on main, archive after a bump); `archive` and
    `pip` rewrite it to a SYNTHESIZED skill of that kind, so both kinds are proven
    whatever main's skill currently declares (issue #389).
    """
    kind = request.param
    if kind in (ARCHIVE, PIP):
        d = host.tmp / "skills" / "engines" / "tensorfold"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(ARCHIVE_SKILL if kind == ARCHIVE else PIP_SKILL)
        monkeypatch.setattr(es, "SKILLS_DIR", d.parent)
        pinned = ARCHIVE_PINNED if kind == ARCHIVE else PIP_PINNED
    else:
        pinned = PINNED
    return {"kind": kind, "pinned": pinned}


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


@pytest.mark.parametrize("seed,state", [(None, "missing"), ("0.6.4", "outdated"), ("current-seed", "current")])
@pytest.mark.parametrize("tf", [LIVE, ARCHIVE], indirect=True)
def test_native_status_missing_outdated_current(host, tf, seed, state):
    # Given TensorFold absent, at an older release, or at the pinned release
    if seed:
        host.install(tf["pinned"] if seed == "current-seed" else seed)

    # When its native state is read through the skill's real detect
    st = iel.native_state("tensorfold")

    # Then it is missing / outdated / current, with the installed and wanted versions
    want_installed = {"missing": None, "outdated": "0.6.4", "current": tf["pinned"]}[state]
    assert st == {"state": state, "installed": want_installed, "wanted": tf["pinned"]}


# ---------------------------------------------------------------------------
# ensure_native: install / update / reuse through the skill's install script
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("tf", [LIVE, ARCHIVE], indirect=True)
def test_missing_tensorfold_is_installed_with_its_skill_install_script(host, capsys, tf):
    # Given a Mac without TensorFold
    assert host.version() is None

    # When llgenie ensures TensorFold for the pick
    rc = iel.ensure_native(host.bindir, "tensorfold")

    # Then it ran the skill's install steps once, and TensorFold is at the pinned release
    out = capsys.readouterr().out
    assert rc == 0, out
    assert len(host.installs()) == 1
    assert "not installed -> installing" in out

    # And TensorFold is now current and its native start script exists
    assert host.version() == tf["pinned"]
    script = host.bindir / "llgenie-engine-tensorfold"
    assert os.access(script, os.X_OK) and "serve tensorfold --backend metal" in script.read_text()


@pytest.mark.parametrize("tf", [LIVE, ARCHIVE], indirect=True)
def test_outdated_tensorfold_is_updated_to_the_pinned_release(host, capsys, tf):
    # Given TensorFold installed at an older release
    host.install("0.6.4")

    # When llgenie ensures TensorFold
    rc = iel.ensure_native(host.bindir, "tensorfold")

    # Then it reinstalls the pinned release with the skill's steps
    out = capsys.readouterr().out
    assert rc == 0, out
    assert f"installed 0.6.4 != pinned {tf['pinned']} -> updating" in out
    assert len(host.installs()) == 1
    assert host.version() == tf["pinned"]


@pytest.mark.parametrize("tf", [LIVE, ARCHIVE], indirect=True)
def test_newer_unpinned_tensorfold_is_brought_back_to_the_pinned_release(host, tf):
    """A newer release than the skill pins is not what CI tested: llgenie installs the pin."""

    # Given TensorFold installed at a newer, untested release
    host.install("9.9.9")

    # When llgenie ensures TensorFold
    rc = iel.ensure_native(host.bindir, "tensorfold")

    # Then it is back at the pinned release
    assert rc == 0 and host.version() == tf["pinned"]


@pytest.mark.parametrize("tf", [LIVE, ARCHIVE], indirect=True)
def test_current_tensorfold_is_reused_without_reinstalling(host, capsys, tf):
    # Given TensorFold at the pinned release
    host.install(tf["pinned"])

    # When llgenie ensures TensorFold twice
    assert iel.ensure_native(host.bindir, "tensorfold") == 0
    assert iel.ensure_native(host.bindir, "tensorfold") == 0

    # Then nothing is installed, and the start script is written
    assert host.installs() == []
    assert "(current)" in capsys.readouterr().out
    assert (host.bindir / "llgenie-engine-tensorfold").exists()


@pytest.mark.parametrize("tf", [LIVE, ARCHIVE], indirect=True)
def test_install_then_reuse_installs_exactly_once(host, tf):
    # Given a Mac without TensorFold

    # When llgenie ensures it three times (first pick, then later picks)
    for _ in range(3):
        assert iel.ensure_native(host.bindir, "tensorfold") == 0

    # Then the skill's install steps ran exactly once
    assert len(host.installs()) == 1


@pytest.mark.parametrize("tf", [LIVE, ARCHIVE], indirect=True)
def test_a_failed_install_fails_loudly_and_writes_no_start_script(host, monkeypatch, capsys, tf):
    # Given a Mac without TensorFold whose install fails (e.g. no network)
    monkeypatch.setenv("FAKE_INSTALL_FAIL", "1")

    # When llgenie ensures TensorFold
    rc = iel.ensure_native(host.bindir, "tensorfold")

    # Then it fails non-zero, says so, and leaves no start script to exec
    assert rc != 0
    assert "FAIL tensorfold/metal" in capsys.readouterr().out
    assert not (host.bindir / "llgenie-engine-tensorfold").exists()


@pytest.mark.parametrize("tf", [PIP, ARCHIVE], indirect=True)
def test_a_host_without_uv_only_blocks_the_pip_install(host, monkeypatch, capsys, tf):
    """The release-archive install needs no uv, so it must not be refused without one.

    The derivation drops the pip tool from `prereqs` when its steps do not call it
    (issue #386). A leftover `uv` is a false precondition: `check(mode="native")` would
    refuse an install that never invokes uv. The pip kind must still demand it.
    """
    import shutil as _shutil

    # Given a Mac whose PATH carries the skill's external tools but no uv. Every entry
    # that provides uv is dropped; the rest is KEPT, so sysctl (/usr/sbin), tar and the
    # rest of the host still resolve — a PATH of "just the fakes" brakes hardware
    # detection on macOS, not the install.
    novu = host.tmp / "novu"
    novu.mkdir()
    for name in ("curl", "shasum", "tar"):
        (novu / name).symlink_to(host.tool_dir / name)
    rest = [d for d in os.environ.get("PATH", "").split(os.pathsep)
            if d and not (Path(d) / "uv").exists() and Path(d).resolve() != host.tool_dir.resolve()]
    monkeypatch.setenv("PATH", os.pathsep.join([str(novu), *rest]))
    assert _shutil.which("uv") is None, "this test needs a PATH without uv"

    # When llgenie ensures TensorFold for the pick
    rc = iel.ensure_native(host.bindir, "tensorfold")
    captured = capsys.readouterr()
    out = captured.out + captured.err   # blockers are printed on stderr

    # Then the archive kind installs (curl/tar only), and the pip kind still demands uv
    if tf["kind"] == ARCHIVE:
        assert rc == 0, out
        assert host.version() == tf["pinned"]
        assert "missing prerequisite" not in out, out
    else:
        assert rc != 0, out
        assert "missing prerequisite: uv" in out, out


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
                          capture_output=True, text=True,
                          timeout=hf_auth.TOP_TIER_DRY_RUN_TIMEOUT)


def _state_label(state: str, installed: str | None, wanted: str | None) -> str:
    """The picker's Engine-line tail for a metal engine, from the product's own
    `llgenie_serve._STATE_LABEL` (never a copy that could drift from it). The
    subprocess pick tests below lock the same string end to end."""
    return llgenie_serve._STATE_LABEL[state].format(
        installed=installed or "", wanted=wanted or "latest").rstrip()


@pytest.mark.parametrize("tf", [LIVE, ARCHIVE], indirect=True)
@pytest.mark.parametrize("seed,state", [(None, "missing"), ("0.6.4", "outdated"), ("current-seed", "current")])
def test_archive_kind_picker_labels(host, tf, seed, state):
    """The picker label for every native state holds for the archive kind too
    (the subprocess pick tests below lock it for the live/pip kind)."""
    # Given TensorFold absent / outdated / current under the release-archive skill
    if seed:
        host.install(tf["pinned"] if seed == "current-seed" else seed)

    # When its native state is read the way the picker shows it
    st = iel.native_state("tensorfold")

    # Then the label says install / update / reuse, exactly like the pip kind
    want_installed = {"missing": None, "outdated": "0.6.4", "current": tf["pinned"]}[state]
    wanted_tail = {"missing": f"(installs {tf['pinned']} on pick)",
                   "outdated": f"(installed 0.6.4 -> updates to {tf['pinned']} on pick)",
                   "current": f"(installed {tf['pinned']})"}[state]
    assert _state_label(st["state"], st["installed"], st["wanted"]) == f"  {wanted_tail}"
    assert st == {"state": state, "installed": want_installed, "wanted": tf["pinned"]}



def _tensorfold_row(tmp_path):
    """The first servable row on a 48 GB Mac that TensorFold itself can serve, and its
    1-based position in the printed list. No model name is pinned (issue #693): whichever
    row the store gives TensorFold a checkpoint for is the one these seams exercise."""
    import model_engine_pick as mp
    os.environ.pop("LLGENIE_REGISTRY_SRC", None)
    rows = mp.offer(mp.load_registry(), "metal", 48, root=tmp_path / "models", ram_gb=48)
    pickable = [r for r in rows if not r["why"]]
    served_by_tf = [r for r in pickable if any(e["id"] == "tensorfold" for e in r["engines"])]
    assert served_by_tf, "no servable row on a 48 GB Mac is served by TensorFold"
    row = served_by_tf[0]
    eng = next(e for e in row["engines"] if e["id"] == "tensorfold")
    # `--select N` numbers the PICKABLE list, and `--engine` narrows that list to the rows
    # the engine can serve — so the position depends on which form the test drives
    return row, eng, pickable.index(row) + 1, served_by_tf.index(row) + 1

@pytest.mark.parametrize("seed,label", [
    (None, f"(installs {PINNED} on pick)"),
    ("0.6.4", f"(installed 0.6.4 -> updates to {PINNED} on pick)"),
    (PINNED, f"(installed {PINNED})"),
])
def test_select_shows_what_picking_tensorfold_will_do(host, tmp_path, seed, label):
    # Given TensorFold absent / outdated / current on a 48 GB Mac
    if seed:
        host.install(seed)

    # When `llgenie --select N --dry --engine tensorfold` plans the pick for the row
    # TensorFold serves on this host (no model pinned — #693)
    _, _, _, n = _tensorfold_row(tmp_path)
    r = _llgenie(host, tmp_path, "--select", str(n), "--engine", "tensorfold", "--dry")

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
    row, tf_engine, _, n = _tensorfold_row(tmp_path)
    plan = mp.engine_plan(row, tf_engine)
    ckpt = tmp_path / "models" / plan["repo"].replace("/", "__")
    ckpt.mkdir(parents=True)
    (ckpt / "config.json").write_text('{"model_type": "qwen3_5"}')
    (ckpt / "model.safetensors").write_bytes(b"\0" * 16)

    # When the user picks that row with TensorFold (port not served: the fake exits at once)
    r = _llgenie(host, tmp_path, "--select", str(n), "--engine", "tensorfold", "--port", "18999")

    # Then TensorFold was installed once, by the step its skill declares, at the pinned tag
    # (the skill's declared step, not a hardcoded command: a bump may have moved it to a
    # release archive — issue #389)
    assert len(host.installs()) == 1, r.stdout + r.stderr
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
    row, tf_engine, n_all, _ = _tensorfold_row(tmp_path)
    model_name = row["model"]["name"]
    ckpt = tmp_path / "models" / mp.engine_plan(row, tf_engine)["repo"].replace("/", "__")
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
        n_model = next(n for n, name in models if name.strip() == model_name)
        p.send(n_model)
        p.expect(r"Pick inference server \[1\]: ", 300)
        menu = p.out.split(f"Engines for {model_name}", 1)[1]
        engines = re.findall(r"^\s+(\d+)\.\s+(.+?)\s+\[(\w+)\](.*)$", menu, re.M)
        n_engine, _, variant, tail = next(e for e in engines if e[1].strip() == "TensorFold")
        p.send(n_engine)
        rc = p.wait(300)
    finally:
        p.close()

    # Then Qwen3.8-27B was in the trend list and TensorFold in its engine list, native metal, "installs on pick"
    assert models, p.out[-3000:]
    assert variant == "metal" and tail.rstrip().endswith(f"(installs {PINNED} on pick)"), tail

    # And the pick installed the pinned TensorFold with the step its skill declares
    # (kind-agnostic: a bump may have moved the install to a release archive — issue #389)
    assert len(host.installs()) == 1, p.out[-3000:]

    # And served Qwen3.8-27B's TensorFold checkpoint through the native start script
    calls = host.calls.read_text()
    assert rc == 0, p.out[-3000:]
    assert f"tensorfold serve {ckpt}" in calls and "--port 18998" in calls and "--name llm-local" in calls, \
        p.out[-3000:] + calls
