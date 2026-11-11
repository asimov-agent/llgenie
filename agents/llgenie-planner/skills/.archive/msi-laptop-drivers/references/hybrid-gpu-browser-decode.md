# Hybrid GPU Browser Video Decode (Optimus / Intel iGPU + NVIDIA dGPU)

## Problem

On Optimus/hybrid laptops (Intel iGPU + NVIDIA dGPU), the internal panel
scans out through the Intel iGPU. When `LIBVA_DRIVER_NAME=nvidia` is set
globally (common in Omarchy/Arch NVIDIA setups), Brave/Chrome attempts
VP9/AV1 hardware decode on the dGPU, then passes frames back to Intel
over Wayland. This path is broken — produces black video, spinners, or
audio-only playback.

## Symptoms

- YouTube videos show black box with audio
- Spinner plays indefinitely
- `brave://gpu` shows hardware acceleration enabled but decode fails
- Software decode (accel off) works but uses CPU

## Fix 1: Override `nvidia.lua` (update-safe)

The root cause is Omarchy's `default/hypr/nvidia.lua` setting
`LIBVA_DRIVER_NAME=nvidia` unconditionally. The fix is a **user override**
that checks `omarchy-hw-hybrid-gpu` first and uses `iHD` (Intel) on hybrid
laptops, `nvidia` on discrete-only.

Create `~/.config/omarchy/default/hypr/nvidia.lua`:

```lua
local paths = require("default.hypr.paths")

local nvidia = paths.omarchy_path .. "/bin/omarchy-hw-nvidia"
local nvidia_gsp = paths.omarchy_path .. "/bin/omarchy-hw-nvidia-gsp"
local nvidia_without_gsp = paths.omarchy_path .. "/bin/omarchy-hw-nvidia-without-gsp"
local hybrid_gpu = paths.omarchy_path .. "/bin/omarchy-hw-hybrid-gpu"

if o.shell_succeeds(o.shell_quote(nvidia)) then
  if o.shell_succeeds(o.shell_quote(nvidia_gsp)) then
    hl.env("NVD_BACKEND", "direct")
    hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    if o.shell_succeeds(o.shell_quote(hybrid_gpu)) then
      hl.env("LIBVA_DRIVER_NAME", "iHD")
    else
      hl.env("LIBVA_DRIVER_NAME", "nvidia")
    end
  elseif o.shell_succeeds(o.shell_quote(nvidia_without_gsp)) then
    hl.env("NVD_BACKEND", "egl")
    hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    if o.shell_succeeds(o.shell_quote(hybrid_gpu)) then
      hl.env("LIBVA_DRIVER_NAME", "iHD")
    else
      hl.env("LIBVA_DRIVER_NAME", "nvidia")
    end
  end
end
```

This survives `omarchy update` because it lives in `~/.config/`, not
`/usr/share/omarchy/`. Restart Hyprland to apply.

## Fix 2: Enable VA-API in Chromium flags

Create `/etc/chromium-flags.conf` (system-wide, applies to all Chromium-based
browsers):

```
--ozone-platform=wayland
--ozone-platform-hint=wayland
--password-store=gnome-libsecret
--enable-features=TouchpadOverscrollHistoryNavigation
--enable-features=VaapiVideoDecoder,VaapiIgnoreDriverChecks
--disable-features=UseChromeOSDirectVideoDecoder
--load-extension=/usr/share/omarchy/default/chromium/extensions/copy-url,/usr/share/omarchy/default/chromium/extensions/yt-dlp,/usr/share/omarchy/default/chromium/extensions/whatsapp-slim
```

Routes browser video decode to iGPU's native VP9/AV1 engine. dGPU stays free
for GL rendering and CUDA.

## Fix 3: Widevine CDM Version Compatibility

Brave 152+ requires Widevine CDM host version 11. The `chromium-widevine`
AUR package (4.10.3050.0) only supports host version 10.

**Solution:** Get newer Widevine from `google-chrome-beta`:

```bash
yay -S --noconfirm google-chrome-beta
sudo pacman -U --noconfirm /home/asimov/.cache/yay/google-chrome-beta/google-chrome-beta-*-x86_64.pkg.tar.zst
sudo rm -rf /opt/brave-bin/WidevineCdm
sudo cp -r /opt/google/chrome-beta/WidevineCdm /opt/brave-bin/WidevineCdm
```

Then restart Brave. Verify at `brave://components` — Widevine 4.10.3112.0.

Can remove `google-chrome-beta` afterward: `sudo pacman -R google-chrome-beta`

## Verification

- `brave://gpu` → "Video Decode: Hardware accelerated" with VA-API
- `brave://components` → Widevine 4.10.3112.0
- YouTube plays correctly with hardware decode on iGPU

## References

- Brave Help Center: "How do I enable Widevine DRM on Linux?"
- Chromium VA-API documentation
