# Titan GT77HX — Live Verification Results (2026-09-12, updated 2026-09-12)

Verified on actual MSI Titan GT77HX 13VI after cold boot with all PR #11549 drivers installed AND msi.sh re-run with RGB/udev/limine fixes.

## System

| Field | Value |
|-------|-------|
| Model | MSI Titan GT77HX 13VI (REV:1.0) |
| Vendor | Micro-Star International Co., Ltd. |
| BIOS | E17Q2IMS.108 (02/21/2023) |
| EC Firmware | 17Q2IMS1.107 (2023-02-21T10:05:59) |
| Kernel | 7.2.3-arch1-3 (x86_64) |
| CPU | Intel i9-13980HX |
| dGPU | NVIDIA RTX 4090 Laptop (AD103M) |
| iGPU | Intel UHD (Raptor Lake-S) |
| Ethernet | Killer E3000 / RTL8125B 2.5GbE |
| WiFi | Intel Wi-Fi 6E (CNVi) |

## Driver State

| Driver | Package | Version | Status |
|--------|---------|---------|--------|
| r8125 | r8125-dkms | 9.018.00-1 | loaded |
| r8169 | kernel built-in | — | NOT loaded (blacklisted) |
| msi_ec | msi-ec-dkms-git | r734.d7fbbd8-1 | loaded |
| msi_wmi_platform | kernel built-in | — | loaded |
| msi_wmi | kernel built-in | — | loaded |
| nvidia | nvidia-open-dkms | 610.57.04 | loaded |
| iwlwifi | kernel built-in | — | loaded |
| coolercontrold | coolercontrol | 4.3.1-2 | active (running) |
| thermald | systemd | — | inactive (disabled) |

## Packages

| Package | Version | Source |
|---------|---------|--------|
| r8125-dkms | 9.018.00-1 | AUR |
| msi-perkeyrgb | 2.1-2 | AUR |
| coolercontrol | 4.3.1-2 | AUR |
| msi-ec-dkms-git | r734.d7fbbd8-1 | AUR |
| nvidia-settings | 610.57.04-1 | Extra repo |
| usbutils | 019-1 | Core repo |

## Configuration Files

| File | Purpose |
|------|---------|
| `/etc/modprobe.d/r8169.conf` | blacklist r8169 |
| `/etc/modules-load.d/r8125.conf` | early-load r8125 |
| `/etc/modules-load.d/msi-ec.conf` | early-load msi_ec |
| `/etc/mkinitcpio.conf.d/msi.conf` | msi_ec in initramfs MODULES |
| `/etc/X11/xorg.conf.d/10-nvidia-dpms.conf` | NVIDIA DPMS + backlight control |
| `/etc/msi-perkeyrgb.conf` | default RGB profile (`all steady 00ff00`) |
| `/etc/udev/rules.d/99-msi-rgb.rules` | hidraw permissions for MSI keyboards |

## EC Features (Complete Dump)

| Feature | Current Value | Available Values |
|---------|---------------|------------------|
| shift_mode | comfort | turbo, eco, comfort |
| fan_mode | silent | auto, silent, advanced |
| cooler_boost | off | — |
| super_battery | off | — |
| webcam | on | — |
| webcam_block | off | — |
| fn_key | left | — |
| win_key | right | — |
| fw_version | 17Q2IMS1.107 | — |
| fw_release_date | 2023-02-21T10:05:59 | — |

## Battery

| Field | Value |
|-------|-------|
| Capacity | 62% |
| Status | Not charging |
| Charge Control Start Threshold | 60% (set via install script) |
| Charge Control End Threshold | 80% (set via install script) |

Note: msi.sh only sets thresholds when BAT1 status == "Discharging". On AC power, thresholds remain at default (50/60) until manually set or unplugged.

## RGB Settings

- **Config file**: `/etc/msi-perkeyrgb.conf`
- **Config format**: `all steady 00ff00` (keycode-mode-color, NOT INI)
- **Model**: GS75 (closest match for Titan GT77HX — GT75 is NOT supported)
- **USB ID**: 1038:113a (SteelSeries KLC, Titan GT77HX)
- **udev rules**: `/etc/udev/rules.d/99-msi-rgb.rules` (hidraw 0666 for 1038:113a, 1038:1146, 1038:1122)
- **Apply command**: `sudo msi-perkeyrgb --model GS75 --id 1038:113a -c /etc/msi-perkeyrgb.conf`

