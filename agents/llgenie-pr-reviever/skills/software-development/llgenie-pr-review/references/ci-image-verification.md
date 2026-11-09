# Proving tests inside the real CI image, not a local venv

When a dispatch, PR body, or implementer note claims "N/N tests pass in `llgenie/test:latest`", a
local venv `pytest` run is NOT the same evidence — different interpreter, different installed deps,
different conftest behaviour. When that claim is part of an acceptance criterion you are grading,
reproduce it in the published image.

## Pull the image the supported way

`docker pull llgenie/test:latest` fails: the published tag is a content hash
(`ghcr.io/asimov-agent/llgenie/test:<hash>`), not `latest`. The supported path resolves the hash
from the Dockerfile + lockfiles and re-tags it:

```
make test-image        # -> python3 scripts/ci_images.py ensure test
# [ci-images] llgenie/test:latest = ghcr.io/asimov-agent/llgenie/test:<hash> (pulled, not built)
```

Use `ensure` (pull-or-build). `test-image-pull` is for replaying a CI leg verbatim: it fails hard
when nothing is published and never builds.

## Run the graded tests inside it

```
docker run --rm -v "$PWD":/repo -w /repo llgenie/test:latest \
  python -m pytest tests/test_<area>.py -q
```

Mount the PR worktree and run from its root so the image sees the head's code and tests, not the
canonical clone.

## Why the container run is load-bearing

A PR blocked on an earlier gate (acceptance hold, stale base) has its later legs `skipped` — so a
"tests passed" line in the PR body means the suite has not actually been exercised at this head by
CI at all. The container run is the cheap independent proof that the head's tests bite, and it
reproduces the implementer's claim instead of paraphrasing it. Post the run as a record with the
image hash and the pass count; "verified live" in someone else's comment is not your evidence.

## Pitfall

Quote the `ghcr.io/.../test:<hash>` line the pull printed, not the `latest` alias — two
`llgenie/test:latest` lines can be different images.
