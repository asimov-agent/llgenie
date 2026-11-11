---
name: network-audit
description: Audit local network devices and identify suspicious hosts via ARP, nmap scanning, OUI lookup, and port/service enumeration.
triggers:
  - "is there anything fishy on my network"
  - "scan my local network"
  - "what devices are on my LAN"
  - "check for unknown devices on my network"
  - "audit my home network"
  - "nmap scan my network"
---

# Network Audit

Scan and audit local network devices, identify suspicious hosts, and enumerate open ports/services.

## Prerequisites

```bash
# nmap is required
which nmap || sudo pacman -S --noconfirm nmap
```

## Workflow

### 1. Enumerate ARP Table

    ip -4 addr show | grep inet
    ip route show default
    cat /proc/net/arp | grep -v '00:00:00:00:00:00'

This gives you all recently-seen devices with IP, MAC, and interface.

### 2. OUI Lookup (Vendor Identification)

Extract the OUI (first 3 octets of MAC) and look up the vendor:

    echo "00:1c:c2" | tr -d ':' | cut -c1-6 | tr 'a-f' 'A-F'

Common OUIs:
- `04:42:1a` — ASUS
- `D4:A6:51`, `A8:80:55`, `54:60:09`, `94:94:26`, `B0:4A:39` — Apple
- `CC:64:1A`, `50:8A:06` — Xiaomi
- `FC:70:2E` — TP-Link
- `00:1C:C2` — Intel NIC
- `C0:18:03` — HP

### 3. Full Port Scan

Get IPs from ARP table and run nmap:

    ips=$(cat /proc/net/arp | grep -v '00:00:00:00:00:00' | awk '{print $1}' | tr '\n' ' ')
    nmap -sV -sC --top-ports 100 -T4 -n $ips

NOTE: OS detection (`-O`) requires root. Skip it for a standard audit.

### 4. Analyze Results

For each device with open ports, check:
- Is the service expected? (router admin on 8443 = normal)
- Is the certificate valid and self-signed appropriately?
- Are there unexpected services? (RDP, SMB, Telnet exposed on LAN = suspicious)
- Does the UPnP/service fingerprint match the expected device type?

### 5. Red Flags

- Unknown device with many open ports
- SMB (445) or RDP (3389) exposed from a non-server device
- Telnet (23) open on any device
- Services claiming to be from a different vendor than the MAC OUI suggests
- Reverse DNS returning unexpected hostnames

## Output Format

Present results as a compact table:

| IP | Device | Open Ports | Notes |
|---|---|---|---|
| 192.168.1.1 | Router (ASUS) | 53, 8443 | Expected |
| 192.168.1.50 | Apple iPhone | (all closed) | Normal |
| 192.168.1.100 | HP Printer | 80, 443, 631, 9100 | Expected |

Follow with a verdict: clean, suspicious device(s), or topology notes.

## Pitfalls

- nmap ARP resolution can fail if run without sufficient privileges — use `-n` to skip DNS
- Locally administered MACs (second bit of first octet = 1) mean MAC randomization — normal for modern phones
- Some IoT devices (Xiaomi, smart plugs) have filtered ports and show as "no-response" — not necessarily stealthy
- UPnP service fingerprints can be misleading (ASUS mesh reporting as Cisco Linksys is common with bridged APs)

## Reference Data

For detailed OUI mappings and service fingerprint interpretation, see `references/oui-service-fingerprints.md`.
