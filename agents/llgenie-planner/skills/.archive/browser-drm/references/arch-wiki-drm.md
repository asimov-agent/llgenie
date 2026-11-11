# Arch Linux DRM Playback Notes

## Overview

Arch Linux repositories cannot ship Widevine CDM due to licensing restrictions (Google's proprietary binary). Users must obtain it through AUR or manual install.

## AUR Packages

- `chromium-widevine` — the canonical Widevine CDM package for Arch. Works with Brave, Chromium, Chrome, and other Chromium-based browsers.
- Maintained by: Arch Linux community

## How Widevine Works in Chromium Browsers

Chromium browsers look for Widevine in:
1. Browser installation directory (e.g., `/opt/brave.com/brave/WidevineCdm`)
2. System library paths (e.g., `/usr/lib/chromium/WidevineCdm`)
3. User data directory (`~/.config/BraveSoftware/Brave-Browser/WidevineCdm`)

The component updater in Chromium checks for updates to Widevine via the component updater service (`brave://components`).

## Architecture Paths

- x86_64: `_platform_specific/linux_x64/libwidevinecdm.so`
- ARM64: `_platform_specific/linux_arm64/libwidevinecdm.so`

## Widevine Security Levels

- **L1 (Hardware-backed)**: Requires TPM + secure media pipeline. Enables HD/4K on Netflix.
- **L3 (Software-only)**: Works without special hardware. May limit Netflix to SD/720p.

Most Arch setups run L3 unless configured otherwise with compatible hardware.

## Troubleshooting

### Widevine not showing in brave://components
- Ensure `chromium-widevine` is installed
- Restart browser completely
- Check `brave://version` for profile path and confirm Widevine path exists

### Netflix gives error M7111-1331
- Usually means Widevine L3 only or missing Widevine
- Install `chromium-widevine` and restart

### After browser update Widevine disappears
- Re-run: `yay -S chromium-widevine` (reinstalls after major Brave updates)
- Check `brave://components` for "Check for update"

## Sources

- https://wiki.archlinux.org/title/Chromium#Widevine_Content_Decryption_Module
- https://support.brave.app/hc/en-us/articles/360023851591
