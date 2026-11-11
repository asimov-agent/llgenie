# Apple Silicon and arm64 images

## Why an arm64 ISO does not boot a Mac

Apple Silicon has no UEFI firmware. iBoot boots a signed macOS from internal
storage, or a m1n1 + U-Boot stack that the Asahi project installs *from macOS*.
It does not chainload an EFI System Partition on removable media, so no ISO
written to a USB stick — arm64, hybrid GPT, whatever — appears in the boot
picker. "Apple Silicon + USB installer" is not a formatting problem to solve.

Intel Macs are the opposite case: they have EFI, `dd` works, hold Option at boot.

## Omarchy on Apple Silicon (supported path, no USB)

The Omarchy Mac work merged into Omarchy; the boot side still lives in the
Omarchy Mac packages. Two routes, both macOS-side.

**A. GUI installer (preferred).** Open the notarized package, launch *Omarchy MX
Mac Installer* from Applications. It fetches the signed image, partitions, and
installs alongside macOS:

```
https://downloads.aicodelabs.com.au/installer/stable/Omarchy-MX-Mac-Installer.pkg
```

Verify first: `pkgutil --check-signature` / `spctl -a -vv -t install` must say
`Notarized Developer ID` (MARCELO DE BARROS ALCANTARA, T2C384FJBD). Admits only
the 22 M1/M2 models and refuses M3/M4 before touching the disk. Run
`omarchy update` afterwards.

**B. Terminal/Asahi route.** Run this in macOS Terminal, not from the stick:

```sh
curl https://asahi-alarm.org/installer-bootstrap.sh | sh
```

- Choose `Asahi Alarm Minimal (BTRFS)` and allocate at least 50 GB. The ext4
  variant works — the setup converts it — but BTRFS starts in the right shape.
- Boot the new install, log in as `root`/`root`, get online with `nmtui`
  (`Activate a connection`), then:

```sh
curl -fsSL https://raw.githubusercontent.com/omarchy-mac/omarchy-mac/quattro/bin/omarchy-mac-setup | bash
```

- ~15 minutes, three reboots, two prompts. Answer **no** to the gum dialog
  offering to build packages with no known aarch64 build (`obs-studio` alone
  compiles for hours and then fails the arch check).
- Root is encrypted by default (`--no-encrypt` to skip); the disk passphrase is
  chosen at the console on the encrypting boot, and the rewrite is resumable.
- Covers M1/M2 including Pro/Max. Newer chips are still in progress.
- Upstream omarchy-mac lags (4.0.3rc4); the maintained line is the MX Mac fork
  (maralcbr/omarchy-mx-mac, 4.0.4-mac.1).

## Reading a release's hardware list

An `aarch64` ISO often targets specific ARM laptops, not Macs — e.g. NVIDIA N1x
machines and Snapdragon X machines, where the ISO carries its own aarch64 kernel
and pulls GPU/DSP firmware (or device trees) at setup. Check the release notes'
named hardware before promising a boot. If the ISO contains no `uboot-asahi` or
m1n1 payload (a cheap `bytes.count()` scan over the image answered this in
seconds), it has no Apple Silicon boot path at all.

## Verifying a download

Compare `sha256sum <image>.iso` with the checksum published in the release notes;
they are usually listed next to each download link. A mismatch means re-download
— do not write the stick.
