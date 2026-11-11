# AUR Package Names for MSI Laptop Drivers

## Correct Package Names

| What you want | Correct AUR package | Common mistake |
|---------------|---------------------|----------------|
| Fan/thermal GUI | `coolercontrol` | `coolerctrl` (wrong) |
| Fan/thermal daemon | `coolercontrold` | `coolerctrl` (wrong) |
| EC driver | `msi-ec-dkms-git` | `msi-ec-dkms` (wrong) |
| RGB keyboard | `msi-perkeyrgb` | `msi-rgb` (wrong) |
| 2.5GbE driver | `r8125-dkms` | `r8125` (wrong) |

## Searching AUR

Always verify package names before installing:

```bash
yay -Ss coolercontrol    # Find exact package name
yay -Ss msi-ec           # Find EC driver variants
yay -Ss r8125            # Find networking driver variants
```

## Installation Command

```bash
yay -S --noconfirm r8125-dkms msi-perkeyrgb coolercontrol msi-ec-dkms-git
```

> **Note:** `coolercontrol` depends on `coolercontrold`, so installing
> `coolercontrol` alone will pull in the daemon automatically.
