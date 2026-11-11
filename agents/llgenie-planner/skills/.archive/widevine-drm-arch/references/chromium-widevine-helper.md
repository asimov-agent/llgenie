# chromium-widevine-helper Reference

AUR package that provides a native messaging host + browser extension for installing Google's Widevine CDM into Chromium-based browser profiles on Linux.

## What It Does

- Downloads the official Google Widevine component
- Installs it into the active browser profile's `WidevineCdm` directory
- Provides a browser extension that detects when Widevine is missing and offers to install it

## Installation

```bash
yay -S chromium-widevine chromium-widevine-helper
```

If yay fails at sudo stage (non-interactive shell), install manually:
```bash
sudo pacman -U /home/asimov/.cache/yay/chromium-widevine/chromium-widevine-*.pkg.tar.zst
sudo pacman -U /home/asimov/.cache/yay/chromium-widevine-helper/chromium-widevine-helper-*.pkg.tar.zst
```

## Commands

```bash
# Register native messaging host for a browser
chromium-widevine --install-native-hosts brave
chromium-widevine --install-native-hosts chromium
chromium-widevine --install-native-hosts chrome
chromium-widevine --install-native-hosts edge
chromium-widevine --install-native-hosts vivaldi
chromium-widevine --install-native-hosts opera
chromium-widevine --install-native-hosts thorium
chromium-widevine --install-native-hosts iridium
chromium-widevine --install-native-hosts ungoogled-chromium

# Enable Widevine
chromium-widevine --enable

# Check status
chromium-widevine --status

# Disable Widevine
chromium-widevine --disable

# Force update check
chromium-widevine --update

# Restart browser
chromium-widevine --restart
```

## Supported Browsers

- Brave, Chromium, Chrome, Edge, Vivaldi, Opera, Helium, Thorium, Iridium, ungoogled-chromium
- NOT Firefox-family browsers (Mullvad, Zen) — they require separate Firefox-compatible extension

## File Locations

- Native helper: `/usr/libexec/chromium-widevine/chromium-widevine`
- User binary: `/usr/bin/chromium-widevine`
- Extension: `/usr/share/chromium-widevine/extension`
- Native messaging hosts: `/etc/brave/native-messaging-hosts/org.chromium.widevine.json` (and similar for other browsers)
- Logs: `~/.config/BraveSoftware/Brave-Browser/WidevineCdm/chromium-widevine-native.log`

## Architecture Support

- x86_64 (most desktops/laptops)
- aarch64 / arm64 (Raspberry Pi, ARM laptops)

## Session Notes (2026-09-11)

- `brave-bin` 1.94.121-1 on Arch did NOT have Widevine bundled
- `chromium-widevine` installs to `/usr/lib/chromium/WidevineCdm/`
- `chromium-widevine-helper` 1.0.9-1 provides the native messaging host
- After `chromium-widevine --enable`, browser must be fully restarted
- The extension may need reloading in `chrome://extensions` after browser updates
