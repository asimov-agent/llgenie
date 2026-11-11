---
name: displaylink-drivers
description: >-
  Install and configure DisplayLink docking station drivers on Arch Linux.
  Covers USB-C/USB-A docks that use DisplayLink chipsets (DL-6xxx, DL-5xxx,
  DL-41xx, DL-3xxx series). Triggers: DisplayLink, docking station, external
  monitors via USB, ICY BOX, Plugable, Dell D6000, HP USB-C Dock, USB graphics
  adapter, dual monitors, evdi kernel module.
---

# DisplayLink Docking Station Drivers

Install DisplayLink drivers for USB docking stations on Arch Linux.

## When to use

When the user connects a USB docking station (USB-C or USB-A) and external
monitors are not detected, or when asked to set up DisplayLink support.

Common devices: ICY BOX IB-DK2252AC, IB-DK2241AC, IB-DK2106-C, Dell D6000,
HP USB-C Dock G5, Plugable UD-6950, Wavlink docks, generic DisplayLink adapters.

## Identification

DisplayLink docks usually show up as USB devices with vendor ID `17e9`:

```
lsusb | grep 17e9
Bus 002 Device 005: ID 17e9:6006 DisplayLink
```

If you don't have `lsusb` (part of `usbutils`), install it first or check
`dmesg` for DisplayLink mentions after plugging in.

## Installation

Two packages are required from AUR:

| Package | Purpose |
|---------|---------|
| `evdi-dkms` | Kernel module for virtual display support |
| `displaylink` | Userspace driver and service |

### With AUR helper (yay/paru)

```bash
yay -S evdi-dkms displaylink
# or
paru -S evdi-dkms displaylink
```

### Manual AUR install

```bash
mkdir -p ~/repository/git && cd ~/repository/git
git clone https://aur.archlinux.org/evdi-dkms.git
cd evdi-dkms && makepkg -si
cd ~/repository/git
git clone https://aur.archlinux.org/displaylink.git
cd displaylink && makepkg -si
```

> **Note:** `displaylink` depends on `evdi-dkms`, so the AUR resolver will
> pull it in. Always install both to be explicit.

## Post-install

```bash
sudo systemctl enable --now displaylink.service
```

Verify:

```bash
systemctl status displaylink.service
```

Then plug in the dock (or replug). External displays should be detected
within a few seconds.

## Troubleshooting

- **"No screens found" / black screen**: Replug the dock, check `journalctl -u displaylink -f`
- **Build failures after kernel update**: `evdi-dkms` auto-rebuilds via DKMS on kernel updates. If stuck, `sudo dkms install evdi/1.15.0 -k $(uname -r)`
- **Wayland**: Works out of the box with `displaylink` 5.3+. No extra config needed.
- **Xorg**: Use `xrandr` to configure DisplayLink monitors alongside the `udl` driver
- **NVIDIA + DisplayLink (Optimus)**: Known tricky combo. See references/nvidia-optimus.md

## Pitfall: Reinstalls rebuild from source

When the user asks to "reinstall" or "force update" drivers, `yay -S`
without `--needed` will rebuild all packages from source (evdi, displaylink,
coolercontrold, msi-ec-dkms-git all compile). This takes 2-5 minutes.

For reinstalls, use `--needed` to skip already-installed packages:

```bash
yay -S --noconfirm --needed evdi-dkms displaylink nvidia-settings r8125-dkms msi-perkeyrgb coolercontrol msi-ec-dkms-git
```

If the user explicitly wants a force reinstall (same versions), just run
it — but warn them it'll take a few minutes. Don't ask "are you sure?".

## Pitfall: Long installs get interrupted

DisplayLink and MSI driver installs take 2-5 minutes of compilation
(evdi, coolercontrold, msi-ec-dkms-git all build from source).

- Use `--noconfirm` to avoid interactive prompts that stall the build.
- If the user interrupts (Ctrl+C / exit code 130), the packages may be
  partially built. Re-run with `--needed` to skip already-installed ones:
  `yay -S --noconfirm --needed <packages>`
- Don't over-explain or narrate. Give the command, run it, report the
  result. The user wants terse, direct output — not a tutorial.

## Pitfall: User prefers terse responses

This user explicitly prefers minimal explanation. When installing drivers:

- State what you're doing in one line
- Run the command
- Report success/failure
- Don't explain what the drivers do unless asked
- Don't offer follow-up options unless asked
- For reinstalls, just run the command without asking "are you sure?"
- If a package is already installed, skip it silently or note it in one word