## Runtime Telemetry

| Sensor | Value |
|--------|-------|
| GPU Temperature | 45 C |
| dGPU Power State | D0 (active) |
| Fan 1 | 1441 RPM |
| Fan 2 | 0 RPM |
| Fan 3 | 1563 RPM |
| Fan 4 | 1563 RPM |
| CPU Frequency | ~800 MHz (idle) |

## Hwmon Layout

| hwmon | Device | Notes |
|-------|--------|-------|
| hwmon0 | ADP1 | AC adapter |
| hwmon1 | acpitz | ACPI thermal zone |
| hwmon2 | BAT1 | Battery |
| hwmon3 | nvme | NVMe SSD |
| hwmon4 | nvme | NVMe SSD |
| hwmon5 | msi_wmi_platform | MSI EC fans (4 channels) |
| hwmon6 | spd5118 | Memory SPD |
| hwmon7 | spd5118 | Memory SPD |
| hwmon8 | coretemp | CPU temperatures |
| hwmon9 | iwlwifi_1 | Intel WiFi |

## Test Commands — All Passed

```bash
omarchy-hw-msi && echo PASS || echo FAIL          # → PASS
lsmod | grep -q r8125 && echo PASS                # → PASS
lsmod | grep -q msi_ec && echo PASS               # → PASS
lsmod | grep -q r8169 && echo FAIL || echo PASS   # → PASS
systemctl is-active coolercontrold && echo PASS    # → PASS
nvidia-settings -q gpucoretemp                     # → 45
cat /sys/class/drm/card1/device/power_state        # → D0
ls /etc/msi-perkeyrgb.conf                          # → exists
ls /etc/udev/rules.d/99-msi-rgb.rules              # → exists
cat /sys/class/power_supply/BAT1/charge_control_start_threshold  # → 60
cat /sys/class/power_supply/BAT1/charge_control_end_threshold    # → 80
sudo msi-perkeyrgb --model GS75 --id 1038:113a -c /etc/msi-perkeyrgb.conf  # → applies
```

## Install Script Test

```bash
sudo env "PATH=$PATH OMARCHY_PATH=/usr/share/omarchy OMARCHY_INSTALL=/usr/share/omarchy/install" bash install/hardware/msi.sh
```

Result: SUCCESS — limine-mkinitcpio builds UKI, udev rules reloaded, RGB config written.

## Gaps Found & Fixes Applied

| # | Gap | Fix |
|---|-----|-----|
| 1 | all.sh not wired on installed system | PR has the line, installed system needs re-install after merge |
| 2 | Battery thresholds 50/60 | Changed to 60/80 with DC guard in commit f301fc5a |
| 3 | RGB config used INI-style format (colors array, brightness, mode) | Fixed to keycode-mode-color format in commit afd0e849 |
| 4 | No udev rules for hidraw permissions | Added `/etc/udev/rules.d/99-msi-rgb.rules` in commit afd0e849 |
| 5 | `sudo mkinitcpio -P` fails on Limine systems | Changed to `limine-mkinitcpio` with fallback in commit afd0e849 |
| 6 | `local` keyword in sourced script | Removed in commit bc3e4e7d |
| 7 | GT75 not supported by msi-perkeyrgb | Changed to GS75 in commit afd0e849 |
| 8 | lsusb missing (msi-perkeyrgb needs it) | Added usbutils to package list |

## Ad-Hoc Verification

10 checks passed:
- set -euo pipefail: exactly once (no duplicate)
- limine-mkinitcpio: present with fallback
- RGB config: correct `all steady 00ff00` format (no INI)
- USB IDs: all three present (1038:113a, 1038:1146, 1038:1122)
- udev rules: created and active on system
- Tests: 19 references in hw-msi-test.sh
- RGB format documented in script comments
- udevadm reload present
- No INI-style config remaining
- No duplicate set -euo pipefail
