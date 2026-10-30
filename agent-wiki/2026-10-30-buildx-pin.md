# Re-point the dead docker/setup-buildx-action pin

CI's `docker/setup-buildx-action` was pinned to `8d2750c68a` (a `# v3` tag reference). That commit is NOT
served by upstream anymore — verified by the failing `linux / unit` on main (run 41057782597: "Unable to
resolve action docker/setup-buildx-action@8d2750…" in 7s at the action-resolve step) — so every CI run on
main died before any test started.

The fix re-points all five `setup-buildx-action` uses to the resolvable `v3.11.1` commit
`e468171a9de216ec08956ac3ada2f0791b6bd435` (verified HTTP 200 via the GH API; not the dead `v3`/`v3.12.0`
tag, which still names `8d2750c68a` — re-pinning `@v3` would repeat the exact failure). This keeps the
buildx v3 line and stays reproducible (pinned commit, not a floating tag):
- `.github/workflows/ci.yml` (2 sites, the `ci-images` and `scanner-images` buildx setup)
- `.github/workflows/engine-build.yml`
- `.github/workflows/publish-agent-image.yml`
- `.github/actions/docker/action.yml` (the shared Docker action)

The Node-20 checkout deprecation notice is unrelated and untouched (out of scope). PR #1048.
