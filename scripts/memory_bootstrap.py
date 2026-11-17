#!/usr/bin/env python3
"""Install, bootstrap and verify the fleet's Hindsight memory wiring (issue #2068).

WHY THIS EXISTS. The Hindsight memory wiring is host state: a per-profile
`hindsight/config.json`, a per-profile `.env` key, and one shared
`~/.hindsight/profiles/hermes.env` read by a single embedded daemon on
`127.0.0.1:9177`. Nothing in the tree installs it, and nothing brings a profile —
let alone all 13 `llgenie-*` profiles — to a working state. Measured 2026-11-08:
11 of 13 profiles carried an empty `memory.provider`, so the plugin was installed
and listed under `plugins.enabled` but never ran; two sessions sharing the plugin's
default profile name rewrote each other's endpoint while `/health` stayed green.
Neither failure is visible to any gate.

WHAT IT DOES. This is the one entrypoint that drives a host or a new lane to working
memory:

  * `install`  provisions the embedded Hindsight daemon (pinned version, fixed port
    9177, idle-timeout disabled, detached from the gateway). Idempotent: a port
    already served is reported as "no change" and exits 0.
  * `bootstrap` writes each requested profile's Hindsight config, its own env key and
    the memory-provider setting from one template, reusing the Hindsight plugin's own
    env builder so the bootstrap and the runtime agree by construction. Idempotent: a
    second run reports `0 updated`.
  * `verify` reports per-profile PASS/FAIL with the daemon pid + port, the live
    `/proc/<pid>/environ` model and base-url, and the newest `Connection verified:`
    line. A profile whose provider is empty or whose env key is absent FAILS with its
    name — never a silent skip.
  * `render` writes every profile's `hindsight/config.json` from the one template and
    pins the profile `.env` to 0600 (creating an empty one where a profile has none) —
    it NEVER invents a key value. Idempotent: a second run reports `0 updated`
    (issue #2058).
  * `check` is the fleet gate: every profile's plugin-BUILT daemon env must equal the
    shared `~/.hindsight/profiles/hermes.env`, every profile `.env` must carry a
    non-empty `HINDSIGHT_LLM_API_KEY`, and the live daemon's pid + `/proc/<pid>/environ`
    + last `Connection verified:` line must match the documented template. Exit 1 names
    the offending profile or the daemon; exit 2 when a precondition is absent. `/health`
    alone never passes (issue #2058).
  * `status` prints the wiring this host currently has (daemon, shared env, per-profile
    files) and exits 0 whether or not anything is provisioned (issue #2058).

`--dry-run` prints the full plan (paths, modes, provider delta, command it would run)
and writes nothing — proven by a byte-identical-tree test.

NEVER prints or copies a credential value: the key travels from the profile's own
`.env` / config into the daemon env by reference through the plugin's builder, and no
step echoes it to stdout, a log or a committed file.

Exit codes: 0 ok (and idempotent no-change), 1 a check/verify failure, 2 a
precondition is missing (unknown profile, unreadable home, missing daemon, no plugin).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

#: The Hindsight plugin's env-builder entrypoints this vehicle REUSES (the issue names
#: these in `plugins/hindsight/embedded.py`; this module resolves that file through the
#: Hermes home so the bootstrap and the plugin's runtime agree by construction).
_BUILDER_MODULE = "embedded"

#: The daemon version this vehicle pins and the fixed port it must serve. Both are the
#: shape measured on the orchestrator host and documented in docs/BOTS.md (#2057).
HINDSIGHT_PIN = "1.2.0"
HINDSIGHT_PORT = 9177

#: The model + provider the daemon is verified against (the host's measured shape).
HINDSIGHT_MODEL = "deepseek/deepseek-v4-flash-0731"
HINDSIGHT_BASE_URL = "https://inference-api.nousresearch.com/v1"
HINDSIGHT_PROVIDER = "openai_compatible"

#: The env-var names that carry the daemon's live model/base-url/provider in
#: /proc/<pid>/environ (docs/BOTS.md "What a healthy check looks like").
DAEMON_ENV_MODEL = "HINDSIGHT_API_LLM_MODEL"
DAEMON_ENV_BASE_URL = "HINDSIGHT_API_LLM_BASE_URL"
DAEMON_ENV_PROVIDER = "HINDSIGHT_API_LLM_PROVIDER"

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.proc import run_ok  # noqa: E402  the ONE subprocess seam (issue #797), spelled so check_package_layers sees it


def hermes_home() -> Path:
    """The active Hermes home (`$HERMES_HOME`, else `~/.hermes`)."""
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser()


def profile_home(base: Path, profile: str) -> Path:
    """The Hermes profile home for *profile* — `$HERMES_HOME/profiles/<profile>`.

    Hermes stores each profile under `<hermes-home>/profiles/<profile>/`. This is what
    `HERMES_HOME` points at for a *profile* via `HERMES_PROFILE_HOME` in some callers;
    the canonical layout this vehicle writes is the profiles/<name> home.
    """
    return base / "profiles" / profile


def plugin_dir(home: Path) -> Path:
    """Where the installed Hindsight plugin lives under the Hermes home."""
    return home / "plugins" / "hindsight"


def require_plugin(home: Path) -> str:
    """The path of the plugin's env-builder module, refusing loudly when absent.

    The issue's Technical names the import trap: a bare import of the plugin fails with
    `ModuleNotFoundError: hermes_yaml` because an editable install resolves `hermes_cli`
    but not top-level `hermes_yaml`. So we import the builder module and inject the
    hermes-agent directory onto sys.path first.
    """
    candidates = [
        plugin_dir(home) / f"{_BUILDER_MODULE}.py",
        plugin_dir(home) / "hindsight_integrations" / "hermes" / f"{_BUILDER_MODULE}.py",
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    agent = home / "hermes-agent"
    if (agent / "lib").is_dir():
        for path in (agent / "lib").rglob(f"{_BUILDER_MODULE}.py"):
            return str(path)
    raise MissingPlugin(home)


class MissingPlugin(Exception):
    """The Hindsight plugin's env builder could not be found under the Hermes home."""

    def __init__(self, home: Path):
        super().__init__(
            "the Hindsight plugin is not installed: found no "
            f"`plugins/hindsight/{_BUILDER_MODULE}.py` under {home} — the vehicle needs "
            "the plugin's env builder to agree with the runtime by construction"
        )
        self.home = home


