---
name: widevine-drm-arch
description: Install and configure Widevine CDM for DRM-protected video playback in Chromium-based browsers on Arch Linux
tags: [arch, browser, drm, widevine, video, brave, chromium]
---

# Widevine DRM on Arch Linux

## Trigger
User needs to play DRM-protected content (Netflix, HBO, Amazon Prime, Spotify, Disney+, etc.) in a Chromium-based browser on Arch Linux and gets playback errors or "missing plugin" messages.

## Problem
`brave-bin` and other Chromium-based browsers on Arch do NOT bundle Widevine CDM. The component is missing entirely, so DRM-protected video/audio refuses to play.

## Solution

### Preferred Method: chromium-widevine-helper (recommended)

The `chromium-widevine-helper` AUR package provides a native messaging host + browser extension that downloads, installs, and enables Widevine CDM automatically. More maintainable than manual symlinks.

```bash
# Install both packages
yay -S chromium-widevine chromium-widevine-helper
```

If `yay` fails at the sudo stage (password prompt in non-interactive shell), packages are already built. Install manually:
```bash
sudo pacman -U /home/asimov/.cache/yay/chromium-widevine/chromium-widevine-*.pkg.tar.zst
sudo pacman -U /home/asimov/.cache/yay/chromium-widevine-helper/chromium-widevine-helper-*.pkg.tar.zst
```

Register the native messaging host for your browser:
```bash
chromium-widevine --install-native-hosts brave
# Also works with: chromium, chrome, edge, vivaldi, opera, thorium, iridium, ungoogled-chromium
```

Enable Widevine:
```bash
chromium-widevine --enable
```

Check status:
```bash
chromium-widevine --status
```

### Fallback Method: Manual Symlink

If the helper package is not available or preferred:

1. Install Widevine CDM: `yay -S chromium-widevine`
2. Symlink into browser installation directory:
   ```bash
   # For Brave (/opt/brave-bin/)
   sudo ln -s /usr/lib/chromium/WidevineCdm /opt/brave-bin/WidevineCdm
   
   # For Chromium (/usr/lib/chromium/)
   sudo ln -s /usr/lib/chromium/WidevineCdm /usr/lib/chromium/WidevineCdm
   ```
3. Create path manifest in user data directory:
   ```bash
   mkdir -p ~/.config/BraveSoftware/Brave-Browser/WidevineCdm
   echo '{"Path":"/opt/brave-bin/WidevineCdm"}' > ~/.config/BraveSoftware/Brave-Browser/WidevineCdm/latest-component-updated-widevine-cdm
   ```

### Final Steps (both methods)
1. **Fully restart** the browser (close all windows — do not just restart the process)
2. Navigate to `brave://settings/content/protectedContent` (or `chromium://settings/content/protectedContent`)
3. Toggle ON both:
   - "Allow sites to play protected content"
   - "Allow sites to play protected content identifiers"
4. Navigate to `brave://components` and verify "Widevine Content Decryption Module" appears and is up to date

## Pitfalls
- `brave-bin` does NOT auto-install Widevine — manual setup is always required
- If `yay -S chromium-widevine` fails at the sudo stage, the package is already built at `/home/asimov/.cache/yay/chromium-widevine/`. Install it manually: `sudo pacman -U /home/asimov/.cache/yay/chromium-widevine/chromium-widevine-*.pkg.tar.zst`
- Symlink path must be named exactly `WidevineCdm` (case-sensitive) inside the browser's installation directory
- Browser must be fully restarted after symlinking — partial restarts may not pick up the component
- The `chromium-widevine-helper` extension may need to be reloaded in `chrome://extensions` after browser updates
- `chromium-widevine --enable` reports `needs_restart: true` — always restart the browser after enabling

## Verification
Visit a DRM-protected site (Netflix, HBO Max, etc.) and confirm playback starts. Alternatively, check `brave://components` for "Widevine Content Decryption Module" status.

## See Also

- `references/chromium-widevine-helper.md` — Full reference for the helper package (commands, browsers, file locations, session notes)
