---
name: msi-laptop-drivers
description: >-
  Install and manage drivers for MSI laptops on Arch Linux. Covers networking
  (Killer E-series), fan/thermal management, embedded controller access, and
  NVIDIA GPU settings. Triggers: MSI laptop, MSI Titan, MSI Stealth, MSI Raider,
  MSI Vector, MSI Crosshair, MSI Summit, msi-ec, r8125, coolercontrol,
  Killer E3000, MSI fan control, MSI EC, nvidia-settings.
---

# MSI Laptop Drivers (Arch Linux)

Install drivers for MSI gaming/workstation laptops on Arch Linux.

## When to use

When the user has an MSI laptop and needs drivers for:
- 2.5GbE networking (Killer E-series, Realtek RTL8125B)
- RGB keyboard control
- Fan curves and thermal management
- Embedded controller (EC) access
- NVIDIA GPU settings (for MSI laptops with dGPU)

## Identification

Identify the laptop model first:

```bash
cat /sys/class/dmi/id/product_name   # e.g., "Titan GT77HX 13VI"
cat /sys/class/dmi/id/sys_vendor     # "Micro-Star International Co., Ltd."
```

Then check what hardware is present:

```bash
lspci | grep -iE "network|ethernet|nvidia|vga"
lsusb | grep -i "17e9"               # DisplayLink devices
```

## Driver Set

Common MSI laptop drivers available on Arch Linux:

| Driver | Package | Purpose | Source |
|--------|---------|---------|--------|
| r8125-dkms | r8125-dkms | Killer E3000 / RTL8125B 2.5GbE alt driver | AUR |
| msi-perkeyrgb | msi-perkeyrgb | RGB keyboard control | AUR |
| coolercontrol | coolercontrol | Fan/thermal GUI + daemon | AUR |
| coolercontrold | coolercontrold | CoolerControl daemon (dependency of coolercontrol) | AUR |
| msi-ec-dkms-git | msi-ec-dkms-git | MSI Embedded Controller driver | AUR |
| nvidia-settings | nvidia-settings | NVIDIA GPU GUI settings | Extra repo |

> **Note:** `r8169` (kernel built-in) often works for Killer E3000, but `r8125-dkms`
> can be more stable for sustained 2.5GbE throughput.

> **Note:** `msi-ec-dkms-git` provides EC access for fan modes, battery thresholds,
> and other laptop-specific features. It requires DKMS to rebuild on kernel updates.

> **Note:** `coolercontrol` depends on `coolercontrold`. Installing `coolercontrol`
> pulls in `coolercontrold` automatically via AUR resolver.

## Installation

### Full install (all MSI laptop drivers)

```bash

# nvidia-settings from official repos
sudo pacman -S --noconfirm nvidia-settings

# AUR packages
yay -S --noconfirm r8125-dkms msi-perkeyrgb coolercontrol msi-ec-dkms-git
```

### Individual drivers

```bash

# Networking only
yay -S --noconfirm r8125-dkms

# RGB keyboard only
yay -S --noconfirm msi-perkeyrgb

# Fan/thermal only
yay -S --noconfirm coolercontrol

# EC driver only
yay -S --noconfirm msi-ec-dkms-git
```

### With paru

```bash
paru -S --noconfirm r8125-dkms msi-perkeyrgb coolercontrol msi-ec-dkms-git
```

## Post-install

For DKMS-based drivers (r8125-dkms, msi-ec-dkms-git), verify module status:

```bash
dkms status
```

For `coolercontrol`, enable and start the daemon:

```bash
sudo systemctl enable --now coolercontrold
```

For `nvidia-settings`, no service needed — just launch the GUI:

```bash
nvidia-settings
```

## Running Install Scripts

Omarchy install scripts live at `$OMARCHY_INSTALL/hardware/` and can be run directly on an installed system. They use `omarchy-pkg-add` and `omarchy-hw-*` helpers from `$OMARCHY_PATH/bin/`.

To run an install script directly:

```bash
sudo env "PATH=$PATH OMARCHY_PATH=/usr/share/omarchy OMARCHY_INSTALL=/usr/share/omarchy/install" bash /path/to/install/hardware/msi.sh
```

This works because `omarchy-pkg-add` is already in `/usr/share/omarchy/bin/` and handles both pacman and AUR packages.

**CRITICAL: Install and test on the target machine, not just detection logic.**

Writing the code is step 1. After writing, actually run the install script on the real hardware and verify everything works end-to-end. The user explicitly called this out — "did you actually try to install the drivers and test them?"

