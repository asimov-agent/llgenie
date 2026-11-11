---
name: omarchy-contributing
description: >-
  Guide for contributing to Omarchy — filing bugs, submitting PRs, and testing
  Hyprland Lua modules without a compositor. Use when the user wants to report
  an Omarchy bug, suggest a feature, or contribute a fix upstream.
---

# Omarchy Contributing

Guide for contributing to Omarchy — filing bugs, submitting PRs, and testing
Hyprland Lua modules without a compositor.

## Reporting Issues and Submitting PRs

Omarchy lives at https://github.com/omacom/omarchy. Route requests to the
right place:

- **Verified bugs** -> GitHub issues. Issues are for validated bugs only, not
  support requests.
- **Feature ideas and suggestions** ->
  https://github.com/omacom/omarchy/discussions/categories/suggestions
- **Support and "is this a bug?" questions** -> the Discord community at
  https://omarchy.org/discord. Start here when the problem isn't clearly a bug
  in Omarchy itself.

## Filing a Good Bug Report

The bug template asks for system details (CPU, GPU, Omarchy version), a
description with steps to reproduce, and diagnostics. Gather them:

```bash
omarchy version

# Generate the diagnostic log (also written to /tmp/omarchy-debug.log)
omarchy debug --no-sudo --print

# Interactive variant: `omarchy debug` offers to upload the log to
# logs.omarchy.org (expires after 24h) and prints a shareable URL to
# include in the issue.
```

**Capture the problem on screen.** A screenshot or short recording of the bug
is often worth more than the description — see `capture.md` for
`omarchy capture screenshot` and `omarchy screenrecord`. Keep recordings short
and focused on the misbehavior. GitHub issue attachments are added by
drag-and-drop in the web form, so save the capture and hand the user the file
path to attach (`gh` cannot upload media).

For screen-recording failures specifically, rerun with
`OMARCHY_SCREENRECORD_DEBUG=true` and attach `/tmp/omarchy-screenrecord.log`.

File the issue with `gh` when available:

```bash
gh issue create --repo omacom/omarchy --title "..." --body "..."
```

Include: what happened, what was expected, steps to reproduce, system details,
the debug log URL (or attached log), and the capture.

## Submitting a PR

Never develop against `/usr/share/omarchy`. Clone a working copy instead:

```bash
gh repo fork omacom/omarchy --clone
cd omarchy
```

**Check for competing PRs first.** Search existing PRs before writing code — someone else may already be fixing the same bug:

```bash
gh pr list --repo omacom/omarchy --search "<keyword>" --state open
```

If someone else is already fixing the same bug, consider collaborating on their PR instead of opening a competing one. A complementary comment with your findings or a gap you identified is often more valuable than a separate PR.

**Target upstream, not your fork.** The PR base should be `omacom/omarchy` (the upstream repo), not your fork. If you already pushed to your fork, you can change the PR target or create a new PR against upstream.

Follow the repository's own `AGENTS.md` for style, testing, and commit conventions — it is the authority on contributions. Keep commits atomic (a single squashed commit per fix), run `./test/all` before pushing, and open the PR with `gh pr create`. A PR that fixes a visual problem should include before/after captures.

### PR Workflow

1. Fork and clone the upstream repo
2. **Search for competing PRs** — `gh pr list --repo omacom/omarchy --search "<keyword>"`
3. Create a feature branch from `upstream/quattro` (see below)
4. Make changes following `AGENTS.md` conventions
5. **Update existing tests** — when adding config changes (e.g., new flags in `chromium-flags.conf`), check if existing tests reference that file and update them too
6. Add new tests in `test/shell.d/<name>-test.sh`
7. Hardware detection scripts (`omarchy-hw-*`) must support `OMARCHY_*_PATH` env var stubbing for tests (e.g., `OMARCHY_PCI_DEVICES_PATH` for nvidia, `OMARCHY_DMI_ID_PATH` for MSI). Add the env var support to the detector before writing tests against it.
8. Run tests: `./test/cli && ./test/shell.d/<name>-test.sh`
9. Squash to a single atomic commit
10. Push and create PR against `omacom/omarchy` (upstream)
11. Comment on related issues linking to your PR

