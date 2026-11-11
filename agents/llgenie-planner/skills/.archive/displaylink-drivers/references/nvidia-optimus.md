# NVIDIA Optimus + DisplayLink Troubleshooting

## Problem

DisplayLink external monitors don't work (or Xorg fails to start) on laptops with NVIDIA dGPU + Intel iGPU (Optimus/hybrid graphics).

## Diagnosis

Check your GPU setup:
```bash
lspci | grep -E "VGA|3D"
```

Two entries means Optimus. Verify which GPU is rendering:
```bash
glxinfo | grep "OpenGL renderer"
# or
nvidia-smi
```

## Solutions

### Xorg - Force NVIDIA to be the primary GPU

Create `/etc/X11/xorg.conf.d/10-optimus.conf`:

```
Section "Device"
    Identifier "nvidia"
    Driver "nvidia"
    BusID "PCI:1:0:0"   # adjust based on lspci output
    Option "AllowExternalGpus" "true"
EndSection
```

Then add to `/etc/modprobe.d/nvidia.conf`:
```
options nvidia-drm modeset=1
```

Rebuild initcpio and reboot:
```bash
sudo mkinitcpio -P
```

### Wayland (Hyprland/Sway)

DisplayLink works with Wayland out of the box if you're using:
- `nvidia-drm.modeset=1` kernel param or
- `nvidia_drm.modeset=1` in `/etc/modprobe.d/`

Set `WLR_DRM_NO_ATOMIC=1` if you get flickering.

### PRIME Render Offload

If DisplayLink renders on Intel but you want NVIDIA to handle 3D:
```bash
prime-run glxgears
```

But DisplayLink Manager itself runs on the Intel GPU by design.

## Known Issues

- DisplayLink + NVIDIA proprietary: external monitors may flicker or show tearing
- DisplayLink + nouveau: not recommended, poor performance
- Hot-plugging DisplayLink with NVIDIA: sometimes requires service restart:
  ```bash
  sudo systemctl restart displaylink
  ```

## Debug Logs

```bash
journalctl -u displaylink -b --no-pager | tail -100
cat /var/log/displaylink/manager.log  # if exists
```

## Workaround

If nothing works, try the `displaylink-sleep.sh` script from the AUR package:
```bash
/usr/lib/displaylink/displaylink-sleep.sh suspend
/usr/lib/displaylink/displaylink-sleep.sh resume
```

This resets the dock on sleep/wake transitions.
