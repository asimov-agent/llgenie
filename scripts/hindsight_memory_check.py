#!/usr/bin/env python3
"""Fleet memory wiring: render each llgenie-* profile's hindsight config from ONE template
and verify the live daemon matches it (issue #2057, vehicle B).

13 `llgenie-*` Hermes profiles wire their memory through Hindsight (mode `local_embedded`):
one embedded daemon per host on `127.0.0.1:9177`, a per-profile `hindsight/config.json`
(0600), a per-profile `.env` holding `HINDSIGHT_LLM_API_KEY`, and one shared
`~/.hindsight/profiles/hermes.env` read by the single daemon. The wiring was hand-edited on
the host and was silently self-destructive: two sessions rewrite the same env file and
restart the same daemon, the last one winning, and a profile holding no key builds the
placeholder `not-needed` that overwrites the shared real key.

This module is vehicle B of #2057: it is the single source the thirteen `config.json` files
derive from and the gate that stops a flipped endpoint from reaching a dispatch. The
topology documentation lives in `docs/BOTS.md` (vehicle A, its own PR); this module encodes
exactly what that section states.

Commands:

  render   write every `llgenie-*` profile's `hindsight/config.json` from the template,
           idempotently (a second run changes nothing)
  check    verify each profile's built env against the shared `hermes.env`, that no profile's
           LLM key is empty, and that the live daemon's endpoint/model agree with the
           template; prints the pid and port it measured

Stdlib only: `check` reads `/proc/<pid>/environ`, a log file and the profile tree, so it
needs no package, no network and no image.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

#: The plugin profile name the embedded daemon keys off (NOT `HERMES_HOME`) — the shared
#: env file two sessions rewrite is named after this.
PLUGIN_PROFILE = "hermes"
#: The shared dir under the host HOME where the plugin's env and log live.
SHARED_REL = Path(".hindsight/profiles")
SHARED_ENV = "hermes.env"
SHARED_LOG = "hermes.log"
#: The models that run locally inside the daemon (they never leave the host).
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL = "hindsight-ai/hs-rerank-1"
#: The shared bank every profile also writes to / recalls from (dual writes work: the
#: `llgenie-architect` and `llgenie-shared` banks hold the same retained facts).
SHARED_BANK = "llgenie-shared"
#: The daemon's fixed endpoint and model per the documented topology.
DEFAULT_BASE_URL = "https://inference-api.nousresearch.com/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"
#: The default daemon port.
DAEMON_PORT = 9177
#: The base URL must end with /v1 for an OpenAI-compatible provider.
_PROVIDER = "openai_compatible"
_PLACEHOLDER_KEY = "not-needed"
_PORT_RE = re.compile(r"--port[ =](\d+)")
CONNECTION_RE = re.compile(r"Connection verified:\s+(\S+)")


def config_template(profile: str) -> dict:
    """ONE hindsight config shape every profile is rendered from (the single source)."""
    return {
        "profile": PLUGIN_PROFILE,
        "mode": "local_embedded",
        "llm_provider": _PROVIDER,
        "llm_api_key_from": "HINDSIGHT_LLM_API_KEY",  # profile .env key per profile
        "bank_id_template": "{profile}",
        "additional_banks": [SHARED_BANK],
        "embeddings_model": EMBEDDING_MODEL,
        "reranker_model": RERANKER_MODEL,
        "endpoint": DEFAULT_BASE_URL,
        "model": DEFAULT_MODEL,
        "port": DAEMON_PORT,
        "profile_name": profile,
    }


def profiles_dir(home: Path) -> Path:
    return home / ".hermes" / "profiles"


def shared_dir(home: Path) -> Path:
    return home / SHARED_REL


def find_profiles(home: Path) -> list[str]:
    """The `llgenie-*` profile names under the host's HERMES_HOME (sorted, stable)."""
    base = profiles_dir(home)
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.glob("llgenie-*") if p.is_dir())


def render_config(home: Path, profile: str) -> Path:
    """Write `profile`'s hindsight/config.json from the template (0600), idempotently."""
    cfg = config_template(profile)
    path = profiles_dir(home) / profile / "hindsight" / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(cfg, indent=2, sort_keys=True) + "\n"
    prev = path.read_text() if path.exists() else None
    if prev != text:  # idempotence: skip the write when nothing changed
        path.write_text(text)
        os.chmod(path, 0o600)
    return path


def render_all(home: Path) -> list[Path]:
    return [render_config(home, p) for p in find_profiles(home)]


def read_env_file(path: Path) -> dict[str, str]:
    """Parse a KEY=value `.env` file (the profile `.env` and the shared `hermes.env`)."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def profile_key(home: Path, profile: str) -> str:
    """A profile's LLM key from its `.env`; `None` -> placeholder `not-needed` when empty."""
    env = read_env_file(profiles_dir(home) / profile / ".env")
    key = env.get("HINDSIGHT_LLM_API_KEY", "")
    return key or _PLACEHOLDER_KEY


def profile_built_env(home: Path, profile: str) -> dict[str, str]:
    """The env a profile would hand the daemon (its key + the documented endpoint/model).

    Mirror of the plugin's `_build_embedded_profile_env`: the key comes from the profile,
    the endpoint/model from the template the daemon is expected to run on.
    """
    return {
        "HINDSIGHT_LLM_API_KEY": profile_key(home, profile),
        "HINDSIGHT_API_LLM_BASE_URL": DEFAULT_BASE_URL,
        "HINDSIGHT_API_LLM_MODEL": DEFAULT_MODEL,
        "HINDSIGHT_PROFILE": profile,
    }


