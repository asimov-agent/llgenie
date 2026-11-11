#!/bin/bash
# Verify MSI laptop driver state after install/reboot.
# Usage: bash /home/asimov/.hermes/skills/drivers/msi-laptop-drivers/scripts/verify-msi.sh

set -euo pipefail

PASS=0
FAIL=0

check() {
  local desc="$1" result="$2"
  if [[ "$result" == "pass" ]]; then
    echo "  PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== 1. Detector ==="
omarchy-hw-msi && check "MSI detected" "pass" || check "MSI detected" "fail"

echo ""
echo "=== 2. DKMS modules ==="
lsmod | grep -q r8125 && check "r8125 loaded" "pass" || check "r8125 loaded" "fail"
lsmod | grep -q msi_ec && check "msi_ec loaded" "pass" || check "msi_ec loaded" "fail"

echo ""
echo "3. No conflicts ==="
lsmod | grep -q r8169 && check "r8169 blacklisted" "fail" || check "r8169 blacklisted" "pass"

echo ""
echo "=== 4. Thermal services ==="
systemctl is-active thermald &>/dev/null && check "thermald inactive" "fail" || check "thermald inactive" "pass"
systemctl is-active coolercontrold &>/dev/null && check "coolercontrold active" "pass" || check "coolercontrold active" "fail"

echo ""
echo "=== 5. EC features ==="
ls /sys/devices/platform/msi-ec/shift_mode &>/dev/null && check "EC shift_mode accessible" "pass" || check "EC shift_mode accessible" "fail"
ls /sys/devices/platform/msi-ec/fan_mode &>/dev/null && check "EC fan_mode accessible" "pass" || check "EC fan_mode accessible" "fail"

echo ""
echo "=== 6. Fan detection ==="
ls /sys/class/hwmon/hwmon*/name 2>/dev/null | xargs grep -l msi_wmi_platform 2>/dev/null > /dev/null && check "msi_wmi_platform hwmon found" "pass" || check "msi_wmi_platform hwmon found" "fail"

echo ""
echo "=== 7. NVIDIA ==="
nvidia-settings -q gpucoretemp &>/dev/null && check "nvidia-settings works" "pass" || check "nvidia-settings works" "fail"

echo ""
echo "=== 8. all.sh wiring ==="
grep -q msi.sh /usr/share/omarchy/install/hardware/all.sh 2>/dev/null && check "all.sh wired" "pass" || check "all.sh wired" "fail"

echo ""
echo "=== 9. Configuration files ==="
ls /etc/modprobe.d/r8169.conf &>/dev/null && check "r8169 blacklist exists" "pass" || check "r8169 blacklist missing" "fail"
ls /etc/modules-load.d/r8125.conf &>/dev/null && check "r8125 early-load exists" "pass" || check "r8125 early-load missing" "fail"
ls /etc/modules-load.d/msi-ec.conf &>/dev/null && check "msi-ec early-load exists" "pass" || check "msi-ec early-load missing" "fail"
ls /etc/mkinitcpio.conf.d/msi.conf &>/dev/null && check "mkinitcpio msi.conf exists" "pass" || check "mkinitcpio msi.conf missing" "fail"
ls /etc/X11/xorg.conf.d/10-nvidia-dpms.conf &>/dev/null && check "NVIDIA DPMS exists" "pass" || check "NVIDIA DPMS missing" "fail"
ls /etc/msi-perkeyrgb.conf &>/dev/null && check "RGB config exists" "pass" || check "RGB config missing" "fail"

echo ""
echo "=== 10. Battery thresholds ==="
START=$(cat /sys/class/power_supply/BAT1/charge_control_start_threshold 2>/dev/null)
END=$(cat /sys/class/power_supply/BAT1/charge_control_end_threshold 2>/dev/null)
echo "  Start: ${START}%  End: ${END}%"
[[ "$START" == "60" ]] && check "start threshold = 60" "pass" || check "start threshold = 60" "fail"
[[ "$END" == "80" ]] && check "end threshold = 80" "pass" || check "end threshold = 80" "fail"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
