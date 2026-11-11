# MSI Titan GT77HX 13VI — Driver Notes

## Hardware Overview

| Component | Device | Driver |
|-----------|--------|--------|
| CPU | Intel i9-13980HX | `intel-ucode`, `intel-lpmd` |
| dGPU | NVIDIA RTX 4090 Laptop (AD103M) | `nvidia-open-dkms`, `nvidia-utils` |
| iGPU | Intel UHD (Raptor-Lake-S) | `intel-media-driver`, `vulkan-intel` |
| Ethernet | Killer E3000 (RTL8125B) | `r8125-dkms` (alt to `r8169`) |
| WiFi | Intel Wi-Fi 6E (CNVi) | `iwlwifi` (kernel built-in) |
| Thunderbolt | Maple Ridge 4C | `bolt` (kernel built-in) |
| NVMe | Samsung PM9A1 x2 | `nvme` (kernel built-in) |
| Card Reader | Realtek RTS5261 | `rtsx_pci` (kernel built-in) |
| Audio | Intel 700 Series HD Audio | `sof-firmware`, `pipewire` |
| RGB Keyboard | MSI per-key RGB (SteelSeries, USB 1038:113a) | `msi-perkeyrgb` (AUR) |
| EC | MSI Embedded Controller (fw 17Q2IMS.107) | `msi-ec-dkms-git` (AUR) |
| Fan Control | MSI Cooler Boost (4 fans) | `coolercontrol` (AUR) |

## Installed Driver Versions (as of 2026-09-11)

- nvidia-settings: 610.57.04-1
- r8125-dkms: 9.018.00-1
- msi-perkeyrgb: 2.1-2
- coolercontrol: 4.3.1-2
- coolercontrold: 4.3.1-2
- msi-ec-dkms-git: r734.d7fbbd8-1

## Notes

- The Killer E3000 works with the kernel's `r8169` driver, but `r8125-dkms` is
  recommended for better 2.5GbE stability.
- `msi-ec-dkms-git` provides access to fan modes, battery charge thresholds,
  and other EC features. It requires DKMS rebuild on kernel updates.
- `coolercontrol` provides a GUI for fan curves and thermal monitoring.
  It depends on `coolercontrold` (the daemon).
- `nvidia-settings` requires `libxnvctrl` (auto-installed as dependency).
- WiFi (Intel 700 Series CNVi) uses `iwlwifi` — no install needed. Optimize
  via module parameters (see `intel-wifi-optimization` skill).

## Fan Details

The GT77HX has 4 fan channels exposed via `msi_wmi_platform` hwmon:

| Fan | Location | Notes |
|-----|----------|-------|
| 1 | CPU | ~1500 RPM at idle |
| 2 | (unused/off) | Reads 0 RPM at idle |
| 3 | GPU | ~1140 RPM at idle |
| 4 | GPU | ~1140 RPM at idle |

Fan 2 reads 0 RPM at idle but reports correctly under load. All 4 are visible
in coolercontrold and controllable via fan curves.

## RGB Keyboard — Known NOT Functional on GT77HX

The GT77HX uses a **Cherry MX Ultra Low Profile mechanical keyboard** (SteelSeries, USB 1038:113a). `msi-perkeyrgb` writes to the hidraw device successfully (exit 0) but has no effect on the backlight — the keyboard uses a different HID protocol than the tool implements.

- **Manufacturer**: SteelSeries (not MSI direct)
- **USB ID**: `1038:113a` (KLC), `1038:1146` (ALC)
- **msi-perkeyrgb detection**: Does NOT auto-detect. Must specify `--id 1038:113a`
- **Config format** (keycode-mode-color, NOT INI):
  ```
  all steady 00ff00
  ```
- **Config path**: `/etc/msi-perkeyrgb.conf`
- **Status**: Package installed and config created, but RGB does not light up

**DO NOT claim RGB is working in PRs or issues for this model.**

## Battery Charge Thresholds

- Exposed via standard power_supply sysfs: `/sys/class/power_supply/BAT1/`
- Files: `charge_control_start_threshold`, `charge_control_end_threshold`
- Default MSI values: 50/60 (very conservative)
- Recommended: 60/80 for battery health on DC power
- Only set when `status == "Discharging"` to avoid interfering with AC usage

## Optimization Checklist (2026-09-12)

Run after installing drivers. Verified this order resolves all conflicts:

1. **Blacklist r8169** — both `r8125` and `r8169` loaded simultaneously causes
   instability. Blacklist required:
   ```
   echo "blacklist r8169" | sudo tee /etc/modprobe.d/r8169.conf
   sudo mkinitcpio -P && reboot
   ```

2. **Disable thermald + tlp** — both conflict with `coolercontrold`:
   ```
   sudo systemctl disable --now thermald tlp
   sudo systemctl enable --now coolercontrold
   ```

3. **Create NVIDIA xorg.conf.d** — missing DPMS + brightness control config:
   ```
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

4. **Verify EC features**:
   ```
   ls /sys/devices/platform/msi-ec/
   cat /sys/devices/platform/msi-ec/shift_mode     # comfort/silent/sport/turbo
   cat /sys/devices/platform/msi-ec/fan_mode        # silent/balanced/advanced
   cat /sys/devices/platform/msi-ec/cooler_boost    # on/off
   ```

5. **Verify NVIDIA power state**:
   ```
   cat /sys/class/drm/card*/device/power_state   # D0 = active
   ```

### Default EC State (as shipped)

- `shift_mode`: comfort
- `fan_mode`: silent
- `cooler_boost`: off

Users typically want `shift_mode=performance` (or `turbo`) and `fan_mode=balanced`
for sustained loads.
