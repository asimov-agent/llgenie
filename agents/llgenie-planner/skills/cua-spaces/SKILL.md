---
name: cua-spaces
description: Use, set up, or uninstall cua Spaces on a host.
---

# cua Spaces

Spaces are exposed as MCP tools by the `cua` MCP server (`cua mcp`). If the
tools below are missing, ask the user to run `cua agents setup` or
`cua auth login`.

## Get a Space

| Tool | Use |
|---|---|
| `list_spaces` | See the Spaces you can use. Start here. |
| `create_space` | A new Space: `on` = `local` (free, the user's machine), `aws`, `gcp` or `modal` (the user's own cloud account, billed there), or `host:<name>` (one of the user's machines set up with `cua host setup`); `reuse: true` returns a reachable one first. |
| `add_space` / `remove_space` | Register an existing machine by URL and token, or forget one without deleting it. |
| `delete_space` | Delete a Space's sandbox and stop its cost. |
| `stop_space` / `start_space` | Turn a local Space (or one your machines provide) off and back on: suspended or stopped, as `power` in `list_spaces` says. |

Prefer an existing Space. A Space in the user's own cloud account costs money: delete the ones you
created when the task ends.

## Work in it

| Tool | Use |
|---|---|
| `space_bash` | Run a shell command (`space`, `command`, optional `timeout`). |
| `space_write` | Write text to a file. |
| `upload` / `download` | Copy files or folders in and out. |
| `send_file` | Drop a host file into the Space's Downloads (sha256 verified). |
| `list_tools` / `call_tool` | Reach MCP services running inside the Space. |

## Show it to the user

| Tool | Use |
|---|---|
| `open_space_viewer` | Open the full desktop viewer. |
| `show_space_pip` / `hide_space_pip` | Picture-in-picture on the user's screen. |
| `list_space_windows` / `stream_space_window` | Show one window from the Space. |
| `stream_endpoint` | Get a ticketed media URL for the desktop or a window. |

## Agents, apps and network

| Tool | Use |
|---|---|
| `agent_capabilities` | Which agent harnesses the Space supports. |
| `agent_start` | Start an agent run (`space`, `agent`, `prompt`). |
| `agent_status` / `agent_message` / `agent_stop` / `agent_list` | Follow, steer and stop runs. |
| `teleport_manifest` | Preview what moving an app session would copy. |
| `teleport_app` | Move a signed-in app session (tabs, profile) into the Space. |
| `hotspot_start` / `hotspot_status` / `hotspot_stop` | Share the host's network with a Space. |

## Set up a host over ssh (Tailscale or LAN)

To host Spaces on a machine you reach only over ssh (a spare Mac mini on the
user's Tailscale, or the LAN):

1. ssh into it (Tailscale is only the ssh transport, the same as any LAN or
   internet address).
2. Run the install script non-interactively:
   `curl -fsSL https://cua.ai/install.sh | sh -s -- -y --select spaces,host --no-onboarding`.
3. Sign in on the mini: `cua auth login --remote` prints a device code and a
   URL. Show both to the user and have them approve it (on another signed-in
   device or at the URL).
4. `cua host setup --profile spare --name "<name>"` hosts Spaces only (no
   desktop sharing), through the cua.ai relay.
5. Tell the user: the mini needs an active GUI login session (cua-spacesd
   runs as a LaunchAgent in the Aqua session, so it won't start at the
   login window; auto-login is recommended for a headless mini), and it
   needs a one-time grant of Screen Recording and Accessibility to
   cua-spacesd in System Settings.
6. From the laptop: `create_space(on="host:<name>", count=2)`, or
   `cua spaces create macos:26 --on "<name>" --count 2`.

`host:<name>` only resolves machines set up with `cua host setup` (they
register with the relay). `direct:<addr>` attaches one Space that is already
running at that address (`add_space`) and cannot host new ones.

## Remove Cua from a host (uninstall)

Work with the CLI while it still exists; deleting files first leaves the
machine registered on the relay and the systemd unit behind.

1. Inventory: `ps aux | grep -i cua`, `systemctl --user list-units --all | grep -i cua`,
   `command -v cua`, `ls -d ~/.cua ~/.local/share/cua-spaces ~/.local/bin/cua*`.
2. Unregister + tear down: `cua host remove --force --uninstalling`. `--force` is
   mandatory in a non-interactive shell (agents/scripts), and `--uninstalling` is
   mandatory while the host still provides Spaces — without it the command
   refuses. This one call drops the relay registration, the user systemd unit
   (`cua-spacesd-host.service`) and `~/.cua/host/` config.
3. `cua daemon stop`, then check `ps` again: the GUI `cua-spaces` process and its
   `cua mcp` child outlive `daemon stop`. Kill them by PID.
4. Delete data and binaries: `~/.cua`, `~/.local/share/cua-spaces` (hundreds of
   MB), `~/.local/bin/cua{,-driver,-spaces,-spacesd-linux-x86_64,-microvm-init}`,
   `~/.local/share/applications/cua-spaces.desktop`; `systemctl --user daemon-reload`.
   A leftover `/tmp/.mount_cua-*` fuse mount unmounts with the process.
5. Drop the MCP entry: `hermes config unset mcp_servers.cua` (never patch
   `~/.hermes/config.yaml` by hand — agent file-write tools refuse it). Tools
   already loaded in the running session stay callable until Hermes restarts.
6. Verify: `command -v cua` empty, `systemctl --user status cua-spacesd-host.service`
   `not-found`, `~/.cua` gone, and `grep -i cua ~/.hermes/config.yaml` empty.
   The `cua-*` skill docs stay on disk — ask before deleting them.

### Pitfalls

- **Never `pkill -f <pattern>` when your own command line contains that
  pattern** — `pkill -f cua-spaces` from a script that mentions `cua-spaces`
  matches the shell itself and kills it (exit 143, remaining steps silently
  skipped). Collect PIDs from `ps` and `kill <pid>`, or anchor the pattern.
- `cua host remove` prints only "This computer is no longer set up for access." —
  confirm the effect with `cua host status` (should report not set up) rather
  than trusting the one line.
- Don't stop at `cua daemon stop`: an installed AppImage/desktop launcher
  (`cua-spaces`) respawns the daemon on next login unless its binary and
  `.desktop` file are gone.

## Rules

- Run `teleport_manifest` and tell the user what will move before
  `teleport_app`; sensitive items need their explicit acknowledgement.
- Only start a hotspot when the Space needs the host's network (VPN,
  intranet), and stop it afterwards.
- Name the Space you used in your answer.

## Links to things you ran

Any link to something you ran (preview, dashboard, file): use `cua share`, never localhost; open it once to check it works before sending.

The `share` tool (or `cua share 3000`, `cua share space:dev:3000`, `cua share ./report.html`) returns a link that opens on the user's other signed-in devices, phone included. It checks the link loads and reports `check.ok`; do not send a link whose check failed. Links are private by default; use `access: "public"` with a `ttl` only when the user wants anyone to open it. `share_list` and `share_stop` manage them.

