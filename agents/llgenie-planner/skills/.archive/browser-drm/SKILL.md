---
name: browser-drm
description: "Install and configure Widevine CDM for DRM-protected browser content (Netflix, HBO, Spotify, YouTube) on Arch Linux. Covers Brave, Chromium, Chrome, and other Chromium-based browsers. Triggers: Widevine, DRM, protected content, Netflix, HBO, Spotify, browser media playback, libwidevinecdm, brave widevine, chromium widevine."
tags: [widevine, drm, brave, chromium, arch, netflix, hbo, spotify, browser]
---

# Browser DRM (Widevine CDM) on Arch Linux

Install and configure Google's Widevine Content Decryption Module (CDM) for DRM-protected media playback in Chromium-based browsers on Arch Linux.

## When to Use

- User reports videos won't play in Brave/Chromium/Chrome (Netflix, HBO, Spotify, YouTube Premium, etc.)
- User asks about Widevine, DRM, or protected content
- Browser shows "Widevine not installed" or similar DRM errors
- Setting up a fresh Arch install and need media playback working

## Supported Browsers

- Brave (`brave-bin` from AUR)
- Chromium (`chromium` from repos)
- Google Chrome (`google-chrome` from AUR)
- Other Chromium-based browsers (Edge, Opera, Vivaldi)

## Quick Fix: Enable in Settings First

Before installing anything, check if Widevine is already bundled but disabled:

1. Open browser and navigate to:
   - Brave: `brave://settings/content/protectedContent`
   - Chromium: `chromium://settings/content/protectedContent`

2. Toggle ON:
   - "Allow sites to play protected content"
   - "Allow sites to play protected content identifiers"

3. Check component status:
   - Brave: `brave://components` → look for "Widevine Content Decryption Module" → click "Check for update"
   - Chromium: `chromium://components`

4. Restart browser.

## Manual Installation (when bundled Widevine is missing)

### Method 1: chromium-widevine-helper (recommended — most maintainable)

The `chromium-widevine-helper` AUR package provides a native messaging host + browser extension that downloads, installs, and enables Widevine CDM automatically.

```bash
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

### Method 2: Manual symlink from existing install

If you have Widevine from another source (e.g., Chrome install):

```bash
# Find existing Widevine
find / -name "libwidevinecdm.so" 2>/dev/null

# For Brave
sudo mkdir -p /opt/brave.com/brave
sudo ln -s /path/to/WidevineCdm /opt/brave.com/brave/WidevineCdm

# For Chromium
sudo mkdir -p /usr/lib/chromium
sudo ln -s /path/to/WidevineCdm /usr/lib/chromium/WidevineCdm
```

### Method 3: User-level install (no sudo)

```bash
# Create Widevine directory in user data
mkdir -p ~/.config/BraveSoftware/Brave-Browser/WidevineCdm

# Create path manifest
echo '{"Path":"/path/to/your/WidevineCdm"}' > ~/.config/BraveSoftware/Brave-Browser/WidevineCdm/latest-component-updated-widevine-cdm
```

## Verification

1. Restart browser
2. Navigate to `brave://components` (or equivalent)
3. Confirm "Widevine Content Decryption Module" shows version number
4. Test at: https://bitmovin.com/demos/drm or https://www.netflix.com

## Pitfalls

- **Architecture mismatch**: Ensure you download the correct architecture (x86_64 for most, aarch64 for ARM). Brave on Arch x86_64 uses `linux_x64`.
- **Brave updates**: Brave-bin sometimes removes Widevine after major updates. Re-check `brave://components` after browser updates.
- **Flatpak/snap**: Flatpak and Snap browsers bundle their own Widevine. Do not attempt manual symlinks for sandboxed browsers.
- **Widevine L3 vs L1**: Some services (Netflix 4K, etc.) require L1 (hardware-backed) Widevine. L3 (software) works for most streaming but may limit quality.

## See Also

- `references/arch-wiki-drm.md` — Arch Wiki notes on DRM playback
- `references/chromium-widevine-helper.md` — Full reference for the helper package (commands, browsers, file locations)
- `widevine-drm-arch` skill — Companion skill with detailed Widevine installation steps
