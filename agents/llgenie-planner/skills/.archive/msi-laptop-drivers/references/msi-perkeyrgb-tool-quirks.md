# msi-perkeyrgb Tool Quirks

Session-derived notes on msi-perkeyrgb behavior and gotchas (2026-09-12).

## Config Format

msi-perkeyrgb does NOT support INI-style, JSON, or TOML config files. The config file
uses a simple line-based format:

```
<keycodes> <mode> <color>
```

- **keycodes**: `all`, `f_row`, `arrows`, `numrow`, `numpad`, `characters`, `fn`, or decimal keycode ranges (e.g., `15-23`, `25,38,39,40`)
- **mode**: `steady` (only mode currently supported)
- **color**: hex HTML color without `#` (e.g., `00ff00` for green)

Example config (`/etc/msi-perkeyrgb.conf`):
```
all steady 00ff00
```

Multiple lines can target different key groups. Lowest line takes priority for overlapping keys.

## Supported Models

Run `msi-perkeyrgb --list-models` to see current list. As of 2.1-2:

- GE63, GE73, GE75
- GS63, GS73, GS75
- GX63, GT63
- GL63
- GS65

**GT75 is NOT supported.** For Titan GT77HX, use GS75 as closest match.

## USB Detection

The tool internally calls `lsusb` to find keyboards. If `lsusb` is not installed
(`usbutils` package missing), the tool fails with:
```
No MSI keyboards with a known product/vendor IDs were found.
```

Fix: `sudo pacman -S --noconfirm usbutils`

## USB IDs

| Model | Device | USB ID | Notes |
|-------|--------|--------|-------|
| Titan GT77HX | SteelSeries KLC | 1038:113a | Keyboard (hidraw0/1) |
| Titan GT77HX | SteelSeries ALC | 1038:1146 | Keyboard (hidraw?) |
| Most MSI laptops | Default | 1038:1122 | Standard per-key RGB |

Override with `--id VENDOR_ID:PRODUCT_ID` flag.

## Permissions

Requires read/write access to `/dev/hidraw*`. Two options:

1. **Run as root**: `sudo msi-perkeyrgb ...`
2. **udev rules**: Create `/etc/udev/rules.d/99-msi-rgb.rules`:
   ```
   KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1038", ATTRS{idProduct}=="113a", MODE="0666"
   KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1038", ATTRS{idProduct}=="1146", MODE="0666"
   KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1038", ATTRS{idProduct}=="1122", MODE="0666"
   ```
   Then: `sudo udevadm control --reload-rules && sudo udevadm trigger`

## Usage Examples

```bash
# All keys green
msi-perkeyrgb --model GS75 --id 1038:113a -s 00ff00

# From config file
msi-perkeyrgb --model GS75 --id 1038:113a -c /etc/msi-perkeyrgb.conf

# Disable RGB
msi-perkeyrgb --model GS75 --id 1038:113a -d

# List presets
msi-perkeyrgb --model GS75 --list-presets
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `No laptop model specified, using GE63 as default` | No `--model` flag | Add `--model GS75` |
| `Unknown MSI model : GT75` | GT75 not supported | Use GS75 |
| `No MSI keyboards with a known product/vendor IDs were found` | lsusb missing or wrong USB ID | Install usbutils, use `--id 1038:113a` |
| `Cannot open keyboard` | Permissions | Run as root or add udev rules |
| `Error reading config file : string index out of range` | INI-style config format | Use `all steady 00ff00` format |

## Known Non-Functional Models

### Titan GT77HX 13VI (Cherry MX Mechanical Keyboard)

The GT77HX uses a **Cherry MX Ultra Low Profile mechanical keyboard** (SteelSeries, USB 1038:113a/1146). `msi-perkeyrgb` writes to the hidraw device successfully (exit code 0) but has no effect on the backlight — the keyboard uses a different HID protocol than the tool implements.

**Evidence on real hardware:**
- `msi-perkeyrgb --model GS75 --id 1038:113a -s ffffff` → exit code 0, no change
- hidraw device exists (`/dev/hidraw0`, `HID_ID=0003:00001038:0000113A`), permissions correct (0666)
- `msi-perkeyrgb --list-models` does NOT include GT75/GT77/Titan
- All tested models (GS75, GS73, GS63, GE75, GE73, GE63) — same silent exit-0, no effect

**What this means for PRs/issues:**
- **RGB was REMOVED from the PR, tests, and documentation.**
- A separate issue (#11573) was created to track RGB support for GT77HX when a compatible tool becomes available.
- DO NOT add RGB support back to MSI laptop PRs for GT77HX.
- Alternative approaches: SteelSeries GG via Wine/Proton, OpenRGB (if GT77HX support added), MSI Center on Windows

**Diagnostic commands:**
```bash
# Check if hidraw device exists and permissions
ls -la /dev/hidraw* | grep -i 1038

# Check hidraw device info
cat /sys/class/hidraw/hidraw0/device/uevent
# Expect: HID_ID=0003:00001038:0000113A, DRIVER=hid-generic

# Test apply (will succeed silently)
msi-perkeyrgb --model GS75 --id 1038:113a -s ffffff
echo "Exit: $?"  # 0, but nothing happens
```
