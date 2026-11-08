# Materialise agents/<profile>/ into every profile at setup/rebuild time (issue #2165)

## Why

`agents/<profile>/` versions every lane's `SOUL.md` and `skills/`, and
`make sync-agent-profile PROFILE=<p>` is the one seam that copies it — but
nothing invokes that seam when a profile is created or rebuilt. Measured on
origin/main 2026-11-08: every hit of `sync-agent-profile|agent_profile_sync`
across workflows/scripts/Makefile is a declaration, a hint, a promise or a
report — there is no caller. A rebuilt profile starts with whatever its home
happens to contain and fails silently (a missing/older `SOUL.md` produces no
error and no log line). That is why #2090 measured 586 live→tree drift findings
over 474 files across 13 lanes.

## The change

1. **`scripts/provision_agent_profiles.py`** — the provisioning entrypoint:
   materialises EVERY profile the manifest lists from `agents/<profile>/` into
   its Hermes home, idempotently, reusing `agent_profile_sync`'s own `write`/
   `check` (never reimplementing the copy — the write-then-read-back and the
   no-delete path are preserved by construction).
2. **`make provision-agent-profiles`** — the make seam, wired into `make install`
   (the real setup/rebuild path) so a rebuild cannot skip it. `--check` is the
   post-provision gate: compares every provisioned profile back against the tree
   and fails naming the profile and path.
3. Safety kept intact: one-way copy (tree is source); writes only tree-carried
   files (a profile's memory/state.db/.env/live-only skills untouched); no delete
   path; a live-only edit stays a finding.
4. `tests/test_provision_agent_profiles.py` proves it against a temporary home:
   fresh empty home matches tree exactly, gate reds on a missing/mutated file and
   greens after re-provision, profile-own files survive, idempotence is a no-op.
