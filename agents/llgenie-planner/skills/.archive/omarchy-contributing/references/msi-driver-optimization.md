# MSI Titan GT77HX — Driver Optimization Contribution

## Summary

Adding MSI laptop-specific hardware detection and driver installation to Omarchy's
hardware setup. Covered in issue #11532.

## Files Changed

| File | Purpose |
|------|---------|
| `bin/omarchy-hw-msi` | Detect MSI laptop vendor + product family |
| `install/hardware/msi.sh` | Install drivers and configure MSI hardware |
| `install/hardware/all.sh` | Wire MSI install into hardware setup flow |

## Detection Logic (`omarchy-hw-msi`)

Check `/sys/class/dmi/id/sys_vendor` for
`"Micro-Star International Co., Ltd."`, then filter by product family/name
containing: Titan, Stealth, Raider, Vector, Crosshair, Summit, Creator, Modern.

MSI desktop boards also report this vendor but don't match any of these
laptop family strings — they're correctly excluded.

## Driver Set

| Driver | AUR | Purpose |
|--------|-----|---------|
| r8125-dkms | Yes | Killer E3000 / RTL8125B 2.5GbE (alt to r8169) |
| msi-ec-dkms-git | Yes | EC access — fan modes, shift modes, battery thresholds |
| coolercontrol | Yes | Fan curves + GUI (requires coolercontrold daemon) |
| msi-perkeyrgb | Yes | Per-key RGB keyboard control |
| nvidia-settings | Official repos | GPU monitoring/tuning on dGPU models |

## Key Configuration Decisions

1. **Blacklist r8169** — Both `r8169` (kernel) and `r8125` load on Killer E3000.
   Blacklisting `r8169` ensures `r8125` binds exclusively for stable 2.5GbE.

2. **Disable thermald when coolercontrol is installed** — `thermald` uses
   generic Intel DPTF policies that don't know about MSI's EC fan table.
   `coolercontrold` talks to the EC directly and is the correct choice.

3. **Early KMS for msi-ec** — Add `msi_ec` to `mkinitcpio.conf.d/msi.conf`
   so the EC module loads before userspace needs it.

4. **NVIDIA X11 DPMS config** — Write `/etc/X11/xorg.conf.d/10-nvidia-dpms.conf`
   with `EnableBrightnessControl=1` so backlight and DPMS work via nvidia-settings.

## Install Flow (install/hardware/msi.sh) — Final Version

The final msi.sh (as merged in PR #11549) uses **sysfs instead of lspci** for
PCI device detection (per PR #11259) and guards the r8169 blacklist with
an `lsmod | grep r8125` check to avoid leaving the system with no network
driver.

```bash
if omarchy-hw-msi; then
  # Killer E-series Ethernet (RTL8125B) — blacklist r8169 for stability.
  # Use sysfs reads instead of lspci (see PR #11259) to avoid waking
  # suspended GPUs on hybrid laptops.
  pci_devices_path="${OMARCHY_PCI_DEVICES_PATH:-/sys/bus/pci/devices}"
  rtl8125b_found=false
  for device in "$pci_devices_path"/*; do
    [[ $(< "$device/vendor" 2>/dev/null) == "0x10ec" ]] || continue
    device_id=$(< "$device/device" 2>/dev/null)
    if [[ $device_id == "0x8125" ]]; then
      rtl8125b_found=true
      break
    fi
  done

  if $rtl8125b_found; then
    omarchy-pkg-add r8125-dkms
    # Blacklist r8169 so r8125 loads exclusively. Only do this if r8125
    # is actually loaded — otherwise we risk leaving the system with no
    # network driver until the next reboot.
    if lsmod | grep -q r8125; then
      # write /etc/modprobe.d/r8169.conf — "blacklist r8169"
      # write /etc/modules-load.d/r8125.conf — "r8125"
      limine-mkinitcpio 2>/dev/null || sudo mkinitcpio -P
    fi
  fi

  # msi-ec-dkms-git
  if ! lsmod | grep -q msi_ec; then
    omarchy-pkg-add msi-ec-dkms-git
  fi

  # Battery charge thresholds (only when on battery, not AC power)
  if [[ -f /sys/class/power_supply/BAT1/charge_control_start_threshold ]]; then
    current_status=$(cat /sys/class/power_supply/BAT1/status 2>/dev/null)
    if [[ $current_status == "Discharging" ]]; then
      echo 60 | sudo tee /sys/class/power_supply/BAT1/charge_control_start_threshold >/dev/null
      echo 80 | sudo tee /sys/class/power_supply/BAT1/charge_control_end_threshold >/dev/null
    fi
  fi

  # coolercontrol + disable thermald
  omarchy-pkg-add coolercontrol
  sudo systemctl disable --now thermald.service
  sudo systemctl enable --now coolercontrold.service

  # nvidia-settings + X11 DPMS config (dGPU only)
  if omarchy-hw-nvidia; then
    omarchy-pkg-add nvidia-settings
    # write /etc/X11/xorg.conf.d/10-nvidia-dpms.conf with EnableBrightnessControl=1
  fi

  # Early-load msi_ec module via mkinitcpio
  if lsmod | grep -q msi_ec; then
    # write /etc/mkinitcpio.conf.d/msi.conf — MODULES+=(msi_ec)
    limine-mkinitcpio 2>/dev/null || sudo mkinitcpio -P
  fi
fi
```

## Testing

Hardware detection commands like `omarchy-hw-msi` should support an env var
for test stubbing: `OMARCHY_DMI_ID_PATH` pointing to a directory with the
same layout as `/sys/class/dmi/id/` (sys_vendor, product_family, product_name).

Pattern (consistent with `OMARCHY_PCI_DEVICES_PATH` used by nvidia detectors):

```bash
test_detect() {
  OMARCHY_DMI_ID_PATH="$tmp_dir/dmi/id" "$ROOT/bin/omarchy-hw-msi"
}
```

## RGB Removed (Verified Not Working)

The Titan GT77HX 13VI uses a **Cherry MX Ultra Low Profile mechanical keyboard** (SteelSeries, USB 1038:113a). `msi-perkeyrgb` does not support this hardware — it exits cleanly (code 0) but lights do not change.

**After testing, RGB support was completely removed from the PR.** The final PR does NOT include:
- `msi-perkeyrgb` package install
- `/etc/msi-perkeyrgb.conf` config file
- `/etc/udev/rules.d/99-msi-rgb.rules` udev rules
- Any RGB-related tests

If a future contribution adds RGB back, it must clearly state which models actually work (e.g., GE63/GE73 with 1038:1122) and exclude Titan/GT77.