### Branching from upstream (critical)

The fork's `quattro` branch **diverges from upstream** after the first PR attempt. You cannot push directly to your fork's `quattro` or force-push to it — GitHub rejects non-fast-forward pushes. Instead:

```bash
# Add upstream remote if not already present
git remote add upstream https://github.com/omacom/omarchy.git
git fetch upstream quattro

# Create your fix branch from upstream/quattro, NOT your fork's quattro
git checkout -b fix/<topic> upstream/quattro

# Cherry-pick your changes from the old branch
git cherry-pick <commit-hash>

# Push to your fork
git push -u origin fix/<topic>

# Create PR against upstream
gh pr create --repo omacom/omarchy --base quattro --head andyholst:fix/<topic>
```

**CRITICAL: Test on real hardware, not just code.** After writing the install script, actually run it on the target machine and verify all post-install steps succeed. The user explicitly called this out — writing code isn't enough, you need to install and test on the actual laptop. Pattern:
1. Write the install script in the repo
2. Run with `sudo env "PATH=$PATH OMARCHY_PATH=/usr/share/omarchy OMARCHY_INSTALL=/usr/share/omarchy/install" bash install/hardware/msi.sh`
3. Verify modules loaded, services enabled, files created, no conflicts
4. Reboot and confirm the new UKI works

**Always check for competing PRs first.** Search existing PRs with `gh pr list --repo omacom/omarchy --search "<keyword>"` before writing code. If someone else is already fixing the same area, collaborate instead of competing. Cross-reference related PRs in your PR description. For example, the MSI script uses sysfs instead of lspci — explicitly mention PR #11259 in the PR body.

**Limine bootloader recovery.** Omarchy uses Limine, not GRUB. If a UKI modification breaks boot:
- Limine snapshot entries in `/boot/limine.conf` (previous UKI hashes)
- `limine.conf.old` backup of the pre-modification config
- `@factory` btrfs subvolume (clean Omarchy factory install)

**sudo in Hermes sessions.** When running under Hermes, `sudo` writes to system paths get blocked by the Tirith security scanner. Either set `SUDO_PASSWORD` in `~/.hermes/.env` or surface the exact commands for the user to run in their own terminal.

### Competing PR Strategy

If a competing PR exists that covers the root cause more thoroughly:
1. **Close your PR** — don't leave duplicate PRs open
2. **Comment on theirs** with gaps your PR identified (e.g., missing config flags)
3. **Link to your closed PR** so they can pull in your changes
4. **Comment on related issues** linking to the surviving PR

This is better than maintaining a competing PR — upstream maintainers prefer one comprehensive fix over multiple partial ones.

### Squash Commits (User Preference)

The user prefers **a single squashed commit** for a fix, not multiple atomic commits. Even though Omarchy's `AGENTS.md` says "commits should be atomic," the user's preference overrides this — one fix = one commit. Squash before pushing:

```bash
git reset --soft HEAD~N
git commit -m "fix: <description>"
```

### Testing Hyprland Lua config modules

Modules like `default/hypr/nvidia.lua` run inside Hyprland and use the `hl` and
`o` tables. To test them without a compositor, stub those tables and point
`OMARCHY_PATH` at a temporary directory containing only the `default/` symlink
and mock hardware-detection commands in `bin/`:

```lua
-- Stub hl.env to capture what the module sets
local captured = {}
hl = {
  env = function(name, value) captured[name] = value end,
  config = function() end,
  -- ... stub other hl.* functions as needed
}

-- Stub o.shell_succeeds to read exit codes from mock commands
o = {
  shell_succeeds = function(cmd)
    local success = os.execute(cmd .. ' >/dev/null 2>&1')
    return success == true
  end,
  shell_quote = function(path)
    return "'" .. path:gsub("'", "'\\''") .. "'"
  end,
}

package.path = os.getenv("OMARCHY_PATH") .. "/?.lua;" .. package.path
dofile(os.getenv("OMARCHY_PATH") .. "/default/hypr/nvidia.lua")
```

