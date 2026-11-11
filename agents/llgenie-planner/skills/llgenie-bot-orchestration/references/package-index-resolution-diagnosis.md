# Package-index resolution: why `--extra-index-url`/`unsafe-best-match` cannot always defeat a placeholder

Use when an engine cell reds with a package build/import error (`Failed to build \`X==0.1.0\``, `ModuleNotFoundError: No module named 'poetry'`, `was included because <pkg> depends on X`) and a PR claims the fix is an added `--extra-index-url <mirror>` + `--index-strategy unsafe-best-match`.

## The trap
`unsafe-best-match` **only reorders candidate versions for the SAME package NAME across all configured indexes**. If the alternate index does not publish a wheel under that exact package name, no amount of `--extra-index-url` will stop the resolver from falling back to the public placeholder (e.g. PyPI `rocm==0.1.0`). The dependency the error names is literal — `<pkg> depends on \`rocm\`` means the resolver needs a distribution named `rocm`, not `rocm-sdk-*`, not `rocm-bootstrap`, not a `.tar.gz` release archive.

## Verify the fix BEFORE it burns a 240-min engine-build cell
Measure the alternate index's actual contents offline — a directory listing is enough:

```bash
# Does the index publish a WHEEL under the exact package name the error names?
curl -s "<index-root>/<pkg>/" | grep -ocE '\.whl"'      # 0 -> NO wheel under that name
curl -s "<index-root>/<pkg>/" | grep -ocE '\.tar\.gz"'   # tarballs are NOT installable distributions here
curl -s "<index-root>/"        | grep -oiE 'href="[^"]*"' | grep -i <pkg>   # sibling names only?
```

Decision:
- **0 `.whl` under the exact name -> the `--extra-index-url` fix is insufficient** regardless of rebase. Say so on the PR/issue immediately; do not let the lane push and wait for the cell to fail again on a known-fail.
- **>=1 `.whl` under the exact name at a version that satisfies the dep -> the mechanism can work**; then the remaining question is version selection (does the mirror version beat the placeholder?) and build backend availability.

## Where the real fix usually is
When the mirror lacks the named wheel, the error's own hint is the route: make the placeholder buildable (`[tool.uv.extra-build-dependencies] <pkg> = ["poetry"]` or a `uv pip install poetry` prestep) **and** prevent the runtime from using the empty placeholder (preinstall `<pkg>` from a real wheel/metadata, or build the upstream tarball), so the downstream project's runtime gets the real artifact, not `0.1.0`. Alternatively the pinned upstream's dependency must reference the real split package names rather than a bare meta-name.

## Pitfall: an apparent 404/401 from GHCR/an index is often anonymous-auth, not absence
`curl` to a private/token-gated registry returning an auth challenge is **not** a valid measurement of absence — use the registry's own API/authenticated client, or the index directory listing above, which needs no auth. Do not report "image not published" from an unauthenticated curl.

## Pitfall: measure the package name the ERROR names, not the one the PR body claims
A PR body may describe the fix in terms of a meta-package with extras (`rocm[device-gfx*]`); the resolver failure is about the literal name in the traceback. Grep the actual install command (`git show <head>:containers/engines/params/<engine>.json`) for the `--extra-index-url`/`-e .` line and reason from what the traceback dependency is, not the prose.
