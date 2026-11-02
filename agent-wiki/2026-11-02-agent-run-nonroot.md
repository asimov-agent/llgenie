# Agent image runs as a non-root user (issue #1576)

2026-11-02. The agent image (`containers/agent/Dockerfile`) built its whole runtime as `root`:
`USER root` at line 90 was followed by no further `USER`, so the install chain, the `CMD`
liveness, and every tool the container runs after `CMD` (git, gh, hermes) all ran as ROOT — the
semgrep rule `dockerfile.security.last-user-is-root.last-user-is-root` flagged it HIGH, and the
finding is real: a root runtime carrying git/gh and an owner PAT is an unnecessary privilege
surface if one of those tools is ever driven by untrusted input.

The hard part was not the `USER` directive — it was that the runtime genuinely needs a writable,
referenced home. `ENV HERMES_HOME=/root/.hermes` (line 143) and `ENV PATH="/root/.local/bin:…"`
(line 122) pointed the CLI + its plugin tree at root's home. Naively setting `USER nonroot` would
have left `/root/.hermes` unwritable and the `CMD` liveness (`hermes plugins list | grep -q nerve`)
would fail.

## Fix

A minimal least-privilege change: create the runtime user and point the install chain at its
home **up front**, so the whole runtime lands where the non-root user owns it.

- create the runtime user `agent` (`useradd -r -m -d /home/agent -s /bin/bash agent`) and
  `mkdir /home/agent/{.local/bin,.hermes}`;
- set `HOME=/home/agent`, `HERMES_HOME=/home/agent/.hermes`, and
  `PATH=/home/agent/.local/bin:…` **before** the hermes + nerve install RUNs — they write the
  CLI (`~/.local/bin`), the tree (`$HERMES_HOME`), and the nerve bundle straight into the
  non-root home (a post-install relocation of a `/root`-rooted tree is not viable: the
  installed launcher and venv embed the absolute home in 700+ paths);
- after `WORKDIR /repo`, `chown -R agent:agent /home/agent` and `USER agent` immediately
  before `CMD`.

The root-requiring steps are untouched; only the install target home and the runtime identity
are lowered. `grep '^USER'` now yields exactly one directive — `agent`, last before `CMD`, not
root. The committed semgrep pack no longer reports `last-user-is-root` on the agent Dockerfile.
The runtime gate (build, then the `CMD` liveness as the non-root user) still passes.