Then assert on `captured.LIBVA_DRIVER_NAME`, `captured.__GLX_VENDOR_LIBRARY_NAME`,
etc. Put the Lua harness in `test/shell.d/fixtures/<name>.lua` and the bash
driver in `test/shell.d/<name>-test.sh`. Source `test/shell.d/base-test.sh`
for `pass`, `fail`, and `require_command`.

Mock hardware commands by creating a temp `bin/` with scripts that exit 0
(yes) or 1 (no), then set `OMARCHY_PATH` to the temp directory. The module
constructs paths as `paths.omarchy_path .. "/bin/omarchy-hw-*"`, so the mocks
must live at `$OMARCHY_PATH/bin/`.

**Pitfalls:**
- **chmod +x on bin/ scripts**: New files in `bin/` need `chmod +x` or they fail
  with "Permission denied" when invoked directly. Don't forget this after creating
  new detector scripts.
- **sudo in install scripts**: `install/hardware/*.sh` run as root during Omarchy
  setup — don't add `sudo`, use plain commands.
- **jq path**: Lua harness prints `{ "env": { ... }, "order": [...] }`. Use
  `.env.LIBVA_DRIVER_NAME`, not `.LIBVA_DRIVER_NAME`.
- **os.execute**: Returns `true` (not 0) for exit 0 in Lua 5.3+. Use
  `return success == true`, not `success == 0`.

See `references/hybrid-gpu-vaapi.md` for a worked example of this pattern.

## Key Pitfall: GitHub Duplicate Issue Commenting

When the same root cause produces multiple open issues, do NOT paste the same
full analysis to every issue. Instead:

1. Find the canonical issue (most comments/traction) — that's the one that
   holds the full root-cause analysis, regression history, and workaround.
2. For all other duplicates, post a brief comment:
   - States `Duplicate of #<canonical>`
   - Includes a one-line summary of the fix/workaround
   - Does NOT duplicate the full analysis
3. Verify your own comments are actually on the right issues — don't assume.
   Cross-reference issue numbers before posting.

This avoids noise and keeps discussion focused. The user explicitly called
this out — pasting the same wall to 7 duplicate issues is not useful.

Verify PR status before claiming merged: `gh pr view <num> --json state,mergedAt`.
A PR with `state=CLOSED` and `mergedAt=null` was closed without merge. Zero fix
PRs for a given bug means no upstream fix has landed — every upgrade re-regresses.

## Key Pitfall: MSI Laptop Drivers

MSI Titan GT77HX and similar laptops need vendor-specific drivers (r8125-dkms,
msi-ec-dkms-git, coolercontrol, nvidia-settings) and the r8169 driver blacklisted.

See `references/msi-driver-optimization.md` for the full pattern.

**RGB REMOVED from MSI contribution**: The Titan GT77HX uses a Cherry MX
mechanical keyboard that `msi-perkeyrgb` does NOT support. The tool exits
cleanly (code 0) but does not light up the keyboard. After testing, RGB
support was **completely removed** from the PR — no config files, no udev
rules, no package install, no tests. Do NOT include RGB in MSI laptop PRs.
If a future contribution adds RGB, it must clearly state which models it
actually works on (e.g., GE63/GE73 with 1038:1122) and exclude Titan/GT77.

## Issue Verification Discipline

When verifying PR correctness against an issue before posting, never report
false gaps. Common mistakes to avoid:

1. **Installed-system state vs PR content** — If an install script exists
   in the PR diff but not on the installed system, that is expected (PR not
   merged yet), NOT a gap. Verify against the PR diff, not the installed
   state.
2. **Silent features** — Read the actual script content carefully. If the
   script sets battery thresholds or blacklists a driver, it exists — don't
   claim it's missing without reading.
3. **Scope removal** — If a feature (RGB) was intentionally removed from
   scope, it is NOT a gap. It was the right call based on hardware reality.

Posting false "gaps" in a verification comment undermines trust in the PR.
Cross-check every claim against the actual source code before posting.

## Key Pitfall: Hybrid GPU VA-API

