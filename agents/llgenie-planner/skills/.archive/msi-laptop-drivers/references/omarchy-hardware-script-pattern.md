# Omarchy Hardware Install Script Pattern

How to add a new hardware vendor to Omarchy's install system.

## File Layout

```
bin/omarchy-hw-<vendor>          # Detection script (exit 0 = match, exit 1 = no)
install/hardware/<vendor>.sh     # Install + configure drivers
install/hardware/all.sh          # Wire the vendor script in
test/shell.d/hw-<vendor>-test.sh # Detection tests via env-var stubs
```

## Detection Script (`bin/omarchy-hw-<vendor>`)

- Reads DMI IDs from `/sys/class/dmi/id/` (or `$OMARCHY_DMI_ID_PATH` for test stubs)
- Exits 0 if the system matches the vendor, 1 otherwise
- Must be executable (`chmod +x`)
- Must have `omarchy:summary=` metadata comment
- Support `OMARCHY_DMI_ID_PATH` env var for test stubs (same pattern as `OMARCHY_PCI_DEVICES_PATH`)

Example:
```bash
#!/bin/bash
# omarchy:summary=Detect whether the computer is an MSI laptop.

dmi_path="${OMARCHY_DMI_ID_PATH:-/sys/class/dmi/id}"
sys_vendor=$(cat "$dmi_path/sys_vendor" 2>/dev/null)
[[ $sys_vendor == "Micro-Star International Co., Ltd." ]] || exit 1
# ... additional checks ...
exit 0
```

## Install Script (`install/hardware/<vendor>.sh`)

- Guarded by `if omarchy-hw-<vendor>; then ... fi`
- Uses `omarchy-pkg-add` for package installation (handles pacman + AUR)
- Uses `sudo` for system-level changes (mkinitcpio, systemctl, writing to /etc)
- **CRITICAL**: Add `set -euo pipefail` for proper error handling
- Use `omarchy-pkg-present` to skip already-installed packages
- Use `sudo install -Dm644 /dev/stdin <path> <<'EOF'` for atomic system file writes (NOT `echo >`)
- Guard blacklists: only blacklist a module if the replacement is actually loaded
- Disables conflicting services (e.g., thermald when coolercontrol is used)

Example structure:
```bash
set -euo pipefail

if omarchy-hw-<vendor>; then
  if ! omarchy-pkg-present some-pkg 2>/dev/null; then
    omarchy-pkg-add some-pkg || echo "WARNING: Failed to install some-pkg" >&2
  fi

  # Atomic file write
  sudo install -Dm644 /dev/stdin /etc/modprobe.d/some.conf <<'EOF'
blacklist some_module
EOF
fi
```

## Wiring Into all.sh

Add to `install/hardware/all.sh`:
```bash
run_logged "$OMARCHY_INSTALL/hardware/<vendor>.sh"
```

Place near other vendor scripts (asus-rog, framework16, etc.).

## Testing

1. **Detection**: Set `OMARCHY_DMI_ID_PATH` to a temp dir with stub files, run the detector
2. **Install**: Copy detector to `/usr/share/omarchy/bin/`, run install script with sudo
3. **Verify**: Check all files created, services enabled/disabled, modules loaded
4. **Test script**: Run the actual install script on the target machine, not just detection logic

## Contribution Workflow

1. Fork `omacom/omarchy` to your GitHub account
2. Branch from upstream `quattro` (NOT local quattro — may have cherry-picks): `git fetch upstream quattro && git checkout -b feat/<description> upstream/quattro`
3. Make changes, squash to one atomic commit
4. Push to your fork, create PR with `gh pr create --repo omacom/omarchy --base quattro --head <user>:<branch>`
5. Link related issues in commit message (`Fixes #NNNN`)
6. Cross-reference related PRs in PR body (e.g. "Related: #11259")
7. Run tests: `bash test/shell.d/hw-<vendor>-test.sh` and `bash test/cli`

## Common Pitfalls

- **Don't lump general laptop issues into vendor-specific work**: Hybrid GPU browser fixes, VA-API, Widevine CDM apply to ALL laptops with those GPUs — not just one vendor.
- **Rebase onto upstream/quattro**: Your local quattro may have cherry-picked commits from other work. Always rebase to avoid polluting PR history with unrelated commits.
- **Use sysfs reads, not lspci**: `lspci` reads PCI config space and wakes suspended GPUs. Use `/sys/bus/pci/devices/*/vendor` + `device` instead.
- **Don't just write code — test it**: Actually run the install script on the real hardware and verify everything works end-to-end.
