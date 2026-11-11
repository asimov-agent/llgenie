---
name: intel-wifi-optimization
description: >-
  Optimize Intel WiFi performance on Arch Linux. Covers iwlwifi module
  parameters, regulatory domain settings, channel width, power management,
  and troubleshooting for Intel AX211, AX210, AX201, AX200, 9260, 9560, 8265,
  and other Intel wireless chips. Triggers: WiFi optimization, Intel WiFi,
  iwlwifi, slow WiFi, WiFi latency, WiFi throughput, wireless tuning,
  5 GHz, 6 GHz, WiFi 6, WiFi 6E.
---

# Intel WiFi Optimization (Arch Linux)

Optimize Intel wireless performance through driver parameters, regulatory
settings, and configuration tuning.

## When to use

When the user asks to improve WiFi speed, latency, or reliability on a
system with an Intel wireless chip.

## Identification

```bash
# Identify the WiFi chip
lspci -nn | grep -i network
# e.g., 8086:7a70 = Intel 700 Series CNVi (AX211)

# Check current driver and firmware
dmesg | grep -i 'iwlwifi.*firmware\|iwlwifi.*loaded' | tail -5

# Check current connection
iw dev wlo1 link
```

## Current State Assessment

```bash
# All iwlwifi parameters
for f in /sys/module/iwlwifi/parameters/*; do
  echo "$(basename $f) = $(cat $f 2>/dev/null)"
done

# iwlmvm parameters (for newer chips)
for f in /sys/module/iwlmvm/parameters/*; do
  echo "$(basename $f) = $(cat $f 2>/dev/null)"
done

# Regulatory domain
iw reg get | head -10

# Chip capabilities
iw phy | grep -A30 'Supported interface modes\|Band\|Frequencies\|HT information\|VHE\|HE.*GHz'
```

## Common Optimizations

### 1. Disable power save (lowest latency)
Already default on most systems. Verify:
```bash
cat /sys/module/iwlwifi/parameters/power_save
# N = disabled (good for latency)
# Y = enabled (saves battery, adds latency)
```

To disable at boot:
```bash
echo "options iwlwifi power_save=0" | sudo tee /etc/modprobe.d/iwlwifi.conf
```

### 2. Hardware crypto (default)
```bash
cat /sys/module/iwlwifi/parameters/swcrypto
# 0 = hardware crypto (good)
# 1 = software crypto (slower, for debugging)
```

### 3. UAPSD (Unscheduled Automatic Power Save Delivery)
```bash
cat /sys/module/iwlwifi/parameters/uapsd_disable
# 0 = enabled (power saving)
# 3 = disabled (lower latency, better for gaming/real-time)
```

### 4. Bluetooth coexistence
```bash
cat /sys/module/iwlwifi/parameters/bt_coex_active
# Y = enabled (shares antenna with BT)
# N = disabled (full WiFi performance, disable if not using BT)
```

To disable BT coex:
```bash
echo "options iwlwifi bt_coex_active=N" | sudo tee /etc/modprobe.d/iwlwifi.conf
```

### 5. 160 MHz channel width
Requires router support and clean DFS spectrum. Check if supported:
```bash
iw phy | grep '160 MHz' | head -5
```

If supported, the driver will use it automatically when available. No
manual configuration needed — the AP advertises 160 MHz capability.

### 6. WiFi 6E (6 GHz)
Requires:
- Intel chip that supports 6 GHz (AX211, AX210, AX411)
- 6E-capable router
- Regulatory domain that allows 6 GHz

Check 6 GHz support:
```bash
iw phy | grep '5945.*6425\|6GHz' | head -5
```

Sweden (SE) allows 5945–6425 MHz (NO-OUTDOOR). If your router supports
6 GHz, connect to the 6 GHz SSID for the cleanest, fastest connection.

### 7. AMSDU size
```bash
cat /sys/module/iwlwifi/parameters/amsdu_size
# 0 = default (usually optimal)
# 1 = short AMSDU (lower latency)
# 4 = long AMSDU (higher throughput)
```

### 8. Disable 11n/11ac/11ax/11be (debugging only)
```bash
cat /sys/module/iwlwifi/parameters/disable_11ac
cat /sys/module/iwlwifi/parameters/disable_11ax
cat /sys/module/iwlwifi/parameters/disable_11be
```
All should be `N` for normal operation. Only disable for debugging
compatibility issues.

## Performance Expectations by Chip

| Chip | Max PHY Rate | Band | MIMO |
|------|-------------|------|------|
| AX211 | 2402 Mbps | 5/6 GHz | 2x2 |
| AX210 | 2402 Mbps | 5/6 GHz | 2x2 |
| AX201 | 1201 Mbps | 5 GHz | 2x2 |
| AX200 | 2402 Mbps | 5 GHz | 2x2 |
| 9260 | 1733 Mbps | 5 GHz | 2x2 |
| 9560 | 1733 Mbps | 5 GHz | 2x2 |

Real-world throughput is typically 50-70% of the PHY rate.

## Troubleshooting

- **Slow speeds**: Check signal strength (`iw dev wlo1 link`), ensure on
  5 GHz not 2.4 GHz, check for interference.
- **High latency**: Disable power_save, disable UAPSD, disable BT coex.
- **Connection drops**: Check `dmesg | grep iwlwifi`, may be firmware crash.
  Try `echo 1 | sudo tee /sys/module/iwlwifi/parameters/fw_restart` to
  enable firmware restart on crash.
- **Not connecting to 6 GHz**: Check regulatory domain allows 6 GHz,
  router must be 6E, driver must support it.

## Pitfall: No alternative drivers for Intel WiFi

Intel WiFi chips use the `iwlwifi` driver, which is built into the kernel.
There are no alternative drivers to install. Optimization is limited to
module parameters, firmware updates, and configuration. Don't search for
"better drivers" — they don't exist for Intel WiFi.

## Pitfall: User prefers terse responses

When reporting WiFi status:
- State the chip, current speed, and signal in 2-3 lines
- List only actionable optimizations, not every parameter
- Don't explain what iwlwifi is unless asked
- Don't offer follow-up options unless asked

## References

- `references/ax211-performance.md` — Intel AX211 specific notes and benchmarks
- `references/iwlwifi-parameters.md` — Full iwlwifi module parameter reference