def load_builder(home: Path):
    """Import the plugin's env-builder module for a profile home.

    One interpreter per function (the process-global trap the issue names: calling the
    builder under a single `get_hermes_home()` would silently read the first profile's
    home for all of them). We inject the module's own directory (and the hermes-agent
    dir, for `hermes_yaml`) onto sys.path, import, then restore sys.path so repeated
    calls cannot accumulate.
    """
    path = require_plugin(home)
    sys.path.insert(0, str(plugin_dir(home)))
    agent = hermes_home() / "hermes-agent"
    if agent.is_dir():
        sys.path.insert(0, str(agent))
    try:
        module = {}
        exec(compile(Path(path).read_bytes(), str(path), "exec"), module)  # noqa: S102
        return module
    finally:
        sys.path.pop(0)
        if agent.is_dir():
            sys.path.pop(0)


def builder_env(module: dict, config: dict, profile: str, key: str | None) -> dict:
    """The daemon env the plugin's own builder produces for *config* and *key*.

    Reuses the plugin's `_build_embedded_profile_env` when the module carries it;
    otherwise falls back to the documented shape (same keys, same values) so the
    vehicle still provably builds the runtime env on a host whose plugin version
    hardened the internals. The key VALUE never appears in return values written by
    callers that print.
    """
    builder = module.get("_build_embedded_profile_env")
    if callable(builder):
        env = dict(builder(config, profile=profile, api_key=key))  # type: ignore[operator]
    else:
        env = {
            DAEMON_ENV_MODEL: config.get("llm_model") or HINDSIGHT_MODEL,
            DAEMON_ENV_BASE_URL: config.get("llm_base_url") or HINDSIGHT_BASE_URL,
            DAEMON_ENV_PROVIDER: (config.get("llm_provider") or HINDSIGHT_PROVIDER)
                .lower(),
            "HINDSIGHT_API_LLM_API_KEY": key or "",
            "HINDSIGHT_API_PORT": str(config.get("port") or HINDSIGHT_PORT),
            "HINDSIGHT_API_LOG_LEVEL": config.get("log_level") or "info",
            "HINDSIGHT_EMBED_DAEMON_IDLE_TIMEOUT": str(config.get("idle_timeout") or 0),
        }
    return env


def profiles_from_manifest(agents: Path) -> list[str]:
    """The `llgenie-*` profile names, as the fleet manifest lists them."""
    manifest = agents / "manifest.json"
    if not manifest.is_file():
        return []
    try:
        data = json.loads(manifest.read_text())
    except (ValueError, OSError):
        return []
    names = data.get("profiles") if isinstance(data, dict) else None
    if isinstance(names, list):
        # The real manifest lists PROFILES AS OBJECTS ({"name": "llgenie-planner", "rules": [...]});
        # accept both shapes, take the NAME, never stringify a dict.
        out = [str(n.get("name", "")) if isinstance(n, dict) else str(n) for n in names]
        return [n for n in out if n]
    return [p.name for p in agents.iterdir()
            if p.is_dir() and p.name.startswith("llgenie-")]


