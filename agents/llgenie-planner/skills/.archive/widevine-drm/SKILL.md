---
name: widevine-drm
description: Install and troubleshoot Widevine CDM (DRM) for Chromium-based browsers on Arch Linux. Covers Brave, Chromium, Chrome, and other Chromium forks. Handles version compatibility issues between browser versions and Widevine CDM host/interface/module versions.
tags: [arch-linux, brave, chromium, widevine, drm, netflix, youtube, streaming]
---

# Widevine DRM on Arch Linux

Widevine is Google's Content Decryption Module (CDM) required for DRM-protected streaming (Netflix, HBO, Spotify, etc.). On Arch Linux, it is NOT bundled with `brave-bin` or `chromium` packages and must be installed separately.

## Trigger Conditions

- User reports DRM content won't play in Brave/Chromium/Chrome on Arch Linux
- `brave://components` shows Widevine missing or error
- Streaming sites show "plugin not supported" or similar errors
- User explicitly asks to install Widevine or fix DRM playback

## Key Version Compatibility Rule

**Brave 152+ and recent Chromium builds require Widevine CDM host version 11.**

The `chromium-widevine` AUR package (version 4.10.3050.0) only supports host version 10. This is the #1 cause of "still not working" after installation.

| Package | Widevine Version | Host Versions | Works with Brave 152+? |
|---------|-----------------|---------------|------------------------|
| `chromium-widevine` | 4.10.3050.0 | 10 | ❌ No |
| `google-chrome-beta` (bundled) | 4.10.3112.0 | 10, 11 | ✅ Yes |
| `google-chrome-stable` (bundled) | varies | 10, 11 | ✅ Yes |

## Installation Steps

### Method 1: Copy from google-chrome-beta (Recommended)

This is the most reliable method as of 2026:

```bash
# Install google-chrome-beta (ships newer Widevine)
yay -S google-chrome-beta
sudo pacman -U --noconfirm /home/asimov/.cache/yay/google-chrome-beta/google-chrome-beta-*-x86_64.pkg.tar.zst

# Copy Widevine to Brave's directory
sudo rm -rf /opt/brave-bin/WidevineCdm
sudo cp -r /opt/google/chrome-beta/WidevineCdm /opt/brave-bin/WidevineCdm

# Register the path with Brave
mkdir -p ~/.config/BraveSoftware/Brave-Browser/WidevineCdm
echo '{"Path":"/opt/brave-bin/WidevineCdm"}' > ~/.config/BraveSoftware/Brave-Browser/WidevineCdm/latest-component-updated-widevine-cdm

# Restart Brave
pkill -9 -f brave
```

### Method 2: chromium-widevine-helper (May not work for Brave 152+)

```bash
yay -S chromium-widevine chromium-widevine-helper
sudo pacman -U --noconfirm /home/asimov/.cache/yay/chromium-widevine/chromium-widevine-*-x86_64.pkg.tar.zst
sudo pacman -U --noconfirm /home/asimov/.cache/yay/chromium-widevine-helper/chromium-widevine-helper-*-any.pkg.tar.zst

# Register native messaging host for Brave
chromium-widevine --install-native-hosts brave

# Enable Widevine
chromium-widevine --enable
```

**Note:** This method often fails for Brave 152+ because the `chromium-widevine` package's CDM only supports host version 10. If `chromium-widevine --enable` says "installed" but DRM still doesn't work, use Method 1.

## Post-Installation Verification

1. Open Brave and go to `brave://components`
2. Find "Widevine Content Decryption Module" — should show version 4.10.3112.0 or newer
3. If it shows "Check for update", click it
4. Go to `brave://settings/content/protectedContent`
5. Toggle ON both:
   - "Allow sites to play protected content"
   - "Allow sites to play protected content identifiers"
6. Restart Brave
7. Test on a streaming site

## Pitfalls

1. **Symlinking vs copying:** Symlinking `/usr/lib/chromium/WidevineCdm` to `/opt/brave-bin/WidevineCdm` works, but copying is safer — some Chromium builds resolve symlinks differently for security reasons.

2. **Wrong Widevine version:** The `chromium-widevine` AUR package is outdated for newer Brave/Chromium. Always check `x-cdm-host-versions` in `manifest.json` — it must include "11" for Brave 152+.

3. **Missing latest-component-updated-widevine-cdm file:** Brave needs this JSON file in its User Data Directory to know where Widevine is installed. Without it, Brave won't load the CDM even if the files exist.

4. **Not restarting Brave:** Widevine is loaded at startup. You must fully kill and restart Brave after installation.

5. **Protected content toggles disabled:** Even with Widevine installed, Brave's `brave://settings/content/protectedContent` toggles must be enabled.

## Cleanup

If you installed `google-chrome-beta` just for its Widevine files, you can remove it after copying:

```bash
sudo pacman -R google-chrome-beta
```

The Widevine files in `/opt/brave-bin/WidevineCdm` are independent and will continue working.

## References

- [arch-linux-brave.md](references/arch-linux-brave.md) — Session-specific details and troubleshooting transcript
