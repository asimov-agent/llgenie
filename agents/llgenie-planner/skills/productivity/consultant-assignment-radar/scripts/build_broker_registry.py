#!/usr/bin/env python3
"""Build the broker registry the sweep runs against — every Swedish konsultmäklare.

Sources (both are public, curated registers):
  * annaleijon.se/lista-pa-konsultmaklare-i-stockholm.html  (~118 actors, with the
    "Uppdrags-portal" link per actor)
  * kretsia.com/sv/guide/konsultmaklare/                     (60 actors, checked against
    each company's own site)

Output: references/broker-registry.json  ->  [{name, url, site, email}]

Run whenever the registers change (they are updated a few times a year):
    python3 scripts/build_broker_registry.py
"""
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
ANNA = "https://annaleijon.se/lista-pa-konsultmaklare-i-stockholm.html"
KRETSIA = "https://www.kretsia.com/sv/guide/konsultmaklare/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "broker-registry.json")
# employers that slipped into the registers' link tables — not brokers
DROP_HOSTS = {"career.hemnet.se", "www.coody.com", "career.techlove.se", "www.linkedin.com",
              "www.allabolag.se", "annaleijon.se"}


def get(url):
    return subprocess.run(["curl", "-s", "-L", "-m", "40", "-A", UA, url],  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)
                          capture_output=True, text=True).stdout


def from_kretsia(html):
    out = {}
    for href, label in re.findall(r'href="(https?://(?!www\.kretsia\.com)[^"]+)"[^>]*>\s*([^<]{2,80})<', html):
        label = re.sub(r"\s+", " ", label).strip()
        host = urlparse(href).netloc.lower().replace("www.", "")
        if len(label) > 2 and host not in DROP_HOSTS:
            out.setdefault(label, {"site": href})
    return out


def from_annaleijon(html):
    """Each table row carries the broker name and (later in the row) its assignment-portal link."""
    out = {}
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html):
        nm = re.search(r"(?is)<strong[^>]*>(.*?)</strong>", row) or re.search(r"(?is)<b[^>]*>(.*?)</b>", row)
        if not nm:
            continue
        name = re.sub(r"<[^>]+>", " ", nm.group(1))
        name = re.sub(r"\s+", " ", name).replace("&amp;", "&").strip()
        if not (2 < len(name) < 60):
            continue
        links = [h for h in re.findall(r'href="(https?://[^"]+)"', row)
                 if not any(d in h for d in DROP_HOSTS)]
        links = [l for l in links if "utm_source" not in l.split("?")[0][-20:]]
        mail = re.search(r"[\w.+-]+@[\w.-]+\.\w+", row)
        entry = out.setdefault(name, {})
        if links:
            entry.setdefault("portal", links[0])
        if mail:
            entry.setdefault("email", mail.group(0))
    return out


def main():
    kretsia = from_kretsia(get(KRETSIA))
    anna = from_annaleijon(get(ANNA))
    combined, seen_hosts = [], set()
    for name, v in list(kretsia.items()) + list(anna.items()):
        a = anna.get(name, {})
        k = kretsia.get(name, {})
        url = a.get("portal") or k.get("site") or ""
        if not url:
            continue
        host = urlparse(url).netloc.lower().replace("www.", "")
        if host in seen_hosts or host in DROP_HOSTS:
            continue
        seen_hosts.add(host)
        combined.append({"name": name, "url": url, "site": k.get("site", ""), "email": a.get("email", "")})
    combined.sort(key=lambda b: b["name"].lower())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(combined, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"broker registry: {len(combined)} actors -> {os.path.abspath(OUT)}")
    print(f"(kretsia rows: {len(kretsia)}, annaleijon rows: {len(anna)})")


if __name__ == "__main__":
    main()
