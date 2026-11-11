# Intel AX211 Performance Notes

From session: MSI Titan GT77HX 13VI (2026-09-11)

## Hardware Details

| Field | Value |
|-------|-------|
| Chip | Intel 700 Series CNVi WiFi |
| PCI ID | 8086:7a70 (rev 11) |
| Subsystem | Rivet Networks Device 1692 |
| Driver | iwlwifi (kernel built-in) |
| Module | iwlmvm (HE/VHE support) |

## Current Performance (2026-09-11)

- Connection: 5 GHz, channel 52 (5260 MHz), 80 MHz width
- Link rate: 1200.9 MBit/s (HE-MCS 11, HE-NSS 2, HE-GI 0)
- Signal: -38 dBm (excellent)
- Regulatory: SE (Sweden, DFS-ETSI, includes 6 GHz)

## iwlwifi Parameters Active

| Parameter | Value | Meaning |
|-----------|-------|---------|
| 11n_disable | 0 | 11n enabled |
| amsdu_size | 0 | Default AMSDU |
| bt_coex_active | Y | BT coexistence active |
| disable_11ac | N | AC enabled |
| disable_11ax | N | AX enabled |
| disable_11be | N | BE enabled (if supported) |
| enable_ini | 16 | INI profile loaded |
| fw_restart | Y | Auto firmware restart |
| led_mode | 0 | LED off |
| power_level | 0 | Default power |
| power_save | N | Power save disabled |
| swcrypto | 0 | Hardware crypto |
| uapsd_disable | 3 | UAPSD disabled (all bits) |

## Observations

- The chip supports HE (WiFi 6) with 80 MHz channels
- 6 GHz band is supported and allowed by SE regulatory domain
- Current config is latency-optimized (power_save off, UAPSD off)
- 1200 Mbps is near-max for 80 MHz, 2x2 MIMO, HE-MCS 11
- To reach 2400 Mbps, would need 160 MHz channel + clean DFS spectrum

## Firmware

No separate firmware package needed for Intel WiFi — firmware is bundled
in `linux-firmware` package and loaded automatically by the driver.

## Commands Used

```bash
# Check capabilities
iw phy phy0 info | grep -E 'Band|Frequencies|HE.*GHz|VHE'

# Check current connection
iw dev wlo1 link

# List all parameters
for f in /sys/module/iwlwifi/parameters/*; do echo "$(basename $f) = $(cat $f 2>/dev/null)"; done
```
