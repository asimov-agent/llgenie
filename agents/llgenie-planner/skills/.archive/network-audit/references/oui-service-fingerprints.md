# Network Audit — Common OUI and Service Fingerprints

## Common OUIs by Vendor

| OUI Prefix | Vendor | Typical Devices |
|---|---|---|
| `04:42:1a` | ASUS | Routers, mesh nodes |
| `D4:A6:51` | Apple | iPhone, Mac, iPad |
| `A8:80:55` | Apple | iPhone, Mac, iPad |
| `54:60:09` | Apple | iPhone, Mac, iPad |
| `94:94:26` | Apple | iPhone, Mac, iPad |
| `B0:4A:39` | Apple | iPhone, Mac, iPad |
| `CC:64:1A` | Xiaomi | IoT devices, phones |
| `50:8A:06` | Xiaomi | IoT devices, smart home |
| `FC:70:2E` | TP-Link | Switches, IoT hubs |
| `00:1C:C2` | Intel | Laptop/desktop NICs |
| `C0:18:03` | HP | Printers, workstations |
| `00:90:4C` | Cisco/Linksys | Routers, APs |
| `E2:4D:3D` | Apple | Locally administered (MAC random) |
| `32:BC:3E` | — | Locally administered (MAC random) |
| `6A:6B:5B` | — | Locally administered (MAC random) |
| `06:95:6B` | — | Locally administered (MAC random) |

## Locally Administered MACs

If the second-least-significant bit of the first octet is set, the MAC is locally administered (randomized). This is NORMAL behavior for:
- iOS devices (Settings > WiFi > Private Address)
- Android 10+ (Settings > WiFi > Randomized MAC)
- Linux with `macchanger`

These are NOT suspicious — they are privacy features.

## Service Fingerprints to Watch

| Service | Port | Normal Device | Suspicious If |
|---|---|---|---|
| DNS | 53 | Router, DNS server | On a phone or IoT device |
| HTTPS-Admin | 8443 | Router, AP, smart TV | On a phone or laptop |
| IPP/JetDirect | 631, 9100 | Printer | On a non-printer device |
| CastV2/AJP | 8008, 8009 | Chromecast, Cast-enabled | On a non-Cast device |
| UPnP | 49152 | Most modern devices | On a laptop or phone |
| SMB | 445 | NAS, Windows server | On a phone or IoT |
| RDP | 3389 | Windows workstation | On any other device type |
| Telnet | 23 | Legacy IoT, cameras | On a modern device |
| SSH | 22 | Servers, dev machines | On a phone or IoT |

## Router-Specific Fingerprints

**ASUS ZenWiFi / ASUS Routers:**
- Port 53 (DNS), 8443 (admin over SSL)
- httpd/3.0 server header
- Redirects to `/Main_Login.asp`
- UPnP may identify as "Cisco Linksys E4200" when bridging — this is a known quirk

**Google Chromecast / Nest:**
- Port 8008 (HTTP), 8009 (CastV2), 8443 (HTTPS)
- Google Inc. SSL cert
- CastV2 fingerprint: `ssl/castv2 Ninja Sphere Chromecast driver`

**HP Printers:**
- Port 80, 443, 515, 631, 9100
- Self-signed cert with commonName containing "HPC" prefix
- `X-Frame-Options: SAMEORPOSEC` headers

## False Positives

- ASUS mesh nodes showing UPnP as Cisco Linksys E4200 — normal bridged AP behavior
- Multiple Apple devices with locally administered MACs — normal privacy behavior
- Xiaomi devices with filtered ports — normal IoT firewall behavior
- No reverse DNS on LAN devices — normal for home networks
