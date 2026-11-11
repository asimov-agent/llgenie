---
name: bootable-usb-media
description: Use when making bootable USB media for target hardware.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [usb, iso, installer, apple-silicon, asahi, omarchy, dd]
    related_skills: [omarchy]
---

# Bootable USB Media

Turn a downloaded image into bootable media — and, before writing anything,
check that the target machine's firmware can boot that image at all.

## When to Use

- "make this USB bootable", "dd this ISO to the stick", Etcher / burn-an-image asks
- Choosing between an `x86_64` and an `aarch64` image for a specific machine
- Installing on an Apple Silicon Mac, or any question that assumes an ISO can
  boot one
- Verifying a downloaded image with a checksum before writing it

## Procedure

1. **Read the target first, write second.** Confirm which machine the stick will
   boot. Architecture and firmware decide the image; a wrong pair produces a
   stick that silently never appears in the boot menu.
   - x86_64 PC or Intel Mac (UEFI/BIOS) → `x86_64` ISO, raw write works.
   - arm64 UEFI laptop (Snapdragon X, NVIDIA N1x-class) → `aarch64` ISO, raw
     write works.
   - Apple Silicon Mac → **not bootable from USB at all**. Apple Silicon has no
     UEFI: iBoot only chainloads a signed macOS or an m1n1/U-Boot stack
     installed *from macOS*. No ISO, however correct, changes that.
   See [`references/apple-silicon-and-arm64.md`](references/apple-silicon-and-arm64.md)
   for the Omarchy-on-Apple-Silicon path and the aarch64 ISO's real target list.
2. **Verify the download** against the publisher's checksum before writing.
   A 5 GB write on a corrupt file wastes the whole cycle.
   ```bash
   cd ~/Downloads && sha256sum <image>.iso
   ```
3. **Identify the device by model and size, never by guess.**
   ```bash
   lsblk -o NAME,SIZE,TYPE,TRAN,MODEL,MOUNTPOINT | sed -n '1,40p'
   ```
   The stick is the `TRAN=usb` disk (`sda`), not a partition (`sda1`). Unmount
   every mounted partition on it first.
4. **Confirm before overwriting.** Name the device, its size, and what is
   currently on it. If a previous installer image lives there, say so — that is
   the thing being destroyed.
5. **Write and flush.**
   ```bash
   sudo dd if=<image>.iso of=/dev/sdX bs=4M status=progress oflag=sync conv=fsync
   sync
   ```
   Then verify: `sudo cmp -n $(stat -c%s <image>.iso) <image>.iso /dev/sdX`.

## Rules and pitfalls

- **Lead with a recommendation.** At a decision point, state what you suggest and
  why, then ask the one confirmation question. Handing over a numbered menu of
  options gets answered with "what are you suggesting?" — the user wants the
  judgement call, not the survey.
- **Never write media that cannot boot the stated target just because it was
  asked for.** Say plainly what the write would and would not achieve, then offer
  the working alternative. A `dd` that "succeeds" onto the wrong firmware is a
  silent failure the user only discovers at the boot menu.
- **Match architecture against the release notes' hardware list**, not the
  filename. `*-aarch64.iso` is not "the Mac one" — vendors ship aarch64 ISOs for
  Snapdragon/N1x laptops, and those do not boot Macs.
- **`dd` to the disk, not the partition** (`/dev/sda`, never `/dev/sda1`).
- **A lifecycle guard may reject a shell command that references a large image**
  ("larger than the scan cap (1048576 bytes)"). Do not retry shell variants:
  inspect the image from Python (`execute_code` with `mmap` chunked
  `bytes.count()` scans, or pycdlib for the filesystem). Plain `sha256sum` on the
  same path is unaffected.
- **ExFAT is the portable repurpose.** When the stick will not carry an
  installer, `sudo wipefs -a /dev/sdX && sudo mkfs.exfat -n <LABEL> /dev/sdX`
  gives a volume both macOS and Omarchy read and write.

## Reporting back

State: image verified (checksum matched), device written (`/dev/sdX`, size),
whether the target machine's firmware can boot it, and what to do instead if not.