Post-install verification checklist:
1. DKMS modules loaded: `lsmod | grep r8125` and `lsmod | grep msi_ec`
2. No conflicts: `lsmod | grep r8169` should be empty (r8169 blacklisted)
3. Thermal service: `systemctl is-active thermald` should be `inactive`, `systemctl is-active coolercontrold` should be `active`
4. EC features accessible: `ls /sys/devices/platform/msi-ec/` should show shift_mode, fan_mode, cooler_boost, etc.
5. UKI rebuilt: check `/boot/EFI/Linux/omarchy_linux.efi` exists and is newer than the old one
6. Packages: `pacman -Q r8125-dkms msi-perkeyrgb coolercontrol msi-ec-dkms-git nvidia-settings`
7. Reboot and confirm blacklist takes effect: `lsmod | grep r8169` returns nothing

## Post-install Verification & Optimization

After installing drivers, verify no conflicts and apply optimizations:

### Comprehensive Verification Commands

Run these after install AND after reboot to confirm everything is working:

```bash

# 1. Detector works
omarchy-hw-msi && echo "PASS: MSI detected" || echo "FAIL: MSI not detected"

# 2. DKMS modules loaded
lsmod | grep -q r8125 && echo "PASS: r8125 loaded" || echo "FAIL: r8125 not loaded"
lsmod | grep -q msi_ec && echo "PASS: msi_ec loaded" || echo "FAIL: msi_ec not loaded"

# 3. No r8169 conflict
lsmod | grep -q r8169 && echo "FAIL: r8169 still loaded" || echo "PASS: r8169 not loaded"

# 4. Thermal service state
systemctl is-active thermald &>/dev/null && echo "FAIL: thermald still active" || echo "PASS: thermald inactive"
systemctl is-active coolercontrold &>/dev/null && echo "PASS: coolercontrold active" || echo "FAIL: coolercontrold not active"

# 5. EC features accessible
ls /sys/devices/platform/msi-ec/shift_mode &>/dev/null && echo "PASS: EC shift_mode accessible" || echo "FAIL: EC shift_mode missing"

# 6. EC writable (test write then restore)
echo "eco" | sudo tee /sys/devices/platform/msi-ec/shift_mode >/dev/null && echo "PASS: EC writable" && echo "comfort" | sudo tee /sys/devices/platform/msi-ec/shift_mode >/dev/null

# 7. Fan detection via msi_wmi_platform
ls /sys/class/hwmon/hwmon*/name 2>/dev/null | xargs grep -l msi_wmi_platform 2>/dev/null && echo "PASS: msi_wmi_platform hwmon found" || echo "FAIL: msi_wmi_platform hwmon missing"

# 8. NVIDIA settings functional
nvidia-settings -q gpucoretemp &>/dev/null && echo "PASS: nvidia-settings works" || echo "FAIL: nvidia-settings not working"

# 9. NVIDIA power state
cat /sys/class/drm/card1/device/power_state 2>/dev/null | grep -q D0 && echo "PASS: dGPU in D0" || echo "FAIL: dGPU not in D0"

# 10. all.sh wiring (if applicable)
grep -q msi.sh /usr/share/omarchy/install/hardware/all.sh && echo "PASS: all.sh wired" || echo "FAIL: all.sh NOT wired"

# 11. Configuration files present (RGB removed)
ls /etc/modprobe.d/r8169.conf &>/dev/null && echo "PASS: r8169 blacklist exists" || echo "FAIL: r8169 blacklist missing"
ls /etc/modules-load.d/r8125.conf &>/dev/null && echo "PASS: r8125 early-load exists" || echo "FAIL: r8125 early-load missing"
ls /etc/modules-load.d/msi-ec.conf &>/dev/null && echo "PASS: msi-ec early-load exists" || echo "FAIL: msi-ec early-load missing"
ls /etc/mkinitcpio.conf.d/msi.conf &>/dev/null && echo "PASS: mkinitcpio msi.conf exists" || echo "FAIL: mkinitcpio msi.conf missing"
ls /etc/X11/xorg.conf.d/10-nvidia-dpms.conf &>/dev/null && echo "PASS: NVIDIA DPMS config exists" || echo "FAIL: NVIDIA DPMS config missing"
```

### 1. Check for driver conflicts

```bash
lsmod | grep -E "r8169|r8125"   # Should show only r8125
lsmod | grep msi_ec              # Should show msi_ec loaded
```

If both `r8169` and `r8125` are loaded, blacklist `r8169`:

```bash
echo "blacklist r8169" | sudo tee /etc/modprobe.d/r8169.conf
sudo mkinitcpio -P

# Reboot required to apply blacklist
```

### 1b. Limine bootloader (MSI Titan GT77HX)