def current_daemon_port() -> int | None:
    """The daemon's port from /proc or `uvx` args, else None (no live daemon found)."""
    for pid in _daemon_pids():
        environ = _proc_environ(pid)
        port = environ.get("HINDSIGHT_API_LLM_PORT")
        if port:
            return int(port)
        # last resort: a --port in the argv row of /proc/<pid>/cmdline
        args = _proc_cmdline(pid)
        if args:
            m = _PORT_RE.search(args)
            if m:
                return int(m.group(1))
    return None


def _daemon_pids() -> list[int]:
    try:
        proc = subprocess.run(
            ["pgrep", "-f", "hindsight-api"],  # proc-allow: the ONLY live-process probe, issue #797 remainder tracked here
            capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return []
    if proc.returncode != 0:
        return []
    return [int(p) for p in proc.stdout.split()]


def _proc_environ(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    return dict(
        item.split("=", 1) for item in raw.decode("utf-8", "replace").split("\0") if "=" in item
    )


def _proc_cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "replace").replace("\0", " ")
    except OSError:
        return ""


def last_connection_line(log: Path) -> str | None:
    """The last `Connection verified: ...` line in the daemon log (the measured evidence)."""
    if not log.exists():
        return None
    last: str | None = None
    for line in log.read_text().splitlines():
        m = CONNECTION_RE.search(line)
        if m:
            last = m.group(1)
    return last


def profile_findings(home: Path) -> list[str]:
    """Profile-side checks (fully hermetic over real files): each profile's endpoint/model must
    agree with the shared `hermes.env`, and no profile's LLM key may be empty (the empty key
    builds the `not-needed` placeholder that overwrites the shared real key)."""
    failures: list[str] = []
    shared_env = read_env_file(shared_dir(home) / SHARED_ENV)
    for profile in find_profiles(home):
        built = profile_built_env(home, profile)
        for key in ("HINDSIGHT_API_LLM_BASE_URL", "HINDSIGHT_API_LLM_MODEL"):
            want = shared_env.get(key)
            if want is None:
                continue  # shared file not carrying the key -> nothing to disagree with
            got = built.get(key)
            if got != want:
                failures.append(f"{profile}: {key} built={got!r} shared={want!r}")
        if profile_key(home, profile) == _PLACEHOLDER_KEY:
            failures.append(
                f"{profile}: HINDSIGHT_LLM_API_KEY is empty "
                f"(would write the placeholder {_PLACEHOLDER_KEY!r} over the shared key)")
    return failures


def daemon_findings(home: Path) -> list[str]:
    """Live-daemon checks: endpoint/model from each hindsight-api process's `/proc/<pid>/environ`,
    the measured port, and the log's last `Connection verified:` line — real `/proc`, real log.
    On a runner with no daemon this returns a `no daemon` finding (honest evidence, never a mock)."""
    failures: list[str] = []
    pids = _daemon_pids()
    if not pids:
        failures.append("no hindsight-api daemon process found (pgrep -f hindsight-api)")
    for pid in pids:
        environ = _proc_environ(pid)
        url = environ.get("HINDSIGHT_API_LLM_BASE_URL")
        model = environ.get("HINDSIGHT_API_LLM_MODEL")
        if url and url != DEFAULT_BASE_URL:
            failures.append(f"daemon {pid}: HINDSIGHT_API_LLM_BASE_URL={url!r} != {DEFAULT_BASE_URL!r}")
        if model and model != DEFAULT_MODEL:
            failures.append(f"daemon {pid}: HINDSIGHT_API_LLM_MODEL={model!r} != {DEFAULT_MODEL!r}")
    port = current_daemon_port()
    if port is not None and port != DAEMON_PORT:
        failures.append(f"daemon port {port} != {DAEMON_PORT}")
    log = shared_dir(home) / SHARED_LOG
    last = last_connection_line(log)
    if last and DEFAULT_MODEL not in last:
        failures.append(f"last Connection verified {last!r} names a model != {DEFAULT_MODEL!r}")
    return failures


def verify(home: Path, verbose: bool = True) -> int:
    """Vehicle B gate: exit 0 when every profile agrees with the shared file and the live daemon
    agrees with the template; non-zero naming the offending profile otherwise. Called by
    `make memory-check`."""
    failures: list[str] = []
    profiles = find_profiles(home)
    if verbose:
        print(f"[memory-check] profiles: {len(profiles)}  shared env: {shared_dir(home) / SHARED_ENV}")

    failures += profile_findings(home)
    failures += daemon_findings(home)

    if verbose:
        pids = _daemon_pids()
        print(f"[memory-check] daemon pid(s): {pids or '(none found)'}")
        port = current_daemon_port()
        print(f"[memory-check] measured daemon port: {port or '(none)'}")
        print(f"[memory-check] last Connection verified: {last_connection_line(shared_dir(home) / SHARED_LOG) or '(none)'}")

    if failures:
        for f in failures:
            print(f"[memory-check] FAIL: {f}", file=sys.stderr)
        print(f"[memory-check] FAILED ({len(failures)})", file=sys.stderr)
        return 1
    print("[memory-check] OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    doc = __doc__ or ""
    ap = argparse.ArgumentParser(description=doc.splitlines()[0] if doc else "hindsight memory check")
    ap.add_argument("cmd", choices=("render", "check"))
    ap.add_argument("--home", default=str(Path.home()),
                    help="HERMES_HOME to operate on (default: $HOME)")
    ap.add_argument("--quiet", action="store_true", help="suppress progress lines")
    a = ap.parse_args(argv)
    home = Path(a.home)
    if a.cmd == "render":
        paths = render_all(home)
        if not a.quiet:
            print(f"[hindsight-memory] rendered {len(paths)} config(s): {[str(p) for p in paths]}")
        return 0
    return verify(home, verbose=not a.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