On hybrid NVIDIA laptops where the panel scans out through Intel, setting
`LIBVA_DRIVER_NAME=nvidia` breaks Chromium video decode (black screen, spinner,
audio-only). Additionally, GL rendering defaults to NVIDIA, causing rendering
glitches because NVIDIA-rendered frames must cross the PCIe bus to the Intel
compositor — so both VA-API AND GL must be forced to Intel for browsers.

**For end-user systems:** Scope the fix to browser wrappers only — the user
explicitly wants this, not a global change. System stays `nvidia`.

Modified files on this system:
- `/usr/bin/brave` — wrapper script, add env vars before `exec /opt/brave-bin/brave`
- `/usr/bin/google-chrome-beta` — wrapper script, add env vars before `exec`
- `/usr/bin/chromium` — wrapper around `/usr/bin/chromium.real` (original moved)
- `/etc/chromium-flags.conf` — add `--enable-features=VaapiVideoDecoder,VaapiIgnoreDriverChecks`
  and `--disable-features=UseChromeOSDirectVideoDecoder`

Env vars for each browser wrapper:
```bash
export LIBVA_DRIVER_NAME=iHD
export MESA_LOADER_DRIVER_OVERRIDE=iris
```

The `MESA_LOADER_DRIVER_OVERRIDE=iris` forces Intel for GL rendering too,
avoiding the cross-GPU copy issue entirely. Without it, Chrome has rendering
glitches even when video decode works.

**Pitfall — Hyprland Lua override path is WRONG for this.** `bootstrap.lua`
adds `~/.config/?.lua` to Lua's package.path, so `require("default.hypr.nvidia")`
resolves to `~/.config/default/hypr/nvidia.lua`, NOT
`~/.config/omarchy/default/hypr/nvidia.lua`. Wrong path = override silently
ignored.

**For upstream contributions:** See `references/hybrid-gpu-vaapi.md` for the
full pattern (driver selection in `nvidia.lua` + browser flags in
`chromium-flags.conf`).

## Key Pitfall: Hermes Update for System Plugins

To update Hermes core and native plugins (including hermes-jev):
```bash
hermes update        # updates Hermes core + native plugins
hermes skills update # updates skills (separate system)
hermes plugins update <name> # update a specific plugin (e.g., hermes-jev)
```

Native plugins (like hermes-jev) ship with the Hermes package, not the skills
hub. `hermes update` bumps them. Skills update via `hermes skills update`.

**Per-profile updates.** Both skills and plugins are per-profile. To update
ALL profiles, loop through them:
```bash
# Update skills for all profiles
for profile in default ai-matrix-trends architect coder devops hermes-llm omarchy-llm pm pr-reviewer product-owner release reviewer security singularity sre tester; do
  echo "=== $profile ==="
  hermes skills update --profile "$profile" 2>&1 | tail -1
  hermes plugins update hermes-jev --profile "$profile" 2>&1 | tail -1
done
```

**Profile activation.** To switch the default profile for new terminals:
```bash
hermes profile use <name>     # set default profile
hermes -p <name>              # or use per-invocation
```

**List plugins per profile (JSON for parsing):**
```bash
hermes plugins list --profile <name> --json 2>&1 | python3 -c "import sys,json; [print(f'{p[\"name\"]} | {p[\"status\"]}') for p in json.load(sys.stdin)]"
```

## Key Pitfall: Mac Broadcom Wi-Fi

Older MacBooks (Air 5,2 2012) have BCM43224 (14e4:4353) not detected by
`fix-bcm43xx.sh`. The open-source `brcmsmac` claims the device first, preventing
`broadcom-wl-dkms` from attaching. Fix: detect the chip and blacklist b43/brcmsmac/bcma.

See `references/mac-broadcom-wifi.md` for the full pattern.

## Commit Convention

The user prefers **a single squashed commit** for a fix, not multiple atomic
commits. When contributing, squash related changes into one commit before
pushing. The Omarchy repo's `AGENTS.md` says "commits should be atomic" but
the user's preference overrides this — one fix = one commit.
