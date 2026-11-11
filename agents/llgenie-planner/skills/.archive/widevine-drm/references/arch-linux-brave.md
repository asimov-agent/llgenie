# Widevine on Arch Linux + Brave — Session Transcript

## Problem
User wanted to play DRM content (YouTube, etc.) in Brave browser on Arch Linux. `brave-bin` was installed but Widevine CDM was missing.

## Initial Attempt (Failed)
1. Installed `chromium-widevine` AUR package (4.10.3050.0)
2. Symlinked `/usr/lib/chromium/WidevineCdm` to `/opt/brave-bin/WidevineCdm`
3. Created `latest-component-updated-widevine-cdm` registration file
4. Restarted Brave — **still didn't work**

## Second Attempt (Failed)
1. Installed `chromium-widevine-helper`
2. Ran `chromium-widevine --install-native-hosts brave`
3. Ran `chromium-widevine --enable` — reported "installed" and "enabled"
4. Restarted Brave — **still didn't work**

## Root Cause
Brave 152.1.94.121 requires Widevine CDM **host version 11**. The `chromium-widevine` package (4.10.3050.0) only supports host version 10. The manifest showed:
```json
"x-cdm-host-versions": "10"
```

## Working Solution
1. Installed `google-chrome-beta` (154.0.8037.0) which bundles Widevine 4.10.3112.0 with host versions "10,11"
2. Copied `/opt/google/chrome-beta/WidevineCdm` to `/opt/brave-bin/WidevineCdm`
3. Updated `latest-component-updated-widevine-cdm` registration file
4. Restarted Brave — **working**

## Key Insight
Always check `x-cdm-host-versions` in Widevine's `manifest.json`. For Brave 152+ and recent Chromium builds, it must include "11". The `chromium-widevine` AUR package is often outdated for newer browsers.

## Commands Used
```bash
# Check Widevine version compatibility
cat /opt/brave-bin/WidevineCdm/manifest.json | grep -E "version|host"

# Check if Widevine files exist
ls -la /opt/brave-bin/WidevineCdm/_platform_specific/linux_x64/

# Check Brave's Widevine registration
cat ~/.config/BraveSoftware/Brave-Browser/WidevineCdm/latest-component-updated-widevine-cdm

# Kill Brave completely
pkill -9 -f brave

# Verify Brave is dead
pgrep -f brave || echo "Brave killed"
```
