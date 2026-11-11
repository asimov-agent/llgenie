# Mac Broadcom Wi-Fi Fix

Worked example: fixing Wi-Fi on older MacBooks with Broadcom chips.

## Problem

Older MacBooks (e.g., MacBook Air 5,2 2012) have Broadcom BCM43224 (14e4:4353)
Wi-Fi chips. Omarchy's `install/hardware/fix-bcm43xx.sh` didn't detect this chip,
so the proprietary `broadcom-wl-dkms` driver was never installed. The open-source
`brcmsmac` driver loads first, claims the device, and prevents `wl` from attaching.

## Solution

Add BCM43224 detection and blacklist conflicting open-source drivers:

```bash
if (echo "$pci_info" | grep -q "14e4:43a0" || echo "$pci_info" | grep -q "14e4:4331" || echo "$pci_info" | grep -q "14e4:4353"); then
  echo "BCM4360 / BCM4331 / BCM43224 detected"
  omarchy-pkg-add broadcom-wl-dkms linux-headers

  # Blacklist open-source drivers that conflict with wl
  mkdir -p /etc/modprobe.d
  cat > /etc/modprobe.d/broadcom-wl.conf <<'EOF'
# Blacklist open-source Broadcom drivers to prevent conflict with broadcom-wl-dkms (wl)
blacklist b43
blacklist brcmsmac
blacklist bcma
EOF
fi
```

## Verification

| Metric | Before (brcmsmac) | After (broadcom-wl-dkms) |
|--------|-------------------|--------------------------|
| Driver | brcmsmac (open-source) | wl (proprietary) |
| Link speed | 144.4 Mbps | 1170 Mbit/s |
| Signal | -41 dBm | 100% |

## Related Issues

- **#7593** — broadcom-wl hard-freezes BCM4331 (different chip, different fix needed)
- **#9386** — Kernel 7.2 breaks BCM4360 DKMS

## Session Reference

- **PR:** omacom/omarchy#10910 (open)
- **Files changed:** `install/hardware/fix-bcm43xx.sh`, `test/shell.d/bcm43xx-wifi-fix-test.sh`
- **Verified on:** MacBook Air 5,2 (2012) with BCM43224
