#!/usr/bin/env python3
"""Prove that every credential a container receives is visible in the AGENT's shell.

The agent runs its commands (`gh`, `hf`, `curl` …) through Hermes's terminal tool, and Hermes
STRIPS provider credentials from that shell on purpose: `NOUS_API_KEY`, `GH_TOKEN`,
`FIRECRAWL_API_KEY` and `HF_TOKEN` are on its blocklist
(`tools/environments/local_env_policy.py::_STATIC_PROVIDER_ENV_BLOCKLIST`), and `env_passthrough`
can never re-allow a blocklisted name. The one sanctioned way through is the `_HERMES_FORCE_<NAME>`
form, which the terminal env builder unwraps to `<NAME>`.

Measured on this host against the real Hermes (issue #358): a key forwarded as `-e NOUS_API_KEY`
reaches the container and the Hermes process — `make`'s own pre-flight sees it — while the agent's
shell reads it EMPTY:

    $ NOUS_API_KEY=SENTINEL python3 scripts/agent_shell_keys_check.py NOUS_API_KEY
    [agent-shell-keys] NOUS_API_KEY: container=set agent-shell=EMPTY (MISMATCH; _HERMES_FORCE_NOUS_API_KEY NOT forced; value never printed)
    $ NOUS_API_KEY=SENTINEL _HERMES_FORCE_NOUS_API_KEY=SENTINEL python3 scripts/agent_shell_keys_check.py NOUS_API_KEY
    [agent-shell-keys] OK: 1 credential(s) visible in the agent's shell.

The sibling repo (trending-local-llms, its issue #359) paid for this first: the key was in the
container, the step log read `FIRECRAWL_API_KEY: ***`, and the agent's `curl` sent an EMPTY Bearer —
every search leg got HTTP 401 while the job was green.

So this check runs its probe through Hermes's REAL terminal environment (`LocalEnvironment`, the code
the agent's `terminal` tool uses), in the image the bots run, and fails — naming the variable — when
a key that is set in the container is empty in the agent's shell. It prints LENGTHS only: never a
value, never a prefix.

NO-SKIP POLICY: a key that is not set in the container, or a Hermes that cannot be found, is a LOUD
failure (exit 2). `--allow-unconfigured` is an explicit local opt-out that reports NOT CONFIGURED.

Usage:
    python3 scripts/agent_shell_keys_check.py NOUS_API_KEY GH_TOKEN TYPESAFE_API_KEY
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

#: The prefix Hermes unwraps into the terminal child (`_HERMES_PROVIDER_ENV_FORCE_PREFIX`).
FORCE_PREFIX = "_HERMES_FORCE_"

#: A variable name we are willing to interpolate into a probe command.
NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")

#: The probe runs INSIDE Hermes's own interpreter, so it is the agent's real terminal env builder
#: that decides — not a re-implementation of its filter here (AGENTS.md: the business logic is never
#: mocked, and an external system is talked to for real).
PROBE = r"""
import json, sys, tempfile
names = json.loads(sys.argv[1])
from tools.environments.local import LocalEnvironment
cwd = tempfile.mkdtemp()
try:
    env = LocalEnvironment(cwd=cwd, timeout=60, persistent=False)
except TypeError:
    env = LocalEnvironment(cwd=cwd, timeout=60)
cmd = "; ".join('printf "%s=%s\\n" ' + n + ' "${#' + n + '}"' for n in names)
res = env.execute(cmd)
out = res.get("output", "") if isinstance(res, dict) else str(res)
lengths = {}
for line in out.splitlines():
    k, sep, v = line.strip().partition("=")
    if sep and k in names and v.isdigit():
        lengths[k] = int(v)
