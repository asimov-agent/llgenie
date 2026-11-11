# btrfs + LUKS + Limine UKI systems (Omarchy/Arch)

Worked detail for the common case: single NVMe, ESP first, LUKS+btrfs root second, Limine booting unified kernel images, snapper managing rollback snapshots.

## Layout that produces the "boot drive is full" report

```
nvme1n1  1.9T
├─p1    2.0G  vfat   /boot           <- the 75% the user sees
└─p2    1.9T  LUKS -> btrfs /         <- usually 25-30% used, 1.4T free
```

`df` output that triggers the question (EFI vars are noise, ignore them):

```
efivarfs          192K  126K   62K  67% /sys/firmware/efi/efivars
/dev/nvme1n1p1    2.0G  1.5G  517M  75% /boot
/dev/mapper/root  1.9T  518G  1.4T  28% /
```

## Where a 2 GB ESP actually goes

UKI systems build one ~250 MB unified image per kernel per generation:

```
/boot/EFI/Linux/omarchy_linux.efi             249 M   current
/boot/EFI/Linux/omarchy_linux-omarchy.efi     252 M   current
/boot/<machine-id>/limine_history/*.efi       ~1 GB    copies pinned by snapshots
/boot/intel-ucode.img                          15 M
```

So the ESP budget is `(kernels booted) x (snapshots kept + 1 current) x image size`. Two kernels at 250 MB with `NUMBER_LIMIT=5` needs 3 GB on a 2 GB ESP — a guaranteed future failure, not bad luck.

## Audit commands

```bash
sudo du -sh /boot
sudo find /boot -type f -size +1M -printf '%s %TY-%Tm-%Td %p\n' | sort -rn
sudo snapper -c root list
grep -E '^(SUBVOLUME|TIMELINE_CREATE|NUMBER_LIMIT)' /etc/snapper/configs/root
sudo btrfs filesystem du -s /.snapshots      # Total / Exclusive / Set shared
sudo btrfs subvolume list /
journalctl --disk-usage
sudo du -sh /var/cache/pacman/pkg
sudo find /var/cache/pacman/pkg -size +100M -printf '%s %f\n' | sort -rn | head
```

## Cleanup sequence that is safe

```bash
sudo journalctl --vacuum-size=400M
sudo paccache -rk2 -q                    # Omarchy's own policy (omarchy-update-pkg-prune)
sudo rm -f /boot/limine.conf.old /boot/<machine-id>/limine_history/snapshots.json.old
```

`omarchy-update-pkg-prune` only wraps `paccache -rk2`; there is **no** Omarchy command that manages `/boot` or Limine's history. Check with `omarchy commands` before promising one exists.

## Reclaiming /boot properly

Delete snapshots through snapper, then let the sync tool manage the files:

```bash
for s in 11 12 13 14; do sudo snapper -c root delete "$s"; done
sudo limine-snapper-sync                 # rewrites limine.conf, drops orphaned history EFIs
```

`limine-snapper-sync` has no meaningful `--help`/`--version` output — any invocation performs a sync and prints `Updated: /boot/limine.conf`. Calling it *is* the action, so don't probe with flags on a system you have not audited. To inspect instead of act, use the companion tools: `sudo limine-snapper-list` (bootable snapshot entries), `sudo limine-snapper-info`, and `sudo limine-snapper-remove <id>` (drops one entry and its kernel files without touching the snapper snapshot).

Verify both sides afterwards: `sudo snapper -c root list`, the `Snapshots` block in `/boot/limine.conf`, and `sudo du -sh /boot`.

## Dropping the stock kernel (the durable half of the fix)

Check nothing needs it, then remove without `-s` (dependency sweeping can take firmware with it) and without `--print` (rejected together with `-n`):

```bash
pacman -Qi linux linux-headers | grep -E '^(Version|Required By)'
sudo pacman -R --noconfirm linux linux-headers
```

The `limine-mkinitcpio` post-transaction hook does the bootloader side by itself:

```
(3/3) Clean Limine boot entries of removed kernels
Removed unused Limine boot entry: linux
```

Two leftovers pacman does not touch:

```bash
dkms status                              # entries still list the dead kernel
sudo dkms remove -m nvidia -v 615.78.08 -k 7.2.11-arch1-1     # -m/-v/-k, never positional
ls /usr/lib/modules/                     # unowned <ver> dirs survive the package
sudo rm -rf /usr/lib/modules/<removed-ver>                    # verify with pacman -Qo first
```

`dkms remove` takes `-m <module> -v <version> -k <kernel>`; positional args print a usage block and do nothing. Removing a DKMS entry for an already-deleted kernel can itself recreate an empty `/usr/lib/modules/<ver>` dir — re-check after and delete it.

Expect the snapshot entries to keep a kernel you just uninstalled: each `limine_history` image is a **self-contained UKI**, so `////linux` under a snapshot still boots without the package. That is ~250 MB of ESP spent on a kernel you removed; reclaim it only by deleting that snapshot (`sudo snapper -c root delete <id> && sudo limine-snapper-sync`), which also costs the rollback point. State the trade rather than silently dropping it.

## Durability

- `NUMBER_LIMIT=3` (or 2) with `TIMELINE_CREATE=no` caps the ESP instead of letting it grow to the limit.
- Boot one kernel. Shipping both `linux` and `linux-omarchy` doubles every figure above; if the user only boots `linux-omarchy`, dropping stock `linux` halves the churn.
- A 2 GB first-mounted ESP cannot be grown in place: p2 (LUKS) starts immediately after it, and moving p2's start means relocating ~2 TB of encrypted payload. Do not offer `parted`/`sgdisk` moves here.
- Idle second NVMe: `btrfs device add /dev/mapper/<luks> /` is the genuine doubling path (single profile — more space, no extra redundancy).
