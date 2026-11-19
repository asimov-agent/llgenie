# registry-cache-digest-parse — proposal

Issue: [#2924](https://github.com/asimov-agent/llgenie/issues/2924)

## Why

`make registry-cache-gc` cannot delete a single orphan it just listed. Measured on main
`c564764c5645` (2026-11-19): the target printed `FAILED ghcr.io/asimov-agent/llgenie/agent:buildcache:
[registry-cache-orphans] no digest for ...` for all 8 orphans and exited 2 with `deleted 0; remaining
verified orphans: 8`.

The cause is a two-line parse mismatch: `docker buildx imagetools inspect` aligns its line as
`Digest:    sha256:...` (colon then padding spaces), while `scripts/registry_cache_orphans.py::digest_of()`
only accepted a line starting exactly `digest: sha256:` (single space). The digest step therefore
fails before the guarded GHCR delete ever runs. The unit tests injected `digest_resolver`, so the real
parser was never exercised against the tool's only real-world output format.

## What Changes

1. **`scripts/registry_cache_orphans.py`** — extract the digest with one tolerant regex over the
   inspect output: module-level `_DIGEST_RE = re.compile(r"digest:\s*(sha256:[0-9a-fA-F]{16,})",
   re.IGNORECASE)`, consulted via a new `_extract_digest(ref, text)`. Both the real padded `Digest:`
   alignment and the old single-space form resolve to the same digest. The SystemExit wording stays
   identical so the gc failure output keeps its shape.
2. **`tests/test_registry_cache_orphans.py`** — the injected-resolver tests stay; new cases drive the
   REAL `digest_of` through a monkeypatched `run_ok` with the imagetools output captured verbatim from
   GHCR (padded `Digest:    sha256:...` alignment), the legacy `digest: sha256:...` line, and a
   no-digest refusal case.

## Out of scope

The sweep execution itself (deleting the 8 orphans and re-measuring zero) is #2914's own remaining
acceptance item and is stamped there; this change is the tool fix that makes it possible.

##

### MODIFIED Requirements

### Requirement: digest_of resolves the digest from the real imagetools inspect output

`_extract_digest(ref, text)` and `digest_of(ref)` MUST resolve the full content digest from both the
padded `Digest:` alignment captured verbatim from GHCR and the legacy single-space `digest:` form, and
MUST raise `SystemExit` naming the ref when no digest is present, keeping the exact current wording.
