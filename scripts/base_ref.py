#!/usr/bin/env python3
"""Resolve the BASE ref, instead of hard-coding `origin/main` (issue #925).

This host has two clone layouts and they name the same two repositories differently:

```
ai-repositories/llgenie   origin = the fork        upstream = asimov-agent/llgenie
git/llgenie               origin = asimov-agent    fork     = the fork
```

A test or script that diffs against `origin/main` therefore compares against a DIFFERENT tree in half the
clones — measured: `tests/test_ci_publish_order.py::test_every_image_install_pulls_is_published` fails on a
clean `798cbee` checkout because `origin/main` there is the fork's `d9edbdb`. The failure reads as a code or
registry defect and is neither.

Resolution order, each step printed when it is not the obvious one:

1. a remote whose URL names the repository the PRs target (`asimov-agent/llgenie`);
2. else `origin/main`, then `upstream/main`;
3. else the merge-base with `HEAD~1` — a local answer, better than nothing, and says so.

Usage:
    from base_ref import resolve_base
    base = resolve_base()             # e.g. "upstream/main"
"""

from __future__ import annotations

import subprocess
import sys

#: The repository PRs are opened against; the remote whose URL matches this one is the base.
BASE_REPO = "asimov-agent/llgenie"


def _git(*args: str, cwd: str | None = None) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)
    return r.stdout if r.returncode == 0 else ""


def base_remote(cwd: str | None = None) -> str:
    """The remote name whose URL is the base repository, or "" when none is configured."""
    for line in _git("remote", "-v", cwd=cwd).splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        if BASE_REPO in url:
            return name
    return ""


def _exists(ref: str, cwd: str | None = None) -> bool:
    return bool(_git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=cwd).strip())


def resolve_base(cwd: str | None = None, explicit: str = "", quiet: bool = False) -> str:
    """A ref that exists and is the base branch of this clone: `<remote>/main` by preference.

    An `explicit` ref is used verbatim (and still verified), so a caller can pin the comparison.
    """
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    else:
        remote = base_remote(cwd)
        if remote:
            candidates.append(f"{remote}/main")
        # `upstream` before `origin` when both exist: a clone that has an `upstream` is the maintainer layout,
        # where `origin` is the owner's fork (the convention this repository's own docs state). A clone with
        # only `origin` — CI — is unaffected, because the name is absent.
        if any(line.startswith("upstream\t") or line.split()[:1] == ["upstream"]
               for line in _git("remote", cwd=cwd).splitlines()):
            candidates.append("upstream/main")
        candidates.append("origin/main")

    for ref in candidates:
        if _exists(ref, cwd=cwd):
            if not quiet and ref != "origin/main":
                print(f"[base-ref] using `{ref}` — the base remote in this clone is "
                      f"`{base_remote(cwd) or 'unknown'}`, not `origin` (#925)", file=sys.stderr)
            return ref

    fallback = _git("rev-parse", "--short", "HEAD~1", cwd=cwd).strip() or "HEAD"
    if not quiet:
        print(f"[base-ref] no base branch is configured; comparing against `{fallback}` — pass an explicit "
              f"base if the diff matters (#925)", file=sys.stderr)
    return fallback


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--explicit", default="", help="use this ref verbatim (still verified)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    print(resolve_base(explicit=args.explicit, quiet=args.quiet))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
