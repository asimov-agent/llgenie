# Provision agent profiles at setup time (issue #2165)

## What changed

`agents/<profile>/` has always been the versioned source of truth for each
lane's `SOUL.md` and `skills/`, and `make sync-agent-profile PROFILE=<p>` the one
seam copying it — but **nothing invoked that seam when a profile was created or
rebuilt**. Measured 2026-11-08: every hit of `sync-agent-profile|agent_profile_sync`
across workflows/scripts/Makefile was a declaration, a hint, a promise or a
report; there was no caller. A rebuilt profile started with whatever its home
contained and failed silently (a missing/older `SOUL.md` produces no error and no
log line). That is why #2090 measured 586 live→tree drift findings over 474 files
across 13 lanes.

This change makes provisioning a real, wired step:

- **`scripts/provision_agent_profiles.py`** — the provisioning entrypoint:
  materialises **every** lane's `agents/<profile>/` (SOUL.md + skills/) into its
  Hermes home, idempotently, reusing `scripts/agent_profile_sync.py`'s own
  `write`/`check` (never reimplementing the copy — write-then-read-back and the
  no-delete path are preserved by construction).
- **`make provision-agent-profiles`** — the make seam; wired as a prerequisite of
  `make install` (the real setup/rebuild path), so a rebuild cannot skip it.
  `CHECK=1` (the `--check` mode) is the **post-provision gate**: it compares every
  provisioned profile back against the tree and fails (exit 1) naming the profile
  and the differing path.
- **Safety untouched:** one-way copy (`agents/` is source, the live profile is a
  copy); provisioning writes only files the tree carries, so a profile's memory,
  `state.db`, `.env` and live-only skills are untouched; there is **no delete
  path**; a live-only edit stays a *finding*, never something provisioning
  silently re-takes.
- **`tests/test_provision_agent_profiles.py`** — proves it against a temporary
  home (no live profile touched): a fresh empty home matches the tree exactly; the
  gate reds on a missing/mutated tree-carried file and greens after a
  re-provision; a profile's own files survive; provisioning twice is a no-op.

## How to use

```
make provision-agent-profiles            # materialise every lane (setup/rebuild)
make provision-agent-profiles CHECK=1    # post-provision gate: reds on divergence
```

## Not covered

Drift *detection* remains #2090/#2135 (reporting divergence is not this change;
this makes provisioning produce a correct profile in the first place). The
live-profile comparison still cannot run in CI (#928) — the gate here checks the
*provisioned* result, which a test creates in a temporary home.
