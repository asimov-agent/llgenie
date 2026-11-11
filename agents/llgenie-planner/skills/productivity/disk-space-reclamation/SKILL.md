---
name: disk-space-reclamation
description: Use when a disk is filling up or a resize is asked.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [disk, btrfs, luks, limine, snapper, cleanup]
    related_skills: [omarchy]
---

# Disk Space Reclamation & Volume Resizing

## When to Use

- "My drive / boot drive is N% full" or the volume is nearly full.
- "What is using the space?" / "What can we clean up?"
- "Can we double the volume?" / "Is it easy to resize the partition?"
- Auditing `/boot`, btrfs snapshots, journal, or package cache on an Arch/Omarchy machine.

The job is a measured audit, a safe reclaim, and a straight answer about what is *not* resizable.

## Procedure

1. **Measure before you answer anything.**
   ```bash
   df -hT -x tmpfs -x devtmpfs
   lsblk -o NAME,SIZE,FSTYPE,TYPE,MOUNTPOINTS,MODEL
   ```
   Never accept the user's label for *which* volume is full. "My boot drive is 75% full" is usually a 2 GB ESP, while the multi-TB root sits at 25%. Name the exact mountpoint in your answer, with numbers.

2. **On btrfs, `df` speaks two dialects.** `btrfs filesystem usage /` shows Device size / Allocated / Used. `btrfs filesystem du -s /path` shows Total / **Exclusive** / Set shared per subvolume — snapshots can pin hundreds of GiB that a plain `du -sh` never attributes. Deletion frees the exclusive extents plus any shared extents that lose their last reference, so the reclaimed figure usually exceeds the exclusive one.

3. **Find the actual hogs by file size, not by directory name.**
   ```bash
   sudo du -xhd1 / | sort -h | tail -10
   sudo find /boot -type f -size +1M -printf '%s %TY-%Tm-%Td %p\n' | sort -rn
   ```
   A 250 MB UKI or a 2.6 GB package tarball explains the number; "/usr is 15G" does not.

4. **Reclaim the safe tiers first, without asking** (no user data, no rollback lost):
   ```bash
   sudo journalctl --vacuum-size=400M
   sudo paccache -rk2            # Omarchy default policy: keeps offline downgrade
   ```
   Report freed bytes per tier; measure with `du -sb` before and after.

5. **Anything that deletes rollback, kernels, or packages needs an explicit choice.** Snapshot deletion and `paccache -rk1` are destructive: present a table (item / size / risk) and ask, then act on the answer. Do not bundle them into "cleanup".

6. **Resize claims get a hard reality check before any optimism.**
   - btrfs only shrinks **from the end**.
   - Growing a partition that sits *before* another partition means moving the later partition's start, which for LUKS/btrfs payloads means relocating the data (backup + restore). Say no.
   - No LVM ⇒ no online grow of an existing volume. The honest "double it" is `btrfs device add`, or a second disk.
   See `references/btrfs-luks-limine-esb.md` for the worked Omarchy/Limine case and its command set.

7. **Report as a before/after table, then state what will recur.** A one-time clean that leaves the structural limit in place is half a fix — compute the worst case (e.g. snapshot limit × kernels × UKI size vs ESP size) and recommend the config change that prevents the next round. Ship both halves: the cap (snapper `NUMBER_LIMIT`) *and* the footprint change (drop a kernel you never boot). The kernel-removal procedure, plus the DKMS and stale-module-tree cleanup pacman leaves behind, is in `references/btrfs-luks-limine-esb.md`.

## Pitfalls
- **`paccache -rk2` can free almost nothing while the cache looks huge** — keeping "two versions of everything" still keeps two copies of one giant package (CUDA, nvidia-utils). List the largest files before promising a number.
- **Deleting snapshots does not necessarily shrink a small ESP.** Kernel images are reference-counted across snapshots: if several snapshots boot the same kernel, pruning the older ones frees zero bytes in `/boot`. Compute the referenced set, keep at least one snapshot, then sync the bootloader.
- **Never `rm` files a bootloader tool owns.** For Limine UKIs, delete snapshots via `snapper` and let `limine-snapper-sync` rewrite `limine.conf` and drop orphaned history images. Hand-deleting leaves `limine.conf` pointing at missing EFIs — unbootable on the next reboot.
- **Editing `/etc/snapper/configs/root` is the durable fix.** `NUMBER_LIMIT` with `TIMELINE_CREATE=no` never shrinks on its own; a limit larger than the ESP can hold is a scheduled outage.
- **Probe `sudo -n true` first.** It separates "sudo needs a password" from "sudo is broken": if it prompts, still do the read-only audit (`df`, `lsblk`, `btrfs filesystem usage`) and hand over the exact privileged commands instead of stalling.
- **Re-measure minutes later — btrfs frees space asynchronously.** After a snapshot delete the cleaner reclaims extents in the background: `btrfs filesystem usage` can read 20-100 GiB higher a couple of minutes after the command returned. Take a second reading before quoting the final total, and never conclude the delete "didn't work" from the first `df`.
- **Report freed space per subsystem, not one fake total.** Journal, package cache, snapshot extents and the ESP are different filesystems with different accounting; adding them up produces a number nobody can verify.

## Verification
After a reclaim, re-run `df -h <mountpoint>` and `btrfs filesystem usage /` and quote both. If a number did not move (e.g. `/boot` unchanged after a cache prune), say so rather than implying it did.
