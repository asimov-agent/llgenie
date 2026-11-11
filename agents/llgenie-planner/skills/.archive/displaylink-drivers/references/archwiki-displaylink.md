# ArchWiki DisplayLink (Condensed)

## Installation

Install `displaylink` from AUR. This pulls in `evdi-dkms` as a dependency.

```bash
yay -S displaylink
```

## Configuration

### Xorg

After installing, use `xrandr` to configure DisplayLink monitors:
```bash
xrandr --listproviders
```

DisplayLink appears as a provider. Outputs show as `DVI-1-0`, `DVI-1-1`, etc.

### Wayland

Works out of the box with displaylink >= 5.3. No configuration required.

## Troubleshooting

### Dock not detected

Check USB device:
```bash
lsusb | grep 17e9
```

### No screens

Check service status:
```bash
journalctl -u displaylink -f
```

### Module not loaded after kernel update

```bash
sudo dkms install evdi/1.15.0 -k $(uname -r)
```

### NVIDIA + DisplayLink (Optimus)

If using NVIDIA proprietary drivers with an Intel/NVIDIA hybrid setup:
- Add to `/etc/X11/xorg.conf.d/10-optimus.conf`:
  ```
  Section "Device"
      Identifier "nvidia"
      Driver "nvidia"
      Option "AllowExternalGpus" "true"
  EndSection
  ```
- Restart displaylink service

### Firmware

Most DL-3xxx/DL-5xxx docks ship with firmware. Some older ones may need manual firmware files in `/lib/firmware/`.

## External Displays

DisplayLink supports up to 2 external displays per dock. Maximum resolution depends on chipset:
- DL-6950: 4K @ 60Hz
- DL-5500: 4K @ 30Hz
- DL-3500: 2560x1440 @ 60Hz