print("AGENT_SHELL_LENGTHS=" + json.dumps(lengths))
"""


def hermes_root() -> Path | None:
    """The Hermes tree the CLI runs from (the agent image: /root/.hermes/hermes-agent)."""
    cands = [os.environ.get("HERMES_AGENT_ROOT", ""), "/root/.hermes/hermes-agent",
             str(Path.home() / ".hermes" / "hermes-agent")]
    for c in cands:
        if c and (Path(c) / "tools" / "environments" / "local.py").is_file():
            return Path(c)
    return None


def hermes_python(root: Path) -> str | None:
    """The interpreter Hermes itself runs under (its managed venv), else None."""
    home = root.parent
    cands = [os.environ.get("HERMES_PYTHON", ""), str(root / "venv" / "bin" / "python"),
             str(root / ".venv" / "bin" / "python"),
             *sorted(glob.glob(str(home / "installs" / "*" / "environments" / "*" / "venv" / "bin" / "python")))]
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def agent_shell_lengths(names: list[str]) -> dict[str, int]:
    """Run the probe through Hermes's terminal environment; return {name: length in the agent shell}."""
    root = hermes_root()
    if root is None:
        raise RuntimeError("Hermes is not installed here (no tools/environments/local.py under "
                           "/root/.hermes/hermes-agent or ~/.hermes/hermes-agent) — run it in the bot image")
    py = hermes_python(root)
    if py is None:
        raise RuntimeError(f"Hermes's own interpreter was not found next to {root}")
    r = subprocess.run([py, "-c", PROBE, json.dumps(names)], cwd=str(root), env=dict(os.environ),
                       capture_output=True, text=True, timeout=180)
    for line in r.stdout.splitlines():
        if line.startswith("AGENT_SHELL_LENGTHS="):
            return json.loads(line.split("=", 1)[1])
    raise RuntimeError(f"the Hermes terminal probe produced no result (rc={r.returncode}): "
                       f"{(r.stderr or r.stdout)[-400:]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fail when a container credential is empty in the agent's shell.")
    ap.add_argument("names", nargs="+", help="the credentials the agent's shell must see")
    ap.add_argument("--allow-unconfigured", action="store_true",
                    help="explicit local opt-out (never set in CI)")
    args = ap.parse_args(argv)

    bad = [n for n in args.names if not NAME.match(n)]
    if bad:
        print(f"[agent-shell-keys] FATAL: not a variable name: {', '.join(bad)}", file=sys.stderr)
        return 2
    if args.allow_unconfigured:
        print("[agent-shell-keys] NOT CONFIGURED (--allow-unconfigured): nothing about the agent's shell "
              "was verified.")
        return 0

    unset = [n for n in args.names if not os.environ.get(n)]
    if unset:
        print(f"[agent-shell-keys] FATAL: {', '.join(unset)} is missing or empty in the container — "
              "there is nothing to prove the agent can see. Set the repository secret (the value stays "
              "in the environment, never in argv); see AGENTS.md.", file=sys.stderr)
        return 2

    try:
        lengths = agent_shell_lengths(args.names)
    except Exception as exc:  # noqa: BLE001 — every cause is reported, loudly
        print(f"[agent-shell-keys] FATAL: {exc}", file=sys.stderr)
        return 2

    blind = []
    for n in args.names:
        want = len(os.environ[n])
        got = lengths.get(n, 0)
        ok = got == want
        forced = "forced" if os.environ.get(FORCE_PREFIX + n) else "NOT forced"
        print(f"[agent-shell-keys] {n}: container=set agent-shell={'set' if got else 'EMPTY'} "
              f"({'match' if ok else 'MISMATCH'}; {FORCE_PREFIX}{n} {forced}; value never printed)")
        if not ok:
            blind.append(n)
    if blind:
        print(f"[agent-shell-keys] FATAL: the agent's shell cannot see {', '.join(blind)} — Hermes strips "
              f"provider credentials from its terminal; forward each as `-e {FORCE_PREFIX}<NAME>` from the "
              "Makefile's AGENT_SHELL_KEYS (issue #358).", file=sys.stderr)
        return 1
    print(f"[agent-shell-keys] OK: {len(args.names)} credential(s) visible in the agent's shell.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
