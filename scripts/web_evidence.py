#!/usr/bin/env python3
"""The masked web reach, deployed: extract the URLs a bot run depends on, check they resolve, and
pre-fetch them for the agent (issue #380, follow-up of #362).

#362 built the reach — `make agent-fetch` (one leg, key by name, never printed) and
`make search-smoke` (a dead key dies loudly) — and no bot leg ever called either, so the capability
was unreachable from a run and no one could tell which URLs the bots depend on.

This script is the missing half, in three modes:

  list  <file>                 the candidate URLs named in <file> (an issue, `refine-in.md`, …)
  check <file> [--urls …]      one line per URL with its HTTP status; non-zero if any is dead
  fetch <file> --outdir D      pre-fetch each candidate with the REAL `make agent-fetch` target

`check` is deterministic and needs no model and no key: a link that 404s is dead for a bot too.
`fetch` drives `make agent-fetch URL=… OUT=…` — the one fetch leg, unchanged — and writes an index
the agent reads as evidence. It costs one model call per URL, so it is CAPPED (`--max`, default 3).

Nothing here prints a key: the fetch leg reads it from the environment inside the agent image.

Usage:
    python3 scripts/web_evidence.py list refine-in.md
    python3 scripts/web_evidence.py check tests/fixtures/bot-facing-urls.md
    python3 scripts/web_evidence.py fetch refine-in.md --outdir fetched --max 3
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
#: The URLs the bots are expected to be able to read when no issue names one. Kept in a fixture so
#: `make web-coverage` is deterministic and a reviewer sees the list under review.
DEFAULT_FIXTURE = REPO / "tests" / "fixtures" / "bot-facing-urls.md"
#: How many URLs one bot run may pre-fetch: each is a model call in the agent image.
DEFAULT_MAX = 3
#: A URL that resolves slower than this is not something a bot run should wait on.
TIMEOUT = 20

#: A candidate URL: http(s), no whitespace, no surrounding markdown punctuation.
URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"'`]+")
#: Trailing characters that belong to the prose, not to the URL.
TRAILING = ".,;:!?)]}"
#: Hosts a bot never needs to read: the machine it runs on is not "the web".
LOCAL = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")


def candidates(text: str) -> list[str]:
    """The distinct, bot-facing URLs named in `text`, in the order they appear.

    Prose wraps URLs in punctuation, so a trailing `.`/`)` is trimmed; a fragment is dropped (it
    changes nothing for a fetch); duplicates are collapsed; and a loopback URL is not a web reach.
    """
    out: list[str] = []
    for raw in URL_RE.findall(text):
        url = raw.rstrip(TRAILING)
        if url.split("/")[2].split("@")[-1].split(":")[0] in LOCAL:
            continue
        url = url.split("#", 1)[0]
        if url not in out:
            out.append(url)
    return out


def status(url: str, timeout: int = TIMEOUT) -> int | str:
    """The HTTP status of `url`, or a short reason string when it could not be read at all."""
    request = urllib.request.Request(url, headers={"User-Agent": "llgenie-web-coverage"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 — http(s) only
            return int(response.status)
    except urllib.error.HTTPError as e:
        return int(e.code)
    except Exception as e:  # noqa: BLE001 — any failure to read is the finding
        return type(e).__name__


def is_dead(status: int | str) -> bool:
    """Is this status a URL a bot run cannot depend on?

    401/403 are REACHABLE: the resource exists and wants a credential the bot does not have, which is
    a different problem from a link nobody can read. Anything >= 400 that is not one of those is dead,
    and a status that is not an int at all means the read itself failed.
    """
    if not isinstance(status, int):
        return True
    return status >= 400 and status not in (401, 403)


def check(urls: list[str], timeout: int = TIMEOUT) -> tuple[list[tuple[str, int | str]], int]:
    """(one `(url, status)` per URL, the number that are dead)."""
    rows = [(url, status(url, timeout)) for url in urls]
    return rows, sum(1 for _, s in rows if is_dead(s))


def render_index(outdir: Path, entries: list[tuple[str, Path | None]]) -> Path:
    """Write the evidence index the agent reads, and return its path."""
    lines = ["# Pre-fetched evidence (issue #380)", "",
             "The host fetched these URLs with the masked `make agent-fetch` leg before this run.",
             "Read them as evidence; a URL that could not be read is listed as such, and is NOT proof",
             "that the claim is wrong.", ""]
    for url, path in entries:
        if path is None:
            lines.append(f"- {url} — COULD NOT BE FETCHED (the leg failed; treat as unknown)")
        else:
            lines.append(f"- {url} — {path.relative_to(outdir.parent) if outdir.parent in path.parents else path}")
    index = outdir / "index.md"
    index.write_text("\n".join(lines) + "\n")
    return index


def fetch(urls: list[str], outdir: Path, max_urls: int = DEFAULT_MAX, make: str = "make") -> list[tuple[str, Path | None]]:
    """Pre-fetch each URL with the REAL `agent-fetch` target. Returns (url, path-or-None) per URL."""
    outdir.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[str, Path | None]] = []
    for i, url in enumerate(urls[:max_urls], start=1):
        out = outdir / f"evidence-{i}.md"
        result = subprocess.run([make, "--no-print-directory", "agent-fetch", f"URL={url}",
                                 f"OUT={out}"], cwd=REPO, capture_output=True, text=True)
        ok = result.returncode == 0 and out.is_file() and out.stat().st_size > 0
        entries.append((url, out if ok else None))
        print(f"[web-evidence] {'fetched' if ok else 'FAILED'} {url}"
              f"{'' if ok else f' (make agent-fetch rc={result.returncode})'}", file=sys.stderr)
    return entries


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract, check and pre-fetch the URLs a bot run needs.")
    ap.add_argument("mode", choices=("list", "check", "fetch"))
    ap.add_argument("file", nargs="?", default=None, help="the markdown to read (default: the fixture)")
    ap.add_argument("--urls", nargs="*", default=None, help="check these URLs instead of a file")
    ap.add_argument("--outdir", default="fetched", help="where `fetch` writes its evidence")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX, help=f"how many URLs to fetch (default {DEFAULT_MAX})")
    ap.add_argument("--timeout", type=int, default=TIMEOUT, help="per-URL read timeout in seconds")
    args = ap.parse_args(argv)

    if args.urls:
        urls = list(args.urls)
    else:
        path = Path(args.file) if args.file else DEFAULT_FIXTURE
        if not path.is_file():
            print(f"[web-evidence] FATAL: no such input: {path} — refusing to report on an empty list.",
                  file=sys.stderr)
            return 2
        urls = candidates(path.read_text())
        if not urls:
            print(f"[web-evidence] FATAL: {path} names no URL — a coverage report over nothing is not "
                  f"a pass.", file=sys.stderr)
            return 2

    if args.mode == "list":
        print("\n".join(urls))
        return 0

    if args.mode == "check":
        rows, dead = check(urls, args.timeout)
        for url, s in rows:
            print(f"HTTP {s}\t{url}")
        print(f"[web-coverage] {len(rows) - dead} of {len(rows)} URL(s) reachable.")
        if dead:
            print(f"[web-coverage] DEAD: {dead} URL(s) a bot run depends on could not be read.",
                  file=sys.stderr)
            return 1
        return 0

    entries = fetch(urls, Path(args.outdir), args.max)
    index = render_index(Path(args.outdir), entries)
    fetched = sum(1 for _, p in entries if p)
    print(f"[web-evidence] {fetched} of {len(entries)} candidate URL(s) fetched; index: {index}")
    # A fetch that could not read a URL is NOT fatal: the review must proceed, and the index says so.
    return 0


if __name__ == "__main__":
    sys.exit(main())
