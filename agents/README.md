# Host agent profiles

This tree (`agents/<profile>/…`) is the **source of truth** for each host agent's behaviour — its
`SOUL.md` and `skills/`. The live profile at `~/.hermes/profiles/<profile>/` is a **copy**, and the
copy is never edited directly: the sync is one-way (tree → live).

> **The tree is the source; the live profile is a copy; never edit the copy.**

A change to a host agent's behaviour is an issue + PR under `agents/<profile>/`, merged to `main`,
then `make sync-agent-profile PROFILE=<profile>` writes it into the live profile. A live-only edit —
a file edited by hand that has no tree copy — is a finding in `check_agent_profiles.py` (which
profile, by how many bytes, and the remedy), never silent drift the tree re-takes (issue #968).

See [`#791`](https://github.com/asimov-agent/llgenie/issues/791) for what started this, and
[`Makefile`](../Makefile) `sync-agent-profile` / `check-agent-profiles`.
