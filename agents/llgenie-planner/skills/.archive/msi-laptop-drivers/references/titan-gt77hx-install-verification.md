# MSI Titan GT77HX 13VI — Live Install Verification (2026-09-12)

Results from running `install/hardware/msi.sh` directly on the target machine.

## Pre-install State

| Component | Status |
|-----------|--------|
| `r8125` module | Loaded (but `r8169` also loaded — conflict) |
| `msi_ec` module | Loaded |
| `thermald` service | **active** |
| `coolercontrold` service | inactive (disabled) |
| `/etc/modprobe.d/r8169.conf` | MISSING |
| `/etc/X11/xorg.conf.d/10-nvidia-dpms.conf` | MISSING |
| `/sys/devices/platform/msi-ec/` | Present but unused by Omarchy |

## Install Command

```bash
sudo env "PATH=$PATH OMARCHY_PATH=/usr/share/omarchy OMARCHY_INSTALL=/usr/share/omarchy/install" bash install/hardware/msi.sh
```

## Post-install State (verified)

| Check | Result |
|-------|--------|
| `r8169` blacklist created | `/etc/modprobe.d/r8169.conf` |
| `r8125` modules-load | `/etc/modules-load.d/r8125.conf` |
| `msi_ec` mkinitcpio | `/etc/mkinitcpio.conf.d/msi.conf` |
| `thermald` | inactive (disabled by script) |
| `coolercontrold` | active + enabled |
| NVIDIA X11 config | `/etc/X11/xorg.conf.d/10-nvidia-dpms.conf` |
| Packages | All 5 present and latest |
| EC shift_mode | comfort/silent available |
| UKI rebuilt | `/boot/EFI/Linux/omarchy_linux.efi` updated |
| limine.conf updated | `limine-mkinitcpio` ran |

## Post-Reboot Verification (verified 2026-09-12 after cold boot)

### System

| Field | Value |
|-------|-------|
| Model | MSI Titan GT77HX 13VI |
| BIOS | E17Q2IMS.108 |
| EC Firmware | 17Q2IMS1.107 (2023-02-21) |
| Kernel | 7.2.3-arch1-3 |
| CPU | Intel i9-13980HX |
| dGPU | NVIDIA RTX 4090 Laptop (AD103M) — nvidia-open-dkms 610.57.04 |
| iGPU | Intel UHD (Raptor Lake-S) |
| Ethernet | Killer E3000 / RTL8125B 2.5GbE |
| WiFi | Intel Wi-Fi 6E (CNVi) |

### Driver State

| Driver | Package | Status |
|--------|---------|--------|
| r8125 | r8125-dkms 9.018.00 | loaded |
| r8169 | kernel built-in | NOT loaded (blacklisted) |
| msi_ec | msi-ec-dkms-git r734.d7fbbd8 | loaded |
| msi_wmi_platform | kernel built-in | loaded |
| msi_wmi | kernel built-in | loaded |
| nvidia | nvidia-open-dkms 610.57.04 | loaded |
| iwlwifi | kernel built-in | loaded |
| coolercontrold | coolercontrol | active (running) |
| thermald | systemd | inactive (disabled) |

### EC Feature Dump (live)

| Feature | Current | Available |
|---------|---------|-----------|
| shift_mode | comfort | turbo, eco, comfort |
| fan_mode | silent | auto, silent, advanced |
| cooler_boost | off | — |
| super_battery | off | — |
| fn_key | left | — |
| win_key | right | — |
| webcam | on | — |
| webcam_block | off | — |

### Runtime Telemetry

| Sensor | Value |
|--------|-------|
| GPU temp | 45 C |
| GPU power | 3.44 W (idle, Optimus) |
| GPU core clock | 210 MHz |
| GPU mem clock | 405 MHz |
| Fan 1 RPM | 1500 |
| Fan 2 RPM | 0 |
| Fan 3 RPM | 1140 |
| Fan 4 RPM | 1140 |
| CPU freq range | 800 MHz — 4041 MHz |
| dGPU power state | D0 |

### Configuration Files Verified

- /etc/modprobe.d/r8169.conf — blacklist r8169
- /etc/modules-load.d/r8125.conf — early-load r8125
- /etc/modules-load.d/msi-ec.conf — early-load msi_ec
- /etc/mkinitcpio.conf.d/msi.conf — msi_ec in initramfs MODULES
- /etc/X11/xorg.conf.d/10-nvidia-dpms.conf — NVIDIA DPMS + backlight control

### Additional Verification Commands Passed

```
omarchy-hw-msi → exit 0 (detector works)
lsmod | grep r8169 → empty (blacklist active)
echo eco > /sys/devices/platform/msi-ec/shift_mode → write succeeded
nvidia-settings -q gpucoretemp → GPUCoreTemp: 45
journalctl -u coolercontrold → msi_wmi_platform detected with 4 fans
ls /sys/devices/platform/msi-ec/leds/ → platform::micmute, platform::mute
ls /sys/class/hwmon/hwmon5/fan*_input → 4 fans readable
```

### Gap Found During Verification

| Gap | Status |
|-----|--------|
| all.sh NOT wired on installed system | PR has the line, installed /usr/share/omarchy/install/hardware/all.sh does NOT — needs re-install |
| All other 9 issue items | VERIFIED working |

## Recovery Paths if Boot Fails

1. **Limine snapshot entries** — 3 snapshots in limine.conf (from 2026-09-11 and 09-12). They boot from UKI hash `a8feba63...` (pre-modification), not our new `1d4887bf...`. Pick Snapshot 1/2/3 at the Limine menu.

2. **`limine.conf.old`** — backup of previous limine config before our mkinitcpio run updated it.

3. **`@factory` subvolume** — clean Omarchy factory snapshot at `/dev/mapper/root` subvol=@factory.

## Test Suite Results

| Suite | Result |
|-------|--------|
| `test/shell.d/hw-msi-test.sh` | 25/25 passed |
| `test/cli` | all passed |
| `test/shell.d/hw-nvidia-test.sh` | 11/11 passed |
| Detection: 14 MSI families | all yes |
| Detection: desktop/other vendors | all no |
| Ad-hoc post-edit verification | passed (msi.sh edit didn't regress detection) |

## Outstanding

- RGB keyboard control not tested (msi-perkeyrgb installed but `msi-perkeyrgb --help` not run).
- Fan mode switching via EC exercised but not under sustained load (only idle tested).
- Battery threshold config not set (not in issue scope).
- all.sh wiring gap noted above — needs follow-up after PR merge.