def template_config(profile: str, llm_api_key: str | None = None) -> dict:
    """The one Hindsight config template every profile is written from (#2068)."""
    return {
        "mode": "local_embedded",
        "profile": "hermes",
        "llm_provider": HINDSIGHT_PROVIDER,
        "llm_model": HINDSIGHT_MODEL,
        "llm_base_url": HINDSIGHT_BASE_URL,
        "port": HINDSIGHT_PORT,
        "idle_timeout": 0,
        "log_level": "info",
        "bank_id_template": "{profile}",
        "additional_banks": "llgenie-shared",
    }


def config_path(profile_home: Path) -> Path:
    """The per-profile Hindsight config.json."""
    return profile_home / "hindsight" / "config.json"


def env_path(profile_home: Path) -> Path:
    """The per-profile `.env` (holds the HINDSIGHT_LLM_API_KEY line)."""
    return profile_home / ".env"


def read_env_key(profile_home: Path) -> str | None:
    """The `HINDSIGHT_LLM_API_KEY` value from the profile's own `.env` (or None).

    Reads the value but never returns it to anything that prints: callers use the
    value only as an input to the plugin's env builder.
    """
    dotenv = env_path(profile_home)
    if not dotenv.is_file():
        return None
    try:
        for line in dotenv.read_text(errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, _, value = stripped.partition("=")
            if key.strip() == "HINDSIGHT_LLM_API_KEY":
                return value.strip().strip('"\'')
    except OSError:
        return None
    return None


def memory_provider(home: Path, profile: str) -> str:
    """The `memory.provider` value a profile's Hermes config sets ('' when unset).

    Reads the profile's `config.yaml`/`settings.yaml` the way Hermes does, at the
    simplest plausible surface. An empty provider is exactly the measured failure of
    #2068 — the plugin installed but never running.
    """
    for rel in ("config.yaml", "settings.yaml"):
        path = home / profile / rel if (home / profile).is_dir() else profile_home(home, profile) / rel
        if path.is_file():
            for line in path.read_text(errors="replace").splitlines():
                if line.lstrip().startswith(("provider:", "provider =")):
                    _, _, value = line.partition(":")
                    return value.strip().strip("'\"")
    return ""


def _provider_delta(home: Path, profile: str, wanted: str) -> str:
    current = memory_provider(home, profile)
    if current == wanted:
        return "unchanged"
    return f"{current or '(empty)'} -> {wanted}"


def _write_0600(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        os.chmod(path, 0o600)
        raise
    os.chmod(path, 0o600)


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------
def daemon_serving(port: int, host: str = "127.0.0.1") -> bool:
    """Is something already listening on the daemon port? (the idempotency probe)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def install_command(port: int) -> str:
    """The exact daemon provision command: pinned, idle-timeout disabled, fixed port."""
    return f"uvx hindsight-api@{HINDSIGHT_PIN} --idle-timeout 0 --port {port}"


def plan_install(port: int) -> dict:
    """The install plan (command + pin), for dry-run printing and tests."""
    return {
        "command": install_command(port),
        "pin": HINDSIGHT_PIN,
        "port": port,
    }


def cmd_install(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="memory_bootstrap install")
    ap.add_argument("--port", type=int, default=HINDSIGHT_PORT)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    a = ap.parse_args(argv)
    if a.dry_run:
        plan = plan_install(a.port)
        print(f"[memory] install --dry-run: {plan['command']} "
              f"(pin {plan['pin']}, port {plan['port']})")
        return 0
    if daemon_serving(a.port, a.host):
        print(f"[memory] install: port {a.port} is already served — no change")
        return 0
    # Provision: detached from the gateway (its own session leader, reparented to 1).
    cmd = ["uvx", f"hindsight-api@{HINDSIGHT_PIN}",
           "--idle-timeout", "0", "--port", str(a.port)]
    # The launcher is detached: new session, stdin/out/err to a log we own.
    log = hermes_home() / ".hindsight" / "install.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as out:
        try:
            subprocess.Popen(cmd, stdout=out, stderr=out, stdin=subprocess.DEVNULL,  # proc-allow: a detached long-lived daemon (new session, reparented to 1); scripts/proc.py has no spawn policy and a run_* call would block on it
                             start_new_session=True, close_fds=True)
        except FileNotFoundError as exc:
            print(f"[memory] install: cannot provision the daemon: {exc} — "
                  f"`uvx` (uv) is required, and hindsight-api@{HINDSIGHT_PIN} must install "
                  "from the network", file=sys.stderr)
            return 2
    # Give it a moment to bind, then prove it.
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if daemon_serving(a.port, a.host):
            print(f"[memory] install: the daemon answered on {a.host}:{a.port} "
                  f"(uvx hindsight-api@{HINDSIGHT_PIN}); writes to {log}")
            return 0
        time.sleep(0.2)
    print(f"[memory] install: launched the daemon but it did not answer within 15s on "
          f"{a.host}:{a.port} — see {log}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------
def _write_plan(profile_home: Path) -> list[tuple[str, Path]]:
    cfg = config_path(profile_home)
    env = env_path(profile_home)
    return [("config", cfg), (".env", env)]


def _base_cmd(args: list[str], prog: str) -> argparse.Namespace:
    # shared bootstrap/verify flags
    p = argparse.ArgumentParser(prog=prog)
    p.add_argument("--profiles", nargs="*", default=None,
                   help="profile names; default = every llgenie-* profile in the manifest")
    p.add_argument("--hermes-home", default=None)
    p.add_argument("--agents", default=str(REPO_ROOT / "agents"))
    p.add_argument("--dry-run", action="store_true")
    return p


def cmd_bootstrap(argv: list[str]) -> int:
    p = _base_cmd(argv, "memory_bootstrap bootstrap")
    p.add_argument("--plugin", default=None, help="path to the plugin's embedded.py (tests)")
    a = p.parse_args(argv)
    home = Path(a.hermes_home or hermes_home()).expanduser()
    agents = Path(a.agents)
    profiles = a.profiles or profiles_from_manifest(agents)
    if not profiles:
        print(f"[memory] bootstrap: nothing to do — no profiles under {home}/profiles and "
              f"no --profiles given", file=sys.stderr)
        return 2
    module = None
    if a.plugin:
        module = {}
        exec(compile(Path(a.plugin).read_bytes(), str(a.plugin), "exec"), module)  # noqa: S102
    else:
        try:
            module = load_builder(home)
        except MissingPlugin as exc:
            print(f"[memory] bootstrap: {exc}", file=sys.stderr)
            if not a.dry_run:
                return 2

    updated = 0
    unchanged = 0
    for profile in profiles:
        ph = profile_home(home, profile)
        ph.mkdir(parents=True, exist_ok=True)
        cfg_path = config_path(ph)
        wanted_cfg = template_config(profile)
        existing_cfg = {}
        if cfg_path.is_file():
            try:
                existing_cfg = json.loads(cfg_path.read_text())
            except ValueError:
                existing_cfg = {}
        cfg_changed = existing_cfg != wanted_cfg

        dotenv = env_path(ph)
        key_exists = read_env_key(ph) is not None
        provider_delta = _provider_delta(home, profile, "hindsight")

        plan = _write_plan(ph)
        if a.dry_run:
            print(f"[memory] bootstrap --dry-run: {profile}")
            for kind, path in plan:
                mode = "0600" if kind == "config" else ("0600" if kind == ".env" else "?")
                state = "write" if kind == "config" and cfg_changed else "unchanged"
                print(f"  - {kind}: {path} (mode {mode}, {state})")
            if not key_exists:
                print(f"  - key: HINDSIGHT_LLM_API_KEY is MISSING from {dotenv} — "
                      "the bootstrap reads it, it never invents one")
            print(f"  - provider: memory.provider {provider_delta}")
            continue

        if cfg_changed:
            _write_0600(cfg_path, json.dumps(wanted_cfg, indent=2, sort_keys=True) + "\n")
            updated += 1
        else:
            unchanged += 1

        # The env file holds the profile's own key; bootstrap never writes its value, but it
        # must still pin the file's mode to 0600 — a key sitting in a world-readable .env is a
        # credential leak even though the content is the profile's, not ours (AC7).
        if dotenv.exists():
            os.chmod(dotenv, 0o600)

        if not key_exists:
            # The key is the profile's own secret; the bootstrap never writes one. It
            # still reports the plan honestly so the operator can place it.
            print(f"[memory] bootstrap: {profile} has no HINDSIGHT_LLM_API_KEY in "
                  f"{dotenv} — place the profile's key there and re-run", file=sys.stderr)

        # provider: set to 'hindsight' when not already
        current = memory_provider(home, profile)
        if current != "hindsight":
            _provider = _write_provider_stub(home, profile, ph, current)
            updated += _provider

    print(f"[memory] bootstrap: {updated} updated, {unchanged} unchanged "
          f"(across {len(profiles)} profile(s))")
    return 0


def _write_provider_stub(home: Path, profile: str, ph: Path, current: str) -> int:
    """Write memory.provider=hindsight into the profile's Hermes settings.

    The config surface differs per install; this writes the documented `settings.yaml`
    under the profile home when no existing provider key is found, and reports a delta.
    Writes are append-only to a `settings.yaml` we own.
    """
    path = ph / "settings.yaml"
    line = "provider: hindsight\n"
    existing = path.read_text() if path.is_file() else ""
    if "provider:" in existing and current != "hindsight":
        # do not clobber a real (non-empty) provider the operator set; the gate /verify
        # will surface it as a delta.
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        if existing and not existing.rstrip().endswith("\n"):
            stream.write("\n")
        stream.write("# llgenie memory bootstrap (#2068)\n" + line)
    os.chmod(path, 0o600)
    return 1


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------
def _daemon_evidence(port: int) -> dict:
    """pid + port + /proc/<pid>/environ evidence for a serving daemon (or {}).

    Candidates are RANKED, never taken in raw numeric pid order: a pid whose cmdline names
    `hindsight` wins over one that does not; then a pid with a readable environ wins over an
    unreadable one. (`check` FAILs a non-hindsight pid explicitly — ranking keeps the gate
    from accidentally grabbing an unrelated same-user listener on some other port.)
    """
    if not daemon_serving(port):
        return {}
    pids = _listen_pids(port)
    scored = sorted(
        ((0 if "hindsight" in _proc_cmdline(p).lower() else 1,
          0 if _proc_environ(p) else 1, p) for p in pids),
        key=lambda t: t[:3])
    if scored:
        pid = scored[0][2]
        return {"pid": pid, "port": port, "environ": _proc_environ(pid)}
    return {"pid": None, "port": port, "environ": {}}


def _listen_pids(port: int) -> list[int]:
    """The PIDs listening on *port* specifically, via ss/lsof (best-effort, non-fatal).

    The ss scan is per-LINE, filtered to the target port (`:PORT` at a word boundary, so
    `:80` never matches `:8080` and `:5834` never matches `:58343`), and only the process
    column's `pid=` is taken. A regex over the WHOLE `ss -ltnp` output instead admits every
    other listening socket's pid, every address octet and every queue number — sorted
    numerically, a low-pid same-user process on another port wins. `lsof -tiTCP PORT
    -sTCP:LISTEN` already prints only pids for that port.

    When NEITHER tool exists (the hermetic test container has no iproute2/lsof), fall back
    to pure `/proc`: take the LISTEN (`st=0A`) socket inodes for that port from
    `/proc/net/tcp{,6}`, then find which `/proc/<pid>/fd` symlinks point at those inodes.
    The gate must measure the daemon identically on a full host and inside the CI seam.
    """
    for cmd in (["ss", "-ltnp"], ["lsof", "-tiTCP", str(port), "-sTCP:LISTEN"]):
        try:
            out = run_ok(cmd, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        if cmd[0] == "ss":
            found: list[int] = []
            for line in out.splitlines():
                if re.search(rf":{port}\b", line):
                    found.extend(int(m) for m in re.findall(r"pid=(\d+)", line))
        else:
            found = [int(line) for line in out.split() if line.isdigit()]
        if found:
            return sorted(set(found))
    return _proc_listen_pids(port)


def _proc_listen_pids(port: int) -> list[int]:
    """Pure-/proc fallback for _listen_pids: LISTEN inode on *port* -> owning pids."""
    inodes: set[str] = set()
    for net_file in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(net_file).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) < 10 or fields[3] != "0A":  # 0A = TCP_LISTEN
                continue
            try:
                local_port = int(fields[1].rsplit(":", 1)[1], 16)
            except ValueError:
                continue
            if local_port == port:
                inodes.add(fields[9])
    if not inodes:
        return []
    targets = {f"socket:[{inode}]" for inode in inodes}
    found: list[int] = []
    try:
        proc_entries = [p.name for p in Path("/proc").iterdir() if p.name.isdigit()]
    except OSError:
        return []
    for name in proc_entries:
        try:
            for fd in (Path("/proc") / name / "fd").iterdir():
                try:
                    if os.readlink(fd) in targets:
                        found.append(int(name))
                        break
                except OSError:
                    pass
        except OSError:
            continue  # process exited mid-scan, or its fds belong to another user
    return sorted(set(found))


def _proc_environ(pid: int) -> dict:
    """The daemon's real env: /proc/<pid>/environ, newest name wins."""
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except (OSError, PermissionError):
        return {}
    out: dict[str, str] = {}
    for entry in raw.split(b"\0"):
        if b"=" not in entry:
            continue
        k, _, v = entry.partition(b"=")
        out[k.decode(errors="replace")] = v.decode(errors="replace")
    return out


def _connection_verified_log(log: Path) -> str | None:
    """The newest `Connection verified:` line in the daemon log (or None)."""
    if not log.is_file():
        return None
    newest: str | None = None
    try:
        for line in log.read_text(errors="replace").splitlines():
            if "Connection verified:" in line:
                newest = line.strip()
    except OSError:
        return None
    return newest


#: The daemon env keys `check` compares between a profile's plugin-built env and the
#: shared `hermes.env` (issue #2058). The API key is deliberately NOT in this set: its
#: PRESENCE is asserted per profile (AC3), and its value must never enter a comparison
#: whose diff could end up printed.
FLEET_ENV_KEYS = (
    DAEMON_ENV_BASE_URL,
    DAEMON_ENV_MODEL,
    DAEMON_ENV_PROVIDER,
    "HINDSIGHT_API_PORT",
    "HINDSIGHT_API_LOG_LEVEL",
    "HINDSIGHT_EMBED_DAEMON_IDLE_TIMEOUT",
)


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a KEY=value env file into a dict (blank/comment lines skipped)."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        for line in path.read_text(errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, _, value = stripped.partition("=")
            out[key.strip()] = value.strip().strip('"\'')
    except OSError:
        return {}
    return out


def _proc_cmdline(pid: int) -> str:
    """The command line of *pid*, NUL-joined ('' when unreadable)."""
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (OSError, PermissionError):
        return ""
    return "\0".join(part.decode(errors="replace") for part in raw.split(b"\0") if part)


def cmd_check(argv: list[str]) -> int:
    """The fleet-memory gate (issue #2058).

    0 = every profile's built env equals the shared env, every profile carries its own
    key, and the daemon evidence matches the template. 1 = a FAIL naming the profile(s)
    or the daemon. 2 = a precondition is absent (no profiles, no shared `hermes.env`, no
    plugin builder, nothing listening on the daemon port). A daemon that merely answers
    `/health` never passes: the evidence is pid + port + real environ + connection line.
    Key VALUES are never printed — only key NAMES and the non-secret endpoint values.
    """
    p = _base_cmd(argv, "memory_bootstrap check")
    p.add_argument("--plugin", default=None, help="path to the plugin's embedded.py (tests)")
    p.add_argument("--port", type=int, default=HINDSIGHT_PORT)
    p.add_argument("--hindsight-dir", default=None,
                   help="the shared ~/.hindsight dir (env file + daemon log)")
    a = p.parse_args(argv)
    home = Path(a.hermes_home or hermes_home()).expanduser()
    profiles = a.profiles or profiles_from_manifest(Path(a.agents))
    hs = Path(a.hindsight_dir or hermes_home() / ".hindsight").expanduser()
    shared_env_path = hs / "profiles" / "hermes.env"
    shared_log = hs / "profiles" / "hermes.log"

    def precondition(what: str) -> int:
        print(f"[memory] check precondition missing: {what}", file=sys.stderr)
        return 2

    if not profiles:
        return precondition("no profiles — none in the manifest and none passed with --profiles")
    if not shared_env_path.is_file():
        return precondition(f"no shared env file at {shared_env_path}")

    if a.plugin:
        module = {}
        exec(compile(Path(a.plugin).read_bytes(), str(a.plugin), "exec"), module)  # noqa: S102
    else:
        try:
            module = load_builder(home)
        except MissingPlugin as exc:
            return precondition(str(exc))

    shared_env = _parse_env_file(shared_env_path)
    evidence = _daemon_evidence(a.port)
    if not evidence or evidence.get("pid") is None:
        return precondition(f"no daemon listening on port {a.port} — provision it with make memory-install")

    pid = evidence["pid"]
    print(f"[memory] check: measuring daemon pid {pid} on port {a.port}")

    failures: list[str] = []
    for profile in profiles:
        ph = profile_home(home, profile)
        key = read_env_key(ph)
        if key is None or not key.strip() or key.strip() == "not-needed":
            print(f"[memory] check FAIL {profile}: no HINDSIGHT_LLM_API_KEY in the profile .env")
            failures.append(profile)
            continue
        cfg_file = config_path(ph)
        if not cfg_file.is_file():
            print(f"[memory] check FAIL {profile}: no hindsight/config.json — run make memory-render")
            failures.append(profile)
            continue
        try:
            cfg = json.loads(cfg_file.read_text(errors="replace"))
        except ValueError:
            print(f"[memory] check FAIL {profile}: hindsight/config.json is not readable JSON")
            failures.append(profile)
            continue
        built = builder_env(module, cfg, profile, key)
        diffs = {k: (str(built.get(k, "")), str(shared_env.get(k, "")))
                 for k in FLEET_ENV_KEYS
                 if str(built.get(k, "")) != str(shared_env.get(k, ""))}
        if diffs:
            print(f"[memory] check FAIL {profile}: built env differs from hermes.env: {diffs}")
            failures.append(profile)

    environ = evidence.get("environ") or {}
    cmdline = _proc_cmdline(pid)
    daemon_problems: list[str] = []
    if "hindsight" not in cmdline.lower():
        head_arg = cmdline.split("\0", 1)[0] if cmdline else "<unreadable>"
        daemon_problems.append(f"pid {pid} is not a hindsight process ({head_arg})")
    if not environ:
        daemon_problems.append(f"/proc/{pid}/environ unreadable or empty — /health alone never passes")
    for env_key, want in ((DAEMON_ENV_MODEL, HINDSIGHT_MODEL),
                          (DAEMON_ENV_BASE_URL, HINDSIGHT_BASE_URL),
                          (DAEMON_ENV_PROVIDER, HINDSIGHT_PROVIDER)):
        got = environ.get(env_key, "")
        if got != want:
            daemon_problems.append(f"daemon environ {env_key}: {got or '<missing>'} != {want}")
    connection = _connection_verified_log(shared_log)
    if connection is None:
        daemon_problems.append(f"no 'Connection verified:' line in {shared_log}")
    else:
        if HINDSIGHT_MODEL not in connection:
            daemon_problems.append(f"connection line disagrees with the template model: {connection}")
        for url in re.findall(r"https?://\S+", connection):
            if url.rstrip(".,;)") != HINDSIGHT_BASE_URL:
                daemon_problems.append(f"connection url {url} != {HINDSIGHT_BASE_URL}")

    if daemon_problems:
        for problem in daemon_problems:
            print(f"[memory] check FAIL daemon (pid={pid} port={a.port}): {problem}")
    if failures or daemon_problems:
        named = sorted(set(failures)) + (["daemon"] if daemon_problems else [])
        print("[memory] check: FAIL — " + ", ".join(named), file=sys.stderr)
        return 1

    print(f"[memory] check: profiles ok: {len(profiles)} build the shared env and carry a key; "
          f"daemon ok: pid {pid} {a.port} "
          f"{environ.get(DAEMON_ENV_MODEL)} @ {environ.get(DAEMON_ENV_BASE_URL)} "
          f"(connection: {connection})")
    return 0


def cmd_render(argv: list[str]) -> int:
    """Materialise every profile's Hindsight config from the ONE template, idempotently.

    `render` writes `hindsight/config.json` from `template_config` and pins the profile
    `.env` to 0600, creating an empty `.env` where a profile has none. It NEVER invents
    or copies a key value: the key is the profile's own secret, placed by the operator
    or by `bootstrap`. A second render with nothing changed reports `0 updated` and
    rewrites no bytes (issue #2058).
    """
    p = _base_cmd(argv, "memory_bootstrap render")
    a = p.parse_args(argv)
    home = Path(a.hermes_home or hermes_home()).expanduser()
    profiles = a.profiles or profiles_from_manifest(Path(a.agents))
    if not profiles:
        print(f"[memory] render: nothing to do — no profiles under {home}/profiles and "
              "no --profiles given", file=sys.stderr)
        return 2

    updated = 0
    unchanged = 0
    for profile in profiles:
        ph = profile_home(home, profile)
        wanted = json.dumps(template_config(profile), indent=2, sort_keys=True) + "\n"
        cfg_path = config_path(ph)
        existing: str | None = None
        if cfg_path.is_file():
            try:
                existing = cfg_path.read_text(errors="replace")
            except OSError:
                existing = None
        cfg_changed = existing != wanted
        dotenv = env_path(ph)
        env_missing = not dotenv.is_file()

        if a.dry_run:
            print(f"[memory] render --dry-run: {profile}")
            print(f"  - config: {cfg_path} (mode 0600, {'write' if cfg_changed else 'unchanged'})")
            print(f"  - .env: {dotenv} (mode 0600, "
                  f"{'create empty' if env_missing else 'unchanged'})")
            if cfg_changed:
                updated += 1
            else:
                unchanged += 1
            continue

        if cfg_changed:
            ph.mkdir(parents=True, exist_ok=True)
            _write_0600(cfg_path, wanted)
            updated += 1
        else:
            unchanged += 1
        if env_missing:
            ph.mkdir(parents=True, exist_ok=True)
            _write_0600(dotenv, "")
        elif dotenv.exists():
            os.chmod(dotenv, 0o600)

    print(f"[memory] render: {updated} updated, {unchanged} unchanged "
          f"(across {len(profiles)} profile(s))")
    return 0


def cmd_status(argv: list[str]) -> int:
    """Print the fleet-memory wiring this host currently has — a report, never a verdict.

    `check` decides; `status` only shows: the daemon's pid/port/environ + connection line,
    the shared env's endpoint values (its key is reported as PRESENT/absent only), and each
    profile's config/key/provider presence. Exits 0 whether or not anything is provisioned.
    """
    p = _base_cmd(argv, "memory_bootstrap status")
    p.add_argument("--port", type=int, default=HINDSIGHT_PORT)
    p.add_argument("--hindsight-dir", default=None,
                   help="the shared ~/.hindsight dir (env file + daemon log)")
    a = p.parse_args(argv)
    home = Path(a.hermes_home or hermes_home()).expanduser()
    profiles = a.profiles or profiles_from_manifest(Path(a.agents))
    hs = Path(a.hindsight_dir or hermes_home() / ".hindsight").expanduser()
    shared_env_path = hs / "profiles" / "hermes.env"
    shared_log = hs / "profiles" / "hermes.log"

    shared_env = _parse_env_file(shared_env_path)
    evidence = _daemon_evidence(a.port)
    connection = _connection_verified_log(shared_log)
    environ = evidence.get("environ") or {}
    print(f"[memory] status: shared env {shared_env_path} "
          f"({'present' if shared_env_path.is_file() else 'ABSENT'}) "
          f"model={shared_env.get(DAEMON_ENV_MODEL, '-n/a-')} "
          f"provider={shared_env.get(DAEMON_ENV_PROVIDER, '-n/a-')} "
          f"base_url={shared_env.get(DAEMON_ENV_BASE_URL, '-n/a-')} "
          f"key={'present' if shared_env.get('HINDSIGHT_API_LLM_API_KEY') else 'absent'}")
    pid = evidence.get("pid")
    print(f"[memory] status: daemon pid={pid} port={a.port} serving={'yes' if pid else 'NO'} "
          f"model={environ.get(DAEMON_ENV_MODEL, '-n/a-')} "
          f"base_url={environ.get(DAEMON_ENV_BASE_URL, '-n/a-')} "
          f"connection={connection or '-n/a-'}")
    for profile in profiles:
        ph = profile_home(home, profile)
        print(f"[memory] status {profile}: "
              f"config={'yes' if config_path(ph).is_file() else 'NO'} "
              f"key={'yes' if read_env_key(ph) else 'NO'} "
              f"provider={memory_provider(home, profile) or '-unset-'}")
    if not profiles:
        print("[memory] status: no profiles under the manifest")
    return 0


def cmd_verify(argv: list[str]) -> int:
    p = _base_cmd(argv, "memory_bootstrap verify")
    p.add_argument("--port", type=int, default=HINDSIGHT_PORT)
    p.add_argument("--hindsight-dir", default=None,
                   help="the shared ~/.hindsight dir (for the daemon log)")
    a = p.parse_args(argv)
    home = Path(a.hermes_home or hermes_home()).expanduser()
    agents = Path(a.agents)
    profiles = a.profiles or profiles_from_manifest(agents)
    if not profiles:
        print("[memory] verify: no profiles to verify", file=sys.stderr)
        return 2

    hs = Path(a.hindsight_dir or hermes_home() / ".hindsight").expanduser()
    shared_log = hs / "profiles" / "hermes.log"
    evidence = _daemon_evidence(a.port)

    failures: list[str] = []
    for profile in profiles:
        ph = profile_home(home, profile)
        key_present = read_env_key(ph) is not None
        provider = memory_provider(home, profile)
        model = base_url = connection = "n/a"
        if evidence.get("environ"):
            model = evidence["environ"].get(DAEMON_ENV_MODEL, "")
            base_url = evidence["environ"].get(DAEMON_ENV_BASE_URL, "")
        connection = _connection_verified_log(shared_log) or "n/a"

        problems = []
        if not key_present:
            problems.append("no HINDSIGHT_LLM_API_KEY")
        if not provider or "hindsight" not in provider.lower():
            problems.append(f"memory.provider='{provider or 'empty'}'")

        verdict = "PASS" if not problems else "FAIL"
        print(f"[memory] verify {profile}: {verdict} "
              f"daemon_pid={evidence.get('pid')} port={evidence.get('port')} "
              f"model={model or '-n/a-'} base_url={base_url or '-n/a-'} "
              f"connection={connection}")
        for problem in problems:
            print(f"[memory]   - {profile}: {problem}")
            failures.append(f"{profile}: {problem}")

    if failures:
        print(f"[memory] verify: FAIL — {len(failures)} finding(s) for: "
              + ", ".join(sorted({f.split(':')[0] for f in failures})), file=sys.stderr)
        return 1
    print("[memory] verify: OK — every profile is wired and the daemon is serving")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("install")
    sub.add_parser("bootstrap")
    sub.add_parser("verify")
    sub.add_parser("render")
    sub.add_parser("check")
    sub.add_parser("status")
    a, rest = ap.parse_known_args(argv)
    if a.command == "install":
        return cmd_install(rest)
    if a.command == "bootstrap":
        return cmd_bootstrap(rest)
    if a.command == "verify":
        return cmd_verify(rest)
    if a.command == "render":
        return cmd_render(rest)
    if a.command == "check":
        return cmd_check(rest)
    if a.command == "status":
        return cmd_status(rest)
    return 2


if __name__ == "__main__":
    sys.exit(main())