The MSI Titan GT77HX uses Limine, not GRUB. `mkinitcpio -P` automatically detects Limine and generates a UKI at `/boot/EFI/Linux/omarchy_linux.efi`. No separate `grub-mkconfig` needed. The `limine-mkinitcpio-hook` package handles this.

### 2. Disable conflicting thermal services

`thermald` and `tlp` conflict with `coolercontrold`. Disable them:

```bash
sudo systemctl disable --now thermald tlp
sudo systemctl enable --now coolercontrold
```

### 3. Verify EC features are accessible

```bash
ls /sys/devices/platform/msi-ec/
cat /sys/devices/platform/msi-ec/shift_mode
cat /sys/devices/platform/msi-ec/fan_mode
```

### 4. NVIDIA xorg.conf.d (DPMS, brightness control)

Create `/etc/X11/xorg.conf.d/10-nvidia-dpms.conf`:

```bash
sudo mkdir -p /etc/X11/xorg.conf.d
sudo tee /etc/X11/xorg.conf.d/10-nvidia-dpms.conf << 'EOF'
Section "Device"
    Identifier "NVIDIA Card"
    Driver "nvidia"
    Option "RegistryDwords" "EnableBrightnessControl=1"
EndSection

Section "Screen"
    Identifier "Screen0"
    Device "NVIDIA Card"
    Option "AllowNVIDIAGPUScreens" "on"
EndSection
EOF
```

### 5. Verify NVIDIA power state

```bash
cat /sys/class/drm/card*/device/power_state   # Should show D0
```

See `references/msi-titan-gt77hx.md` for model-specific optimization notes.

## RGB Support Removed

The previous version of this PR included RGB support (`msi-perkeyrgb`, udev rules, config files). After testing on real hardware, RGB support was **removed entirely** because the Titan GT77HX uses a Cherry MX mechanical keyboard that `msi-perkeyrgb` does NOT support.

If a future PR adds RGB support back, it must:
- Only target models that actually work (GE63/GE73 with 1038:1122)
- Explicitly exclude Titan/GT77
- Verify with real hardware that the keyboard actually lights up

When creating or updating `install/hardware/msi.sh`, ensure it handles all of these:

### Required Steps

| # | Step | Verification |
|---|------|------------|
| 1 | Install `r8125-dkms` if RTL8125B detected via sysfs | `dkms status` shows r8125 |
| 2 | Blacklist `r8169` ONLY if r8125 is loaded | `lsmod \\| grep r8169` returns nothing |
| 3 | Install `msi-ec-dkms-git` if not loaded | `lsmod \\| grep msi_ec` |
| 4 | Install `coolercontrol` if not present | `pacman -Q coolercontrol` |
| 5 | Disable `thermald`, enable `coolercontrold` | `systemctl is-active coolercontrold` |
| 6 | Install `nvidia-settings` if NVIDIA dGPU present | `omarchy-hw-nvidia` |
| 7 | Create X11 DPMS config | `ls /etc/X11/xorg.conf.d/10-nvidia-dpms.conf` |
| 8 | **Set battery charge thresholds** | Check `BAT1/charge_control_*` |
| 9 | Early-load msi_ec via mkinitcpio if loaded | `ls /etc/mkinitcpio.conf.d/msi.conf` |

**Note**: RGB support (msi-perkeyrgb) was **intentionally removed** from this PR. The Titan GT77HX 13VI uses a Cherry MX mechanical keyboard that msi-perkeyrgb does NOT support. RGB was removed from the PR, tests, and documentation — do NOT add it back.

### Battery Charge Thresholds

MSI laptops expose charge control via standard power_supply sysfs. Set thresholds only when on DC power (status == "Discharging") to avoid interfering with AC-powered usage:

```bash
if [[ $(cat /sys/class/power_supply/BAT1/status) == "Discharging" ]]; then
  echo 60 | sudo tee /sys/class/power_supply/BAT1/charge_control_start_threshold
  echo 80 | sudo tee /sys/class/power_supply/BAT1/charge_control_end_threshold
fi
```

### USB Detection

msi-perkeyrgb internally calls `lsusb` to find keyboards. Install `usbutils` if not present:

```bash
sudo pacman -S --noconfirm usbutils
```

### Style Requirements for msi.sh

- `set -euo pipefail` at top
- Guard behind `omarchy-hw-msi` detection
- `omarchy-pkg-present` checks before installing (skip if already installed)
- `install -Dm644 /dev/stdin` for atomic system file writes (never `echo >`)
- `tee` for sysfs writes (never direct redirect)
- Only blacklist r8169 if r8125 is actually loaded (guard against network loss)
- **NO `local` keyword** — install scripts are sourced, not executed as functions. `local` at top level causes: `line N: local: can only be used in a function`

