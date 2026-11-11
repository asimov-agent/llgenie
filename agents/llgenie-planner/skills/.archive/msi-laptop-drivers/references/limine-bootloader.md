# Limine Bootloader — UKI Rebuild Pattern

MSI Titan GT77HX 13VI uses Limine (not GRUB). The `mkinitcpio -P` command alone
does NOT update Limine boot entries. Use `limine-mkinitcpio` instead.

## The Problem

```bash
sudo mkinitcpio -P
# → ERROR: No presets found in /etc/mkinitcpio.d
# → WARNING: This does not update Limine boot entries.
# → Use 'limine-mkinitcpio' or 'limine-update' instead.
```

## The Fix

Always use `limine-mkinitcpio` for Limine systems:

```bash
limine-mkinitcpio
# → Building UKI for linux (7.2.3-arch1-3)
# → Updated: /boot/limine.conf
```

## Fallback Pattern

For portable scripts that may run on either GRUB or Limine systems:

```bash
limine-mkinitcpio 2>/dev/null || sudo mkinitcpio -P
```

This tries Limine first, falls back to mkinitcpio if Limine is not installed.

## Available Limine Commands

| Command | Purpose |
|---------|---------|
| `limine-mkinitcpio` | Rebuild UKI from mkinitcpio |
| `limine-update` | Full Limine update (scan + rebuild) |
| `limine-install` | Install Limine bootloader |
| `limine-list` | List boot entries |
| `limine-scan` | Scan for OS installations |
| `limine-entry-tool` | Manage boot entries |
| `limine-snapper-sync` | Sync with snapper snapshots |

## When to Call

Call `limine-mkinitcpio` (or the fallback) after:
- Adding modules to `/etc/mkinitcpio.conf.d/` (e.g., msi_ec)
- Blacklisting kernel modules (e.g., r8169 via modprobe.d)
- Updating module parameters

The UKI is output to `/boot/EFI/Linux/omarchy_linux.efi` and Limine
is updated automatically.
