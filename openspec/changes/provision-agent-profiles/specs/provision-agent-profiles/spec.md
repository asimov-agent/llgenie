# Add a provisioning entrypoint that materialises agents/<profile>/ at setup time

## ADDED Requirements

### Requirement: a provisioning entrypoint materialises every lane from the tree, idempotently

A provisioning entrypoint must exist that, for every profile the manifest lists,
copies `agents/<profile>/SOUL.md` and `skills/` into that profile's Hermes home,
reusing `scripts/agent_profile_sync.py`'s own write/check (never reimplementing
the copy), and a second run over an already-provisioned home is a no-op.

#### Scenario: provisioning a fresh empty home matches the tree exactly

Given a temporary empty profile home,
when the provisioning entrypoint runs against it,
then every lane's `SOUL.md` and `skills/` exist and the post-provision comparison
against the tree exits 0.

#### Scenario: a second provisioning run is a no-op

Given an already-provisioned profile home,
when provisioning runs again,
then no tree-carried file changes and the entrypoint exits 0.

### Requirement: the post-provision gate fails on any divergence

After provisioning, a comparison must check every provisioned profile back
against the tree and exit non-zero naming the profile and the differing path when
any file differs. A missing or mutated tree-carried file must red the gate, and a
re-provision must restore it (green).

#### Scenario: a missing SOUL.md reds the gate and re-provisioning restores it

Given a provisioned profile whose `SOUL.md` was removed,
when the gate runs,
then it exits non-zero naming the profile and `SOUL.md`;
when provisioning runs again,
then `SOUL.md` is restored and the gate exits 0.

### Requirement: provisioning is wired into the real setup/rebuild path

The provisioning entrypoint must be invoked by the target that actually creates
or rebuilds a profile (the install/setup path), not merely documented as a
command a human should remember, so a rebuild cannot skip it.

#### Scenario: make install provisions the profiles

Given a host running the setup/install target,
when `make install` completes,
then the provisioning entrypoint has run (it is a prerequisite), materialising
every lane from the tree.

### Requirement: provisioning preserves the one-way copy safety properties

Provisioning must write only files the tree carries and must never delete from a
live profile: a profile's own files (memory, `state.db`, `.env`, live-only
skills) survive provisioning, and a live-only edit is a finding reported by the
comparison, never something provisioning silently re-takes.

#### Scenario: profile-owned files survive provisioning

Given a provisioned profile that also contains `.env` and a live-only skill,
when provisioning runs again,
then `.env` and the live-only skill still exist.

#### Scenario: a live-only edit is a finding, not silently re-taken

Given a profile whose tree-carried file carries an extra live-only line,
when provisioning runs,
then that line is not deleted by provisioning (the write refuses a live-only
edit) and the comparison keeps it red until deliberately merged.