## Cooler Boost Watcher (omarchy-msi-cooler-boost-watch)

On Titan GT77HX (and other MSI laptops where CoolerControl cannot PWM the fans — RPM-only), Omarchy ships a systemd watcher that flips the EC `cooler_boost` flag directly. It is the mechanism behind "Cooler Boost after 30s sustained 85C".

- **Script:** `/usr/bin/omarchy-msi-cooler-boost-watch`
- **Service:** `omarchy-msi-cooler-boost-watch.service`
- **EC flag:** `/sys/devices/platform/msi-ec/cooler_boost`
- **Temps:** `/sys/devices/platform/msi-ec/{cpu,gpu}/realtime_temperature`

### Behavior & tunables (env vars, set in the systemd unit)

| Env | Default | Meaning |
|-----|---------|---------|
| `MSI_COOLER_BOOST_ON_AT` | 85 | turn on when CPU/GPU >= this (C) |
| `MSI_COOLER_BOOST_OFF_AT` | 70 | turn off when both <= this (C) — hysteresis |
| `MSI_COOLER_BOOST_SUSTAIN` | 30 | seconds of sustained high temp before on |
| `MSI_COOLER_BOOST_INTERVAL` | 5 | poll interval (s) |
| `MSI_COOLER_BOOST_MAX_ON` | 300 | force-off after this many seconds on (0 = no cap) |
| `MSI_COOLER_BOOST_COOLDOWN` | 600 | lockout seconds after forced off before re-trigger (0 = none) |

The `MAX_ON`/`COOLDOWN` pair implements a duty-cycle cap: boost runs at most 5 min, then stays off 10 min even if temps are still high. State is tracked in `/run/omarchy-msi-cooler-boost.{sustain,on_since,cooldown_until}`.

### User's chosen mode (Titan GT77HX)

Threshold mode, NOT the `--duty` 5-on/10-rest cycle (user rejected the rest period). Unit:
`ExecStart=/usr/bin/omarchy-msi-cooler-boost-watch` with `MSI_COOLER_BOOST_SUSTAIN=120`
(boost on after 2 min >= 85C, stays on until <= 70C). The sustain check is `>=`, not `>`.
The old `--duty` mode crashed under `set -e`: `[[ ]] && (( gpu > hot )) && hot=$gpu` as the
last line of `read_hot` returns 1 when the GPU is cooler than the CPU, which kills the script. Use an `if` statement.
When the user says "just check systemctl", run only `systemctl show/is-active` + journal, no
fake-EC tests or long loops.

### Editing the installed watcher

The `patch` tool cannot write to `/usr/bin` (permission denied). Edit a copy in `/tmp`, then install with sudo and restart:

```bash

# edit /tmp/omarchy-msi-cooler-boost-watch, then:
bash -n /tmp/omarchy-msi-cooler-boost-watch && echo "SYNTAX OK"
sudo install -m 0755 /tmp/omarchy-msi-cooler-boost-watch /usr/bin/omarchy-msi-cooler-boost-watch
sudo systemctl restart omarchy-msi-cooler-boost-watch
systemctl is-active omarchy-msi-cooler-boost-watch
journalctl -u omarchy-msi-cooler-boost-watch --no-pager -n 5   # confirm new tunables in startup line
sudo /usr/bin/omarchy-msi-cooler-boost-watch --once             # smoke test, exit 0
```

The startup log echoes the active tunables (`max_on=300s cooldown=600s`) — confirm the new values there. `--once` runs a single decision pass without the loop.

**The installed script can diverge from the source repo.** The canonical clean
version lives at `bin/omarchy-msi-cooler-boost-watch` in the Omarchy source
checkout (`/home/asimov/repository/git/linux-omarchy-contribution/omarchy/`);
the installed `/usr/bin` copy may carry a local modification (e.g. a
MAX_ON/COOLDOWN duty-cycle cap) that the source does not. Before hand-editing,
`diff` the installed script against the source version — if the user wants to
revert a local mod (like removing the cooldown cap), the cleanest fix is to
`sudo cp` the source version over the installed one, not to surgically remove
the added blocks. Always back up the installed script first
(`sudo cp /usr/bin/... /usr/bin/....bak-<reason>`).

### Fetching the watcher source from the PR

The `contents` API 404s on the PR's branch ref (`feat/msi-titan-cooler-boost`). Use the PR diff instead:

```bash
gh pr diff 12003 --repo omacom/omarchy > /tmp/pr.diff
awk '/^diff --git a\/bin\/omarchy-msi-cooler-boost-watch/,/^diff --git a\/default/' /tmp/pr.diff
```

