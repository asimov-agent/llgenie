# Build-once / publish / pull — image tagging and the single-definition rule

The build-once pattern (build in one job, push to GHCR, dependent jobs pull) extends to EVERY image the pipeline needs — including the TEST image. Building a derived image inline in each workflow is N implementations of one stage, and locally the only way to get it is a build on top of a CACHED GHCR base, which silently diverges from the revision's own base.

## The single-definition rule

One script (e.g. `scripts/ensure_image.py`) is the ONE definition of "built from this revision". It owns the tags, the pull-vs-build decision, and the publisher's rebuild decision — so a job and the publisher can never disagree on what a tag means.

- **Tag each image as the sha256 (first 12) of its inputs.**
  - base: `Dockerfile` + `Dockerfile.test`
  - test: `Dockerfile.test` + `requirements-test.txt` + the base hash
- **The hash recipe must be byte-identical to tags already published** — changing the recipe invalidates every published tag. Verify before shipping: `python3 scripts/ensure_image.py tags` must print the tag already on GHCR for the current revision.
- **`make image-ensure` (both images) / `make image-ensure-base` (jobs that only run the image)** — the target asks the script, which PULLS the published image when that tag exists and otherwise BUILDS it (base from `Dockerfile`, test image on that base). No inline `docker pull` / `docker tag` / `docker build -f Dockerfile.test` should remain in `.github/workflows/**`.
- **Publish on: tag missing, weekly (Sunday), or a `force_rebuild=true` dispatch input** — the same rules as the base, so a mid-week Dockerfile/req change can be pushed out-of-band by dispatching with `force_rebuild=true` instead of waiting for the gate day.

## The cached-base pitfall

A derived/test image must be built on the revision's OWN base, never a cached pull. `Dockerfile.test` takes its `FROM` as a build arg so a cached GHCR base can never stand in for the revision's base. A test image layered on a stale base silently loses whatever the base installs (a plugin, a binary), and the guard that asserts it can only fail — the failure looks like a broken guard, not a stale image.

## Verify the pulled base carries what the guard asserts

After `make image-ensure-base` pulls, inspect the pulled image for the thing a guard depends on before trusting it:

```bash
docker run --rm --entrypoint sh <base-image> -c 'ls /root/.hermes/plugins/nerve'
```

A guard that asserts a plugin/binary is present is only as good as the base it runs on; prove the pulled base has it, not just that the pull succeeded.

## Verify the new tag really reached GHCR

A green build/push job or a merged image PR does NOT prove reachability. Read the package back for the expected tag + timestamp:

```bash
gh api "user/packages/container/<name>/versions" \
  --jq '.[] | "tags=\(.metadata.container.tags|join(",")) created=\(.created_at)"'
```

A 404 for a package whose push job is still in flight is normal — re-check after the job completes.