## Reinstalling

### Skip if up-to-date (default)
```bash
yay -S --noconfirm --needed r8125-dkms msi-perkeyrgb coolercontrol msi-ec-dkms-git
sudo pacman -S --noconfirm --needed nvidia-settings
```

### Force reinstall (user explicitly asks)
When the user says "force update" or "reinstall", rebuild and reinstall even if the same version:

```bash
yay -S --noconfirm r8125-dkms msi-perkeyrgb coolercontrol msi-ec-dkms-git evdi-dkms displaylink
sudo pacman -S --noconfirm nvidia-settings
```

This triggers DKMS module removal/rebuild and package reinstallation. Takes 2-5 minutes.

## Troubleshooting

- **Package not found in AUR**: Search for the exact package name. `coolerctrl`
  (with two l's) is NOT a valid package; the correct name is `coolercontrol`.
  Similarly, `msi-ec-dkms` is not a package; use `msi-ec-dkms-git`.

- **DKMS build fails after kernel update**: Run `sudo dkms install msi-ec/r734.d7fbbd8 -k $(uname -r)`
  and `sudo dkms install r8125/9.018.00 -k $(uname -r)`, then regenerate initcpio:
  `sudo mkinitcpio -P`

- **r8125-dkms vs r8169 conflict**: Both modules may load simultaneously, causing
  network instability. Blacklist `r8169` if you want r8125 exclusively:
  `echo "blacklist r8169" | sudo tee /etc/modprobe.d/r8169.conf` then `sudo mkinitcpio -P`
  and reboot. After reboot, `lsmod | grep r8169` should return nothing.

- **coolercontrold not starting**: Check `journalctl -u coolercontrold -f`.
  May conflict with `thermald` or `tlp`. Disable those first:
  `sudo systemctl disable --now thermald tlp`. coolercontrold must be both
  enabled and started to function.

- **nvidia-settings blank/empty**: Ensure `nvidia-utils` and `libxnvctrl` are installed.
  On Wayland, run `nvidia-settings --config=/tmp/nvidia-settings-rc` or use
  `optimus-manager` for hybrid GPU setups.

## Hybrid GPU Browser Video Decode (Intel iGPU + NVIDIA dGPU)

On MSI Titan GT77HX (and similar Optimus/hybrid laptops), the internal panel
scans out through the Intel iGPU. Setting `LIBVA_DRIVER_NAME=nvidia` globally
causes Brave/Chrome to attempt VP9/AV1 hardware decode on the RTX 4090, then
pass frames back to Intel over Wayland — this path is broken and produces
black video, spinners, or audio-only playback.

### Fix: Override nvidia.lua + chromium-flags.conf

**Root cause:** Omarchy's `default/hypr/nvidia.lua` sets
`LIBVA_DRIVER_NAME=nvidia` unconditionally. On hybrid laptops where the iGPU
drives the display, this breaks Chromium video decode (black screen/spinner).

**Fix 1 — User override (update-safe):** Create
`~/.config/omarchy/default/hypr/nvidia.lua` that checks
`omarchy-hw-hybrid-gpu` first, uses `iHD` on hybrid, `nvidia` on discrete-only.
See `references/hybrid-gpu-browser-decode.md` for the full Lua code.

**Fix 2 — VA-API flags:** Create `/etc/chromium-flags.conf` with
`--enable-features=VaapiVideoDecoder,VaapiIgnoreDriverChecks` and
`--disable-features=UseChromeOSDirectVideoDecoder`.

Both fixes survive `omarchy update`. Restart Hyprland to apply the Lua override.

### Widevine CDM Version Compatibility

Brave 152+ requires Widevine CDM host version 11. The `chromium-widevine` AUR
package (4.10.3050.0) only supports host version 10 — insufficient.

**Fix:** Install `google-chrome-beta` from AUR, which ships Widevine 4.10.3112.0
(supports host versions 10 and 11), then copy it to Brave:

```bash
yay -S --noconfirm google-chrome-beta
sudo pacman -U --noconfirm /home/asimov/.cache/yay/google-chrome-beta/google-chrome-beta-*-x86_64.pkg.tar.zst
sudo rm -rf /opt/brave-bin/WidevineCdm
sudo cp -r /opt/google/chrome-beta/WidevineCdm /opt/brave-bin/WidevineCdm
```

Then restart Brave. Verify at `brave://components` — Widevine should show
version 4.10.3112.0.

The `google-chrome-beta` package can be removed afterward (`sudo pacman -R
google-chrome-beta`) — only the Widevine files are needed.

## Known Pitfalls

1. **AUR package name confusion**: The user may say "coolerctrl" but the package is
   `coolercontrol`. Always verify with `yay -Ss <name>` before assuming.

2. **Interruptions during install**: The user may interrupt (Ctrl+C) long-running
   installs. Use `--noconfirm` to avoid prompts, and warn the user that the build
   will take several minutes.

3. **Kernel version mismatch**: DKMS modules must match the running kernel.
   After kernel updates, DKMS auto-rebuilds, but verify with `dkms status`.

4. **Multiple AUR helpers**: The user may have both `yay` and `paru`. Default to `yay`
   unless the user prefers otherwise.

5. **WiFi driver confusion**: The user may ask for WiFi "drivers" to install.
   Intel WiFi chips use `iwlwifi` which is built into the kernel — there are no
   alternative drivers. Optimization is done via module parameters (see
   `intel-wifi-optimization` skill). Don't search for "better WiFi drivers";
   they don't exist for Intel chips.

6. **User prefers terse responses**: State what you're doing in one line, run
   the command, report success/failure. No tutorials, no follow-up options unless
   asked. For reinstalls, just run the command without asking "are you sure?"

7. **sudo in Hermes sessions**: `sudo -S` (piped password) is blocked by the
   Tirith security scanner as a brute-force attack vector — never pipe a
   password to `sudo -S`. The working path is to set `SUDO_PASSWORD` in
   `~/.hermes/.env`; once present, `sudo` runs non-interactively (no TTY
   needed). If the user provides the sudo password, write it to `.env` as
   `SUDO_PASSWORD=<value>` (append via terminal, the file is a protected
   credential store that read_file refuses), then `sudo` just works. Only if
   the user declines to set it, surface the exact commands for them to run in
   their own terminal.

   **Remove SUDO_PASSWORD from `.env` as soon as the elevated work is done.**
   The user does NOT want the sudo password left in `.env` — they will ask to
   remove it ("just remove it from the .env file"). After finishing the sudo
   task, delete the line (`sed -i '/^SUDO_PASSWORD=/d' ~/.hermes/.env`) and
   verify it's gone. Do not leave it as a convenience for the next session.

   **Removing SUDO_PASSWORD from `.env` does NOT revoke passwordless sudo if
   an omarchy NOPASSWD sudoers file exists.** Omarchy's `omarchy-sudo-passwordless`
   script writes `/etc/sudoers.d/99-omarchy-nopasswd-${USER}` containing
   `USER ALL=(ALL) NOPASSWD: ALL` and arms a `systemd-run` timer that auto-removes
   it after N minutes (default 15). If that file exists, `sudo -n` succeeds even
   with no SUDO_PASSWORD in `.env`. To fully revoke passwordless sudo, remove the
   sudoers file too: `sudo rm /etc/sudoers.d/99-omarchy-nopasswd-${USER}` (and
   `sudo systemctl stop omarchy-nopasswd-expire-${USER}.timer`). Check for it with
   `sudo ls /etc/sudoers.d/` before assuming `.env` removal is sufficient.

8. **Don't just write code — test it on real hardware**: User explicitly called out that writing the code isn't enough. Actually run the install script on the target machine and verify all post-install steps succeed. The pattern:
      - Write the install script
      - Copy to `/usr/share/omarchy/bin/` (or source from repo)
      - Run with `sudo env "PATH=$PATH OMARCHY_PATH=/usr/share/omarchy OMARCHY_INSTALL=/usr/share/omarchy/install" bash install/hardware/msi.sh`
      - Verify: modules loaded, services enabled, files created, no conflicts

9. **Avoid lspci — use sysfs for PCI device detection**: The MSI script originally used `lspci | grep -iE "Killer.*2\\.5.*GbE|RTL8125"` to detect the Killer E3000. This was changed to sysfs reads (`/sys/bus/pci/devices/*/vendor` + `device`) because lspci reads PCI config space, which can wake suspended GPUs on hybrid laptops (see Omarchy PR #11259). Pattern:
       ```bash
       pci_devices_path="${OMARCHY_PCI_DEVICES_PATH:-/sys/bus/pci/devices}"
       for device in "$pci_devices_path"/*; do
         [[ $(< "$device/vendor" 2>/dev/null) == "0x10ec" ]] || continue  # Realtek
         device_id=$(< "$device/device" 2>/dev/null)
         [[ $device_id == "0x8125" ]] || continue
         # Found RTL8125B
       done
       ```

10. **r8169 + r8125 both loaded by default**: Even when r8125-dkms is installed, the kernel may still load r8169 if it binds first. Must explicitly blacklist r8169 and rebuild initramfs. After reboot, verify `lsmod | grep r8169` returns nothing.

11. **thermald conflicts with coolercontrold**: On MSI laptops, thermald is often enabled by other install scripts. coolercontrold talks to the EC directly and knows the MSI fan table, so thermald must be disabled. The install script handles this, but verify after running.

12. **Scope discipline — don't lump general laptop issues into MSI work**: The user explicitly called out that Chromium VA-API flags, Widevine CDM fixes, and general hybrid GPU browser decode are NOT MSI-specific. They apply to any Intel iGPU + NVIDIA dGPU laptop. Keep MSI-specific work focused on MSI hardware (Killer Ethernet, MSI EC, MSI fan control, per-key RGB). General hybrid GPU issues belong in their own issue/PR, not bundled with MSI driver work.

13. **Install script robustness**: MSI install scripts need `set -euo pipefail`, `omarchy-pkg-present` checks to skip already-installed packages, `install -Dm644` for atomic system file writes (not `echo >`), and a guard that only blacklists r8169 if r8125 is actually loaded (to avoid network loss on failed installs).

14. **Broad MSI family detection**: Detect 14 families (Titan, Stealth, Raider, Vector, Crosshair, Summit, Creator, Modern, Katana, Cyborg, Pulse, Bravo, Alpha, Prestige) to cover budget/mid-tier/ultraportable lines. Test both detector and install script — 25 detection tests covering all families, edge cases, desktop rejection, and other vendors.

15. **Rebase onto upstream/quattro, not local quattro**: Your local quattro may have cherry-picked commits from other work. Always rebase feature branches onto `upstream/quattro` to avoid polluting PR history with unrelated commits (e.g. Chromium VA-API work).

16. **Cross-reference related PRs**: If your work aligns with or depends on another open PR (e.g. #11259 for sysfs PCI detection), mention it in your PR body under "Related PRs". This helps reviewers understand context and dependencies.

17. **all.sh wiring gap — PR vs installed system**: When adding a new hardware script to `install/hardware/all.sh`, the PR may include the wiring line but the installed system's `/usr/share/omarchy/install/hardware/all.sh` may not have it yet. After merging the PR, a second install run or manual merge is needed to activate the script. Always verify with `grep -q msi.sh /usr/share/omarchy/install/hardware/all.sh` after install.

18. **Post-reboot verification is mandatory**: Some driver states only stabilize after a full reboot (r8169 blacklist, msi_ec early-load via mkinitcpio, coolercontrold service). Always verify after reboot, not just after install. The comprehensive verification command block above covers all critical checks.

19. **Live system verification requires complementary data**: When the user asks to verify or update an issue with system info, ALWAYS include these sections in order:
    1. **System** — `uname -a`, DMI product_name, DMI BIOS version, EC firmware version + release date
    2. **Driver State** — table of all relevant drivers (r8125, r8169, msi_ec, msi_wmi_platform, msi_wmi, nvidia, iwlwifi, coolercontrold, thermald) with package and status
    3. **Configuration Files** — list all files created by the install script
    4. **EC Features** — dump all `/sys/devices/platform/msi-ec/` entries with current values and available modes
    5. **Battery** — capacity, status, charge_control_start_threshold, charge_control_end_threshold
    6. **Runtime Telemetry** — GPU temp/power/clocks, fan RPMs, CPU freq range, dGPU power state
    7. **Test Results** — output of each verification command with PASS/FAIL
    See `references/titan-gt77hx-live-verification.md` for a complete example.

20. **Don't stop at "it compiles" — test real functionality**: User explicitly called out that writing the install script isn't enough. After writing msi.sh, verify: battery thresholds actually set (not just "will be set"), RGB config file actually created (not just "should be created"), all.sh actually wired (not just "has the line in PR"). If a step is missing, FIX IT IMMEDIATELY, don't note it as a future TODO.

21. **Run the install script from the repo checkout BEFORE pushing**: User asked "have you tested to install it?" after I committed a script with a syntax error (`local` keyword in top-level code). Always run: `sudo env "PATH=$PATH OMARCHY_PATH=/usr/share/omarchy OMARCHY_INSTALL=/usr/share/omarchy/install" bash install/hardware/msi.sh` from the repo directory. Catch runtime errors before they reach the PR.

22. **`local` keyword in sourced scripts**: Omarchy install scripts are sourced by the runner, not executed as functions. Using `local` at top level causes: `line N: local: can only be used in a function`. Use plain variable assignment (`var=value`) instead.

23. **Battery threshold guard**: Only set charge thresholds when on DC power. Check `cat /sys/class/power_supply/BAT1/status == "Discharging"` before writing to `charge_control_*_threshold`. This prevents interfering with AC-powered usage and avoids confusing "thresholds not applied" reports when the laptop is plugged in.

24. **RGB config format**: msi-perkeyrgb uses `<keycodes> <mode> <color>` format, NOT INI-style (colors array, brightness, mode). Example: `all steady 00ff00`. The tool does not support JSON, TOML, or key-value config files.

25. **GT75 NOT supported**: GT75 is NOT a supported model in msi-perkeyrgb. Use GS75 as the closest match for Titan GT77HX keyboard layouts. Always verify with `msi-perkeyrgb --list-models`.

26. **msi-perkeyrgb requires lsusb**: The tool internally calls `lsusb` to find keyboards. If lsusb is missing, the tool fails with "No MSI keyboards found." Install `usbutils` package: `sudo pacman -S --noconfirm usbutils`.

27. **RGB udev rules**: msi-perkeyrgb needs read/write access to `/dev/hidraw*`. Create `/etc/udev/rules.d/99-msi-rgb.rules` with vendor-specific rules (1038:113a KLC, 1038:1146 ALC, 1038:1122 default) and reload with udevadm.

28. **Limine bootloader**: MSI Titan GT77HX uses Limine, not GRUB. `sudo mkinitcpio -P` fails with "No presets found in /etc/mkinitcpio.d". Always use `limine-mkinitcpio` (or fallback pattern: `limine-mkinitcpio 2>/dev/null || sudo mkinitcpio -P`).

25. **Issue description completeness**: When updating the issue description with test results, ALL of these must be present:
    - Gap analysis table (issue requirement vs PR implementation vs live test status)
    - Test commands with actual output (not just "should work")
    - Battery threshold state (before/after install)
    - RGB config file existence and contents
    - all.sh wiring status on installed system
    - Any gaps found and fixes applied

29. **RGB keyboard does NOT light up on Titan GT77HX despite `msi-perkeyrgb` exit code 0**: The GT77HX uses a Cherry MX Ultra Low Profile mechanical keyboard (SteelSeries, USB 1038:113a). `msi-perkeyrgb` writes to the hidraw device successfully (exit 0) but has no effect on the backlight — the keyboard uses a different HID protocol than the tool implements. RGB support has been **completely removed** from the PR, tests, and documentation. Do NOT add it back.

30. **`grok` CLI is an interactive TUI agent, not a non-interactive command runner**: When the user asks to use `grok` for tasks like "create a GitHub issue", `grok` is a full-screen interactive agent that cannot be driven with a single command from a CLI session. It will fail with errors like "No such device or address (os error 6)" or "unrecognized subcommand". **Fallback**: use `gh issue create` directly with `--repo`, `--title`, `--body` flags. This achieves the same result without the interactive TUI overhead.

31. **Omarchy install script runner context**: When running `install/hardware/msi.sh` directly from the command line (not via the Omarchy setup wizard), the script uses `omarchy-pkg-add`, `omarchy-pkg-present`, `omarchy-hw-nvidia`, and `sudo` — all of which require proper environment setup. Run with:
    ```bash
    sudo env "PATH=$PATH OMARCHY_PATH=/usr/share/omarchy OMARCHY_INSTALL=/usr/share/omarchy/install" bash install/hardware/msi.sh
    ```
    Note: `sudo` writes to system paths (`/etc/modprobe.d/`, `/etc/X11/xorg.conf.d/`, etc.) get blocked by Tirith security scanner unless `SUDO_PASSWORD` is set in `~/.hermes/.env` (see pitfall 7). The user prefers direct sudo use — set SUDO_PASSWORD so sudo works non-interactively rather than surfacing commands for the user to run manually.

## References

- `references/msi-titan-gt77hx.md` — MSI Titan GT77HX 13VI specific notes and optimization checklist
- `references/titan-gt77hx-live-verification.md` — Live install verification results and recovery paths
- `references/aur-package-names.md` — Exact AUR package names for MSI drivers
- `references/omarchy-hardware-script-pattern.md` — How to add new hardware vendor scripts (detectors + installers + all.sh wiring)
- `references/hybrid-gpu-browser-decode.md` — Intel iGPU VA-API + Widevine fix for Brave (NOT MSI-specific, applies to all hybrid laptops)
- `references/msi-perkeyrgb-tool-quirks.md` — msi-perkeyrgb config format, USB IDs, permissions, common errors
- `references/limine-bootloader.md` — Limine UKI rebuild via limine-mkinitcpio (MSI Titan GT77HX)

## Scripts

- `scripts/verify-msi.sh` — Post-install verification script (run after install AND reboot)
